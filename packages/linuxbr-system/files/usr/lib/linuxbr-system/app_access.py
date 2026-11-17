"""Per-application startup adjustments for supported Qt Widgets programs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QMessageBox, QPushButton, QVBoxLayout)

from file_tools import plain_label
from quick_commands import atomic_write, data
from visual_style import BUTTONS


APPLICATIONS = {
    'dolphin': ('Explorador de Arquivos', 'system-file-manager'),
    'kate': ('Kate', 'kate'),
    'konsole': ('Konsole', 'utilities-terminal'),
    'okular': ('Okular', 'okular'),
    'kcalc': ('Calculadora', 'accessories-calculator'),
    'kolourpaint': ('KolourPaint', 'kolourpaint'),
}
SCALES = {'': 'Escala do sistema', '1.25': '125%', '1.5': '150%', '1.75': '175%', '2': '200%'}
HIGH_CONTRAST = '''
QWidget {
    background-color: #ffffff;
    color: #111111;
    selection-background-color: #002d81;
    selection-color: #ffffff;
    alternate-background-color: #e6e6e6;
}
QPushButton, QToolButton, QLineEdit, QComboBox, QSpinBox, QGroupBox {
    border: 1px solid #161616;
}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #002d81;
}
QWidget:disabled { color: #535353; }
'''


def app_path(app):
    if app not in APPLICATIONS:
        raise ValueError('Selecione um aplicativo compatível.')
    return Path('/usr/bin') / app


def configuration(app, extension):
    app_path(app)
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/app-access' / (app + extension)


def shortcut(app):
    app_path(app)
    return data() / 'applications' / ('linuxbr-app-access-' + app + '.desktop')


def validate(value):
    if (not isinstance(value, dict) or value.keys() != {'scale', 'contrast', 'motion'}
            or not isinstance(value['scale'], str) or value['scale'] not in SCALES
            or type(value['contrast']) is not bool or type(value['motion']) is not bool):
        raise ValueError('Selecione uma escala e opções de aparência válidas.')
    return value


def load(app):
    try:
        return validate(json.loads(configuration(app, '.json').read_text(encoding='utf-8')))
    except FileNotFoundError:
        return {'scale': '', 'contrast': False, 'motion': False}


def save(app, preferences):
    validate(preferences)
    filename = configuration(app, '.json')
    destination = shortcut(app)
    if not any(preferences.values()):
        destination.unlink(missing_ok=True)
        filename.unlink(missing_ok=True)
        configuration(app, '.qss').unlink(missing_ok=True)
        return False
    name, icon = APPLICATIONS[app]
    previous = filename.read_text(encoding='utf-8') if filename.is_file() else None
    atomic_write(filename, json.dumps(preferences))
    try:
        atomic_write(destination, ('[Desktop Entry]\nType=Application\n'
                                   f'Name={name} (acessível)\nIcon={icon}\n'
                                   f'Exec=/usr/bin/linuxbr-app-access --launch {app}\n'
                                   'Categories=Accessibility;Utility;\nTerminal=false\nStartupNotify=false\n'))
    except OSError:
        if previous is None:
            filename.unlink(missing_ok=True)
        else:
            atomic_write(filename, previous)
        raise
    return True


def launch(app):
    executable = app_path(app)
    preferences = load(app)
    if not executable.is_file():
        raise ValueError('O aplicativo foi removido deste computador.')
    if not any(preferences.values()):
        raise ValueError('Salve as preferências em Aparência acessível por aplicativo e abra o novo atalho.')
    environment = os.environ.copy()
    if preferences['scale']:
        environment['QT_SCALE_FACTOR'] = preferences['scale']
    sheet = HIGH_CONTRAST if preferences['contrast'] else ''
    if preferences['motion']:
        sheet += '\n* { widget-animation-duration: 0; }\n'
    command = [str(executable)]
    if sheet:
        path = configuration(app, '.qss')
        atomic_write(path, sheet)
        command.extend(('-stylesheet', str(path)))
    return subprocess.Popen(command, env=environment, start_new_session=True)


class AppAccess(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Aparência acessível por aplicativo')
        self.setWindowIcon(QIcon.fromTheme('preferences-desktop-color'))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.addWidget(plain_label('Salve suas escolhas e abra o atalho com “(acessível)” no Iniciar. '
                                     'Feche as janelas existentes do aplicativo para carregar os ajustes.'))
        form = QFormLayout()
        self.apps = QComboBox()
        self.scale = QComboBox()
        for key, (label, icon) in APPLICATIONS.items():
            if app_path(key).is_file():
                self.apps.addItem(QIcon.fromTheme(icon), label, key)
        for key, label in SCALES.items():
            self.scale.addItem(label, key)
        form.addRow('Aplicativo', self.apps)
        form.addRow('Escala em relação ao sistema', self.scale)
        self.contrast = QCheckBox('Aumentar o contraste dos controles')
        self.motion = QCheckBox('Reduzir animações dos controles')
        form.addRow(self.contrast)
        form.addRow(self.motion)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        reset = QPushButton('Remover atalho acessível')
        reset.clicked.connect(lambda: self.store(reset=True))
        buttons.addWidget(reset)
        buttons.addStretch()
        confirm = QPushButton('Salvar atalho')
        confirm.clicked.connect(lambda: self.store())
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.status = plain_label('')
        layout.addWidget(self.status)
        self.apps.currentIndexChanged.connect(self.select)
        for control in (self.scale, self.contrast, self.motion, confirm, reset):
            control.setEnabled(self.apps.count() > 0)
        self.select()

    def select(self):
        app = self.apps.currentData()
        if not app:
            self.status.setText('Nenhum aplicativo compatível está instalado.')
            return
        try:
            preferences = load(app)
            self.status.setText('Atalho acessível disponível no Iniciar.' if shortcut(app).is_file() else '')
        except (OSError, ValueError):
            preferences = {'scale': '', 'contrast': False, 'motion': False}
            self.status.setText('As preferências precisam ser salvas novamente.')
        self.scale.setCurrentIndex(self.scale.findData(preferences['scale']))
        self.contrast.setChecked(preferences['contrast'])
        self.motion.setChecked(preferences['motion'])

    def store(self, reset=False):
        app = self.apps.currentData()
        preferences = {'scale': '' if reset else self.scale.currentData(),
                       'contrast': not reset and self.contrast.isChecked(),
                       'motion': not reset and self.motion.isChecked()}
        try:
            created = save(app, preferences)
            self.select()
            self.status.setText('Atalho salvo no Iniciar.' if created else 'Atalho acessível removido.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch', choices=tuple(APPLICATIONS))
    args = parser.parse_args()
    if args.launch:
        try:
            launch(args.launch)
            return 0
        except (OSError, ValueError) as error:
            application = QApplication(sys.argv)
            QMessageBox.warning(None, 'Aparência acessível por aplicativo', str(error))
            return 1
    application = QApplication(sys.argv)
    application.setStyleSheet(BUTTONS)
    application.setDesktopFileName('linuxbr-app-access')
    AppAccess().exec()
    return 0


if __name__ == '__main__':
    sys.exit(main())
