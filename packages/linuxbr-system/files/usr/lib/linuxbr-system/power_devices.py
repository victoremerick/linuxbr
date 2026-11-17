"""Choose temporary PowerDevil and power-profiles-daemon rules by power source."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import dbus
from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QMessageBox, QVBoxLayout)

from file_tools import plain_label
from quick_commands import atomic_write
from visual_style import BUTTONS


CONTEXTS = {'battery': 'Na bateria', 'charger': 'No carregador', 'dock': 'No dock, com alimentação externa'}
MODES = {'': 'Usar o perfil do Plasma', 'power-saver': 'Economia de energia', 'performance': 'Desempenho'}
UPOWER = 'org.freedesktop.UPower'
UPOWER_PATH = '/org/freedesktop/UPower'
PPD = UPOWER + '.PowerProfiles'
PPD_PATH = UPOWER_PATH + '/PowerProfiles'
POLICY = 'org.kde.Solid.PowerManagement.PolicyAgent'
POLICY_PATH = '/org/kde/Solid/PowerManagement/PolicyAgent'
PROPERTIES = 'org.freedesktop.DBus.Properties'
NAME = 'Perfis de energia do Linux BR'
APP_ID = 'linuxbr-power-devices'


def location():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/power-devices.json'


def item(path):
    try:
        return path.read_text(encoding='utf-8', errors='replace').strip()[:250]
    except OSError:
        return ''


def usb_devices(root=Path('/sys/bus/usb/devices')):
    devices = {}
    for path in sorted(root.glob('*')):
        if re.fullmatch(r'usb[0-9]+', path.name):
            continue
        vendor, product = item(path / 'idVendor'), item(path / 'idProduct')
        if not re.fullmatch('[0-9a-fA-F]{4}', vendor) or not re.fullmatch('[0-9a-fA-F]{4}', product):
            continue
        serial = item(path / 'serial')
        connector = 'serial=' + serial if serial and serial.isprintable() else 'port=' + path.name
        identifier = vendor.lower() + ':' + product.lower() + ':' + connector
        description = item(path / 'product') or item(path / 'manufacturer') or 'Dispositivo USB'
        devices[identifier] = f'{description} · USB {vendor}:{product} · {path.name}'
    return devices


def verify(value):
    if not isinstance(value, dict) or value.keys() != {'dock', 'rules'}:
        raise ValueError('As preferências de energia são inválidas.')
    selected = value['dock']
    if (not isinstance(selected, str) or selected and
            (not selected.isprintable() or len(selected) > 300 or not re.fullmatch(
                r'[0-9a-f]{4}:[0-9a-f]{4}:(?:serial|port)=[^\r\n]+', selected))):
        raise ValueError('O dispositivo USB selecionado é inválido.')
    rules = value['rules']
    if (not isinstance(rules, dict) or rules.keys() != CONTEXTS.keys()
            or any(not isinstance(entry, list) or len(entry) != 3 or not isinstance(entry[0], str)
                   or entry[0] not in MODES or any(type(flag) is not bool for flag in entry[1:])
                   for entry in rules.values())):
        raise ValueError('Selecione um perfil de energia oferecido pelo sistema por fonte de alimentação.')
    if not selected and any(rules['dock']):
        raise ValueError('Escolha o dispositivo USB que identifica o dock antes de ativar suas preferências.')
    return value


def load():
    try:
        return verify(json.loads(location().read_text(encoding='utf-8')))
    except FileNotFoundError:
        return {'dock': '', 'rules': {name: ['', False, False] for name in CONTEXTS}}


def save(value):
    verify(value)
    atomic_write(location(), json.dumps(value))
    enabled = any(any(rule) for rule in value['rules'].values())
    subprocess.run(['/usr/bin/systemctl', '--user', 'enable' if enabled else 'disable', '--now',
                    'linuxbr-power-devices.service'], check=True, capture_output=True, timeout=8)


def source(bus):
    return bool(dbus.Interface(bus.get_object(UPOWER, UPOWER_PATH), PROPERTIES).Get(UPOWER, 'OnBattery', timeout=3))


def context(on_battery, dock, connected):
    return 'battery' if on_battery else 'dock' if dock and dock in connected else 'charger'


class Hold:
    def __init__(self, bus, service, path, acquire, release):
        self.bus, self.service, self.path = bus, service, path
        self.acquire, self.release = acquire, release
        self.owner = self.request = self.cookie = None

    def set(self, request, *args):
        if request is None and self.cookie is None:
            return
        try:
            owner = self.bus.get_name_owner(self.service)
        except dbus.DBusException:
            self.owner = self.cookie = self.request = None
            return
        if owner != self.owner:
            self.owner, self.cookie, self.request = owner, None, None
        if request == self.request:
            return  # Keep user overrides in effect until the next context or configuration change.
        api = dbus.Interface(self.bus.get_object(owner, self.path), self.service)
        if self.cookie is not None:
            try:
                getattr(api, self.release)(dbus.UInt32(self.cookie), timeout=3)
            except dbus.DBusException as error:
                if self.service != PPD or error.get_dbus_name() != 'org.freedesktop.DBus.Error.InvalidArgs':
                    raise
            self.cookie = self.request = None
        if request is not None:
            self.cookie = getattr(api, self.acquire)(*args, timeout=3)
            self.request = request


class PowerRules:
    def __init__(self, system, session):
        self.system = system
        self.profile = Hold(system, PPD, PPD_PATH, 'HoldProfile', 'ReleaseProfile')
        self.inhibit = Hold(session, POLICY, POLICY_PATH, 'AddInhibition', 'ReleaseInhibition')

    def refresh(self):
        try:
            config = load()
            if any(any(rule) for rule in config['rules'].values()):
                active = context(source(self.system), config['dock'], usb_devices() if config['dock'] else {})
                self.apply(active, config['rules'][active])
            else:
                self.apply('', ['', False, False])
        except (OSError, ValueError, dbus.DBusException) as error:
            self.apply('', ['', False, False])
            print(str(error), file=sys.stderr)

    def apply(self, active, rule):
        mode, screen, suspend = rule
        flags = 4 if screen else 1 if suspend else 0
        reason = CONTEXTS.get(active, NAME)
        for hold, request, args in ((self.profile, (active, mode) if mode else None, (mode, reason, APP_ID)),
                                    (self.inhibit, (active, flags) if flags else None, (dbus.UInt32(flags), NAME, reason))):
            try:
                hold.set(request, *args)
            except dbus.DBusException as error:
                print(error.get_dbus_message(), file=sys.stderr)


class PowerDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Energia por carregador e dock')
        self.setWindowIcon(QIcon.fromTheme('preferences-system-power-management'))
        self.setMinimumWidth(620)
        config = load()
        profile_info = {}
        battery = None
        try:
            bus = dbus.SystemBus()
            battery = source(bus)
            profile_info = dbus.Interface(bus.get_object(PPD, PPD_PATH), PROPERTIES).GetAll(PPD, timeout=3)
        except dbus.DBusException:
            pass
        available = {entry.get('Profile') for entry in profile_info.get('Profiles', [])}
        devices = usb_devices()
        layout = QVBoxLayout(self)
        layout.addWidget(plain_label('Conecte o dock e selecione abaixo o dispositivo USB que identifica a estação. '
                                     'Sem número de série, o Linux BR identifica a estação pela porta USB.'))
        self.dock = QComboBox()
        self.dock.setAccessibleName('Dispositivo USB que identifica o dock')
        self.dock.addItem('Nenhum dock selecionado', '')
        for key, label in devices.items():
            self.dock.addItem(label, key)
        if config['dock'] and config['dock'] not in devices:
            self.dock.addItem('Dock configurado (desconectado)', config['dock'])
        self.dock.setCurrentIndex(self.dock.findData(config['dock']))
        layout.addWidget(self.dock)
        self.rows = {}
        for key, label in CONTEXTS.items():
            group = QGroupBox(label)
            form = QFormLayout(group)
            profile = QComboBox()
            for mode, name in MODES.items():
                if not mode or mode in available or mode == config['rules'][key][0]:
                    profile.addItem(name if not mode or mode in available else name + ' (indisponível)', mode)
            profile.setCurrentIndex(profile.findData(config['rules'][key][0]))
            form.addRow('Desempenho', profile)
            screen = QCheckBox('Manter a tela ligada durante a inatividade')
            suspend = QCheckBox('Adiar a suspensão automática')
            screen.setChecked(config['rules'][key][1])
            suspend.setChecked(config['rules'][key][2])
            screen.toggled.connect(suspend.setDisabled)
            suspend.setDisabled(screen.isChecked())
            form.addRow(screen)
            form.addRow(suspend)
            layout.addWidget(group)
            self.rows[key] = (profile, screen, suspend)
        if not available:
            layout.addWidget(plain_label('O serviço de perfis de desempenho está indisponível. As opções de '
                                         'inatividade continuam disponíveis no Plasma.'))
        layout.addWidget(plain_label('Manter a tela ligada também adia a suspensão automática. O Plasma aplica '
                                     'seus próprios tempos de inatividade e as ações de bloqueio da tela.'))
        self.status = plain_label('Alimentação atual — ' + CONTEXTS[context(battery, config['dock'], devices)]
                                  if battery is not None else 'Não foi possível consultar a fonte de alimentação.')
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.store)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def store(self):
        try:
            save({'dock': self.dock.currentData(), 'rules': {key: [mode.currentData(), screen.isChecked(), suspend.isChecked()]
                  for key, (mode, screen, suspend) in self.rows.items()}})
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.status.setText('Não foi possível aplicar as regras de energia. ' + str(error))
            return
        self.accept()


def main():
    if sys.argv[1:] == ['--daemon']:
        app = QCoreApplication(sys.argv)
        worker = PowerRules(dbus.SystemBus(), dbus.SessionBus())
        timer = QTimer(app)
        timer.timeout.connect(worker.refresh)
        timer.start(5000)
        QTimer.singleShot(0, worker.refresh)
        return app.exec()
    app = QApplication(sys.argv)
    app.setStyleSheet(BUTTONS)
    app.setDesktopFileName(APP_ID)
    try:
        PowerDialog().exec()
    except (OSError, ValueError) as error:
        QMessageBox.warning(None, 'Energia por carregador e dock', str(error))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
