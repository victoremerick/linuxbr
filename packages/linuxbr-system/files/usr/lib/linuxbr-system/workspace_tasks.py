"""Named Plasma activities for task sets, wallpaper and notification routing."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from uuid import UUID

import dbus
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout)

from file_tools import message, plain_label
import quick_commands
from visual_style import BUTTONS


ENTRY = re.compile(r'[A-Za-z0-9_.+-]{1,249}\Z')
ACTIVITIES = 'org.kde.ActivityManager.Activities'


def interface(bus=None):
    bus = bus or dbus.SessionBus()
    return dbus.Interface(bus.get_object('org.kde.ActivityManager', '/ActivityManager/Activities'), ACTIVITIES)


def identifier(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('O espaço de trabalho informado é inválido.')
    return value


def state_file():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/workspaces.json'


def settings():
    try:
        result = json.loads(state_file().read_text(encoding='utf-8'))
    except FileNotFoundError:
        result = {}
    if not isinstance(result, dict):
        raise ValueError('As preferências de espaços estão inválidas.')
    return result


def validate(name, wallpaper, actions, routes):
    name = name.strip()
    if not name or len(name) > 80 or not all(char.isprintable() for char in name):
        raise ValueError('Informe um nome de até 80 caracteres.')
    if wallpaper and (not Path(wallpaper).is_absolute() or not Path(wallpaper).is_file()):
        raise ValueError('Escolha um arquivo de papel de parede disponível.')
    if len(actions) > 20:
        raise ValueError('Inclua até 20 atalhos e aplicativos por espaço.')
    verified = [list(quick_commands.checked_action(action)) for action in actions]
    return dict(name=name, wallpaper=wallpaper, actions=verified, route=bool(routes))


def wallpaper_script(activity, filename):
    return ('for (const desktop of desktopsForActivity(' + json.dumps(identifier(activity)) + ')) {'
            'desktop.wallpaperPlugin = "org.kde.image";'
            'desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];'
            'desktop.writeConfig("Image", ' + json.dumps(Path(filename).as_uri()) + ');'
            '}')


def set_wallpaper(activity, filename):
    if not filename:
        return
    shell = dbus.Interface(dbus.SessionBus().get_object('org.kde.plasmashell', '/PlasmaShell'), 'org.kde.PlasmaShell')
    shell.evaluateScript(wallpaper_script(activity, filename), timeout=7)


def save(activity, value):
    all_settings = settings()
    all_settings[identifier(activity)] = value
    quick_commands.atomic_write(state_file(), json.dumps(all_settings, ensure_ascii=False))


def activate(activity, backend=None):
    api = backend or interface()
    activity = identifier(activity)
    if str(api.CurrentActivity(timeout=4)) != activity and not api.SetCurrentActivity(activity, timeout=8):
        raise ValueError('O Plasma não conseguiu ativar este espaço de trabalho.')


def notification_activity(entry, preferences):
    if not isinstance(entry, str) or not ENTRY.fullmatch(entry):
        return None
    desktop = entry.removesuffix('.desktop') + '.desktop'
    for activity, value in preferences.items():
        if value.get('route') and ['app', desktop] in value.get('actions', []):
            return identifier(activity)
    return None


def route_notification(entry):
    activity = notification_activity(entry, settings())
    if activity is not None:
        activate(activity)


def button(label, icon, handler):
    control = QPushButton(QIcon.fromTheme(icon), label)
    control.clicked.connect(handler)
    control.setAutoDefault(False)
    return control


class Workspaces(QDialog):
    def __init__(self):
        super().__init__()
        self.api = interface()
        self.actions = []
        self.setWindowTitle('Espaços de trabalho')
        self.setWindowIcon(QIcon.fromTheme('activities'))
        self.resize(750, 550)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(plain_label('Use um espaço do Plasma para reunir os recursos de uma tarefa.'))
        row = QHBoxLayout()
        self.activities = QComboBox()
        self.activities.setAccessibleName('Espaço de trabalho')
        self.activities.currentIndexChanged.connect(self.read_activity)
        row.addWidget(self.activities, 1)
        row.addWidget(button('Novo espaço…', 'list-add', self.create))
        row.addWidget(button('Ativar', 'go-next', self.switch))
        layout.addLayout(row)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setMaxLength(80)
        form.addRow('&Nome', self.name)
        self.wallpaper = QLineEdit()
        self.wallpaper.setReadOnly(True)
        chooser = QHBoxLayout()
        chooser.addWidget(self.wallpaper, 1)
        chooser.addWidget(button('Escolher…', 'image-x-generic', self.select_wallpaper))
        chooser.addWidget(button('Limpar', 'edit-clear', self.wallpaper.clear))
        form.addRow('&Papel de parede', chooser)
        layout.addLayout(form)
        self.items = QListWidget()
        self.items.setAccessibleName('Atalhos e aplicativos sugeridos')
        layout.addWidget(self.items, 1)
        controls = QHBoxLayout()
        for title, icon, handler in (('Pasta…', 'folder-open', self.folder),
                ('Link…', 'insert-link', self.url), ('Aplicativo…', 'application-x-executable', self.application),
                ('Remover item', 'edit-delete', self.remove)):
            controls.addWidget(button(title, icon, handler))
        controls.addStretch()
        layout.addLayout(controls)
        self.routes = QCheckBox('Abrir ações de notificações destes aplicativos neste espaço')
        layout.addWidget(self.routes)
        self.status = plain_label('')
        layout.addWidget(self.status)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(button('Salvar espaço', 'document-save', self.store))
        bottom.addWidget(button('Ativar e abrir atalhos', 'media-playback-start', self.open_actions))
        bottom.addWidget(button('Fechar', 'window-close', self.reject))
        layout.addLayout(bottom)
        self.setEnabled(True)
        self.refresh(str(self.api.CurrentActivity(timeout=4)))

    def refresh(self, selected=''):
        self.activities.blockSignals(True)
        self.activities.clear()
        for value in self.api.ListActivities(timeout=4):
            activity = str(value)
            self.activities.addItem(str(self.api.ActivityName(activity, timeout=4)), activity)
        self.activities.setCurrentIndex(max(0, self.activities.findData(selected)))
        self.activities.blockSignals(False)
        self.read_activity()

    def read_activity(self):
        activity = self.activities.currentData()
        if not activity:
            return
        value = settings().get(activity, {})
        self.name.setText(value.get('name', self.activities.currentText()))
        self.wallpaper.setText(value.get('wallpaper', ''))
        self.actions = value.get('actions', [])
        self.routes.setChecked(bool(value.get('route')))
        self.render()

    def render(self):
        self.items.clear()
        labels = {'app': 'Aplicativo', 'folder': 'Pasta', 'url': 'Endereço'}
        for kind, value in self.actions:
            self.items.addItem(f'{labels[kind]} · {value}')

    def create(self):
        name, ok = QInputDialog.getText(self, 'Novo espaço de trabalho', 'Nome')
        if not ok:
            return
        try:
            value = validate(name, '', [], False)
            activity = str(self.api.AddActivity(value['name'], timeout=8))
            save(activity, value)
            self.refresh(activity)
            self.status.setText('Espaço criado. Escolha os recursos desta tarefa.')
        except (OSError, ValueError, dbus.DBusException) as error:
            self.status.setText(str(error))

    def store(self):
        activity = self.activities.currentData()
        if not activity:
            return
        try:
            value = validate(self.name.text(), self.wallpaper.text(), self.actions, self.routes.isChecked())
            self.api.SetActivityName(activity, value['name'], timeout=5)
            set_wallpaper(activity, value['wallpaper'])
            save(activity, value)
            self.refresh(activity)
            self.status.setText('Espaço salvo no Plasma.')
        except (OSError, ValueError, dbus.DBusException) as error:
            self.status.setText(str(error))

    def switch(self):
        try:
            activate(self.activities.currentData(), self.api)
            self.status.setText('Espaço de trabalho ativo.')
            return True
        except (ValueError, dbus.DBusException) as error:
            self.status.setText(str(error))
            return False

    def open_actions(self):
        if self.switch():
            value = settings().get(self.activities.currentData(), {})
            errors = quick_commands.execute(value) if value.get('actions') else []
            self.status.setText('\n'.join(errors) if errors else 'Os recursos salvos foram abertos.')

    def select_wallpaper(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Papel de parede', str(Path.home()), 'Imagens (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.wallpaper.setText(path)

    def add(self, kind, target):
        try:
            action = list(quick_commands.checked_action((kind, target)))
            if action in self.actions:
                return
            if len(self.actions) >= 20:
                raise ValueError('Inclua até 20 recursos no espaço de trabalho.')
            self.actions.append(action)
            self.render()
        except ValueError as error:
            self.status.setText(str(error))

    def folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Adicionar pasta', str(Path.home()))
        if path:
            self.add('folder', path)

    def url(self):
        target, ok = QInputDialog.getText(self, 'Adicionar endereço', 'Endereço HTTPS ou HTTP')
        if ok:
            self.add('url', target.strip())

    def application(self):
        items = {f'{name} · {key}': key for key, name in quick_commands.apps().items()}
        selected, ok = QInputDialog.getItem(self, 'Adicionar aplicativo', 'Aplicativo', sorted(items), 0, False)
        if ok and selected:
            self.add('app', items[selected])

    def remove(self):
        row = self.items.currentRow()
        if row >= 0:
            self.actions.pop(row)
            self.render()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--notification', metavar='APLICATIVO')
    args = parser.parse_args()
    if args.notification is not None:
        try:
            route_notification(args.notification)
        except (ValueError, OSError, dbus.DBusException):
            return 1
        return 0
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-workspaces')
    app.setStyleSheet(BUTTONS)
    try:
        Workspaces().exec()
        return 0
    except (OSError, ValueError, dbus.DBusException) as error:
        message(None, 'Espaços de trabalho', str(error), warning=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
