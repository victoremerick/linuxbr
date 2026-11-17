"""Use Plasma's notification inhibition for a recurring, per-user schedule."""
import argparse
from datetime import datetime, time, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import dbus
from PyQt6.QtCore import QCoreApplication, QTime, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QFormLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTimeEdit, QVBoxLayout)

from file_tools import plain_label
from visual_style import BUTTONS


DESKTOP = 'linuxbr-concentration.desktop'
NOTIFICATIONS = 'org.freedesktop.Notifications'
PREFERENCE = re.compile(r'[A-Za-z0-9_.+-]{1,250}\Z')


def location():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/concentration.json'


def load():
    try:
        value = json.loads(location().read_text(encoding='utf-8'))
    except FileNotFoundError:
        return dict(enabled=False, days=[0, 1, 2, 3, 4], start='09:00', end='12:00')
    checked_schedule(value)
    return value


def checked_schedule(value):
    if (not isinstance(value, dict) or type(value.get('enabled')) is not bool
            or not isinstance(value.get('days'), list)
            or any(type(day) is not int or day not in range(7) for day in value['days'])):
        raise ValueError('Dias de concentração inválidos.')
    if not all(isinstance(value.get(key), str) and re.fullmatch(r'\d{2}:\d{2}', value[key])
               for key in ('start', 'end')):
        raise ValueError('Horários de concentração inválidos.')
    start, end = time.fromisoformat(value['start']), time.fromisoformat(value['end'])
    if value['enabled'] and (not value['days'] or start == end):
        raise ValueError('Selecione os dias e informe horários inicial e final diferentes.')
    return start, end


def active(value, now):
    start, end = checked_schedule(value)
    if not value['enabled']:
        return False
    clock = now.time()
    if start < end:
        return now.weekday() in value['days'] and start <= clock < end
    if clock >= start:
        return now.weekday() in value['days']
    return clock < end and (now - timedelta(days=1)).weekday() in value['days']


