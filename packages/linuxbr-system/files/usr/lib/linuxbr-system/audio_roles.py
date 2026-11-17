"""Route playback streams with an explicit PipeWire or PulseAudio media role."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QVBoxLayout)

from audio import pactl
from file_tools import plain_label
from quick_commands import atomic_write


CATEGORIES = {'calls': 'Chamadas', 'media': 'Mídia', 'games': 'Jogos'}
ROLES = {'communication': 'calls', 'phone': 'calls', 'music': 'media', 'video': 'media',
         'movie': 'media', 'game': 'games'}
DEVICE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,254}\Z')


def location():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/audio-roles.json'


def validate(value):
    if not isinstance(value, dict) or value.keys() != CATEGORIES.keys():
        raise ValueError('O arquivo de configuração das saídas é inválido.')
    for route in value.values():
        if (not isinstance(route, list) or len(route) != 2
                or any(not isinstance(name, str) or name and not DEVICE.fullmatch(name) for name in route)
                or route[0] and route[0] == route[1]):
            raise ValueError('Selecione saídas diferentes para o dispositivo preferido e o de reserva.')
    return value


def load():
    try:
        return validate(json.loads(location().read_text(encoding='utf-8')))
    except FileNotFoundError:
        return {category: ['', ''] for category in CATEGORIES}


def configure(rules):
    validate(rules)
    command = ['/usr/bin/systemctl', '--user', 'enable' if any(any(rule) for rule in rules.values()) else 'disable',
               '--now', 'linuxbr-audio-roles.service']
    atomic_write(location(), json.dumps(rules))
    subprocess.run(command, capture_output=True, check=True, timeout=8)


def sink_available(sink):
    port = sink.get('active_port')
    if isinstance(port, str):
        port = next((entry for entry in (sink.get('ports') or []) if entry.get('name') == port), {})
    return not isinstance(port, dict) or port.get('availability') not in ('no', 'not available')


class Router:
    def __init__(self):
        self.observed = {}

    def update(self, routes, sinks, streams):
        devices = {sink['name']: sink['index'] for sink in sinks if sink_available(sink)}
        observed = {}
        for stream in streams:
            properties = stream.get('properties', {})
            role = str(properties.get('media.role', '')).casefold()
            names = routes.get(ROLES.get(role), ())
            target = next(((name, devices[name]) for name in names if name in devices), None)
            index = stream['index']
            key = (index, properties.get('object.serial'), properties.get('application.process.id'), role)
            if target and self.observed.get(key) != target and stream.get('sink') != target[1]:
                try:
                    pactl('move-sink-input', str(index), target[0])
                except (OSError, subprocess.SubprocessError):
                    continue  # The stream can close or the device disconnect during the move.
            observed[key] = target
        self.observed = observed

    def refresh(self):
        try:
            routes = load()
            if any(any(route) for route in routes.values()):
                sinks = json.loads(pactl('-f', 'json', 'list', 'sinks'))
                streams = json.loads(pactl('-f', 'json', 'list', 'sink-inputs'))
                self.update(routes, sinks, streams)
            else:
                self.observed.clear()
        except (OSError, ValueError, subprocess.SubprocessError):
            self.observed.clear()


class AudioRoutes(QDialog):
    def __init__(self, sinks, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Saídas por tipo de uso')
        self.setWindowIcon(QIcon.fromTheme('audio-volume-high'))
        self.setMinimumWidth(560)
        self.rows = {}
        layout = QVBoxLayout(self)
        layout.addWidget(plain_label('Escolha em qual dispositivo tocar cada tipo de som. A reserva é usada '
                                     'quando a saída preferida está desconectada. Aplicativos que não '
                                     'informam o tipo de áudio podem ser ajustados no mixer.'))
        rules = load()
        for category, label in CATEGORIES.items():
            group = QGroupBox(label)
            form = QFormLayout(group)
            self.rows[category] = []
            for index, (title, default) in enumerate((('Saída preferida', 'Usar o roteamento do sistema'),
                                                       ('Saída de reserva', 'Sem saída de reserva'))):
                selector = QComboBox()
                selector.addItem(default, '')
                for sink in sinks:
                    if DEVICE.fullmatch(sink['name']):
                        selector.addItem(sink.get('description') or sink['name'], sink['name'])
                saved = rules[category][index]
                if saved and selector.findData(saved) < 0:
                    selector.addItem(f'{saved} (indisponível)', saved)
                selector.setCurrentIndex(selector.findData(saved))
                form.addRow(title, selector)
                self.rows[category].append(selector)
            layout.addWidget(group)
        self.status = plain_label('')
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.store)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def store(self):
        try:
            configure({category: [selector.currentData() for selector in selectors]
                       for category, selectors in self.rows.items()})
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.status.setText('Não foi possível aplicar as saídas: ' + str(error))
            return
        self.accept()


def daemon():
    app = QCoreApplication(sys.argv)
    router = Router()
    timer = QTimer(app)
    timer.timeout.connect(router.refresh)
    timer.start(4000)
    QTimer.singleShot(0, router.refresh)
    return app.exec()


if __name__ == '__main__':
    sys.exit(daemon())