def save(value):
    checked_schedule(value)
    filename = location()
    filename.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp = tempfile.mkstemp(dir=filename.parent, prefix='.focus-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, filename)
    finally:
        Path(temp).unlink(missing_ok=True)


def group_args(*groups):
    return [argument for group in groups for argument in ('--group', group)]


def read_setting(groups, key, default=False):
    return subprocess.check_output(
        ['/usr/bin/kreadconfig6', '--file', 'plasmanotifyrc', *group_args(*groups), '--key', key,
         '--default', 'true' if default else 'false'], text=True, timeout=4).strip().lower() == 'true'


def write_setting(groups, key, enabled):
    subprocess.run(
        ['/usr/bin/kwriteconfig6', '--notify', '--file', 'plasmanotifyrc', *group_args(*groups),
         '--key', key, '--type', 'bool', 'true' if enabled else 'false'], check=True, timeout=4)


class Inhibition:
    def __init__(self, bus):
        self.bus = bus
        self.owner = None
        self.cookie = None

    def update(self, needed):
        owner = self.bus.get_name_owner(NOTIFICATIONS)
        if owner != self.owner:
            self.owner, self.cookie = owner, None
        interface = dbus.Interface(self.bus.get_object(owner, '/org/freedesktop/Notifications'), NOTIFICATIONS)
        if needed and self.cookie is None:
            self.cookie = interface.Inhibit(DESKTOP[:-8], 'Horário de concentração do Linux BR',
                                            dbus.Dictionary({}, signature='sv'), timeout=3)
        elif not needed and self.cookie is not None:
            interface.UnInhibit(dbus.UInt32(self.cookie), timeout=3)
            self.cookie = None

    def refresh(self):
        try:
            self.update(active(load(), datetime.now()))
        except (OSError, ValueError, dbus.DBusException):
            # The notifier may be between sessions. When it returns we obtain a fresh ID.
            pass


class Settings(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Horários de concentração')
        self.setWindowIcon(QIcon.fromTheme('notifications-disabled'))
        self.resize(650, 540)
        saved = load()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(plain_label('Programe os dias e horários em que deseja reduzir as interrupções. Os avisos continuam no histórico do Plasma.'))
        self.enabled = QCheckBox('Ativar horário de concentração')
        self.enabled.setChecked(saved['enabled'])
        layout.addWidget(self.enabled)
        days = QHBoxLayout()
        self.days = []
        for index, label in enumerate(('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')):
            day = QCheckBox(label); day.setChecked(index in saved['days']); self.days.append(day); days.addWidget(day)
        days.addStretch()
        layout.addLayout(days)
        form = QFormLayout()
        self.start = QTimeEdit(QTime.fromString(saved['start'], 'HH:mm'))
        self.end = QTimeEdit(QTime.fromString(saved['end'], 'HH:mm'))
        for label, field in [('Começar', self.start), ('Terminar', self.end)]:
            field.setDisplayFormat('HH:mm')
            form.addRow(label, field)
        layout.addLayout(form)
        layout.addWidget(plain_label('As exceções abaixo também valem quando o modo Não perturbe é ativado pelo painel.'))
        self.critical = QCheckBox('Mostrar avisos críticos')
        self.critical_original = read_setting(('Notifications',), 'CriticalInDndMode', True)
        self.critical.setChecked(self.critical_original)
        layout.addWidget(self.critical)
        self.applications = QListWidget()
        self.applications.setAccessibleName('Aplicativos autorizados a mostrar avisos durante o silêncio')
        layout.addWidget(self.applications, 1)
        self.application_settings()
        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton(QIcon.fromTheme('document-save'), 'Salvar')
        save_button.clicked.connect(self.store)
        buttons.addWidget(save_button)
        close = QPushButton('Fechar')
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.status = plain_label('')
        layout.addWidget(self.status)

    def application_settings(self):
        from gi.repository import Gio

        entries = {}
        # Read a single KConfig snapshot instead of a subprocess for every application.
        import configparser
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read(location().parents[1] / 'plasmanotifyrc', encoding='utf-8')
        except (configparser.Error, OSError):
            parser.clear()
        for entry in Gio.AppInfo.get_all():
            desktop = entry.get_id() or ''
            identity = desktop.removesuffix('.desktop')
            if not entry.should_show() or not desktop.endswith('.desktop') or not PREFERENCE.fullmatch(identity):
                continue
            entries[identity] = entry.get_display_name()
        for identity, name in sorted(entries.items(), key=lambda value: value[1].casefold()):
            group = 'Applications][' + identity
            original = parser.get(group, 'ShowPopupsInDndMode', fallback='false').lower() == 'true'
            item = QListWidgetItem(f'{name}  ·  {identity}')
            item.setData(Qt.ItemDataRole.UserRole, (identity, original))
            item.setCheckState(Qt.CheckState.Checked if original else Qt.CheckState.Unchecked)
            self.applications.addItem(item)

    def store(self):
        value = dict(enabled=self.enabled.isChecked(), days=[index for index, item in enumerate(self.days) if item.isChecked()],
                     start=self.start.time().toString('HH:mm'), end=self.end.time().toString('HH:mm'))
        try:
            save(value)
            if self.critical.isChecked() != self.critical_original:
                write_setting(('Notifications',), 'CriticalInDndMode', self.critical.isChecked())
                self.critical_original = self.critical.isChecked()
            for index in range(self.applications.count()):
                item = self.applications.item(index)
                identity, original = item.data(Qt.ItemDataRole.UserRole)
                enabled = item.checkState() == Qt.CheckState.Checked
                if enabled != original:
                    write_setting(('Applications', identity), 'ShowPopupsInDndMode', enabled)
                    item.setData(Qt.ItemDataRole.UserRole, (identity, enabled))
            subprocess.run(['/usr/bin/systemctl', '--user', 'enable' if value['enabled'] else 'disable', '--now',
                            'linuxbr-concentration.service'], check=True, timeout=8, capture_output=True)
            self.status.setText('Horário e exceções atualizados.')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.status.setText('Não foi possível aplicar todas as preferências: ' + str(error))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true')
    args = parser.parse_args()
    if args.daemon:
        app = QCoreApplication(sys.argv)
        inhibitor = Inhibition(dbus.SessionBus())
        timer = QTimer(app)
        timer.timeout.connect(inhibitor.refresh)
        timer.start(15000)
        inhibitor.refresh()
        return app.exec()
    app = QApplication(sys.argv)
    app.setDesktopFileName(DESKTOP[:-8])
    app.setStyleSheet(BUTTONS)
    try:
        Settings().exec()
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        QMessageBox.warning(None, 'Horários de concentração', str(error))
        return 1


if __name__ == '__main__':
    sys.exit(main())
