"""Create user-owned Start-menu actions with typed destinations."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout)

from file_tools import desktop_value, message, plain_label
from visual_style import BUTTONS


APP_ID = re.compile(r'[A-Za-z0-9_.+-]+\.desktop\Z')
APP_PREFIX = 'linuxbr-quick-action-'


def data():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))


def checked_identifier(identifier):
    if str(UUID(identifier)) != identifier:
        raise ValueError('Identificador de comando inválido.')
    return identifier


def record_path(identifier):
    return data() / 'linuxbr/quick-commands' / (checked_identifier(identifier) + '.json')


def launcher_path(identifier):
    return data() / 'applications' / (APP_PREFIX + checked_identifier(identifier) + '.desktop')


def checked_action(action):
    kind, target = action
    if not isinstance(target, str) or not target or len(target) > 4096 or not all(c.isprintable() for c in target):
        raise ValueError('O destino da ação não é válido.')
    if kind == 'folder' and Path(target).is_absolute():
        return kind, target
    if kind == 'url':
        url = urlsplit(target)
        if url.scheme in {'https', 'http'} and url.hostname and not url.username and not url.password and '\\' not in target:
            return kind, target
    if kind == 'app' and APP_ID.fullmatch(target) and not target.startswith(APP_PREFIX):
        return kind, target
    raise ValueError('Escolha uma pasta, link HTTP(S) ou aplicativo instalado.')


def checked_command(name, actions):
    name = name.strip()
    if not name or len(name) > 80 or not all(c.isprintable() for c in name):
        raise ValueError('Informe um nome com até 80 caracteres.')
    if not actions or len(actions) > 20:
        raise ValueError('Inclua entre uma e 20 ações.')
    return {'name': name, 'actions': [list(checked_action(action)) for action in actions]}


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix='.linuxbr-quick-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load(identifier):
    raw = json.loads(record_path(identifier).read_text(encoding='utf-8'))
    return checked_command(raw['name'], raw['actions'])


def save(identifier, name, actions):
    identifier = checked_identifier(identifier) if identifier else str(uuid4())
    record = checked_command(name, actions)
    path = record_path(identifier)
    previous = path.read_text(encoding='utf-8') if path.is_file() else None
    atomic_write(path, json.dumps(record, ensure_ascii=False))
    try:
        launcher = ('[Desktop Entry]\nType=Application\n'
                    f'Name={desktop_value(record["name"])}\n'
                    'Comment=Comando rápido do Linux BR\n'
                    f'Exec=/usr/bin/linuxbr-quick-commands --run {identifier}\n'
                    'Icon=system-run\nTerminal=false\nCategories=Utility;\nStartupNotify=false\n')
        atomic_write(launcher_path(identifier), launcher)
    except OSError:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, previous)
        raise
    return identifier


def apps():
    from gi.repository import Gio
    out = {}
    for app in Gio.AppInfo.get_all():
        identifier = app.get_id() or ''
        if app.should_show() and APP_ID.fullmatch(identifier) and not identifier.startswith(APP_PREFIX):
            out[identifier] = app.get_display_name()
    return out


def execute(command):
    from gi.repository import Gio
    errors = []
    for kind, target in command['actions']:
        try:
            if kind == 'folder':
                if not Path(target).is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(target)):
                    raise ValueError('O local está indisponível.')
            elif kind == 'url':
                parsed = QUrl(target, QUrl.ParsingMode.StrictMode)
                if not parsed.isValid() or not QDesktopServices.openUrl(parsed):
                    raise ValueError('Não foi possível abrir o endereço.')
            else:
                app = Gio.DesktopAppInfo.new(target)
                if not app or not app.should_show() or not app.get_filename():
                    raise ValueError('Aplicativo indisponível.')
                subprocess.Popen(['/usr/bin/gio', 'launch', app.get_filename()], start_new_session=True)
        except (OSError, TypeError, ValueError) as error:
            errors.append(f'{target}\n{error}')
    return errors


def button(text, icon, callback):
    value = QPushButton(QIcon.fromTheme(icon), text)
    value.setAutoDefault(False)
    value.clicked.connect(callback)
    return value


class QuickCommands(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Comandos rápidos')
        self.setWindowIcon(QIcon.fromTheme('system-run'))
        self.resize(810, 530)
        self.identifier = None
        self.actions = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(plain_label('Dê um nome ao conjunto e escolha o que deve abrir ao encontrá-lo no menu Iniciar.'))
        columns = QHBoxLayout()
        self.commands = QListWidget()
        self.commands.setAccessibleName('Comandos salvos')
        self.commands.currentItemChanged.connect(self.select)
        columns.addWidget(self.commands, 1)
        edit = QVBoxLayout()
        fields = QFormLayout()
        self.name = QLineEdit()
        self.name.setMaxLength(80)
        fields.addRow('&Nome', self.name)
        edit.addLayout(fields)
        self.steps = QListWidget()
        self.steps.setAccessibleName('Ações do comando')
        edit.addWidget(self.steps, 1)
        add = QHBoxLayout()
        for label, icon, callback in (
                ('Adicionar pasta…', 'folder', self.add_folder),
                ('Adicionar link…', 'insert-link', self.add_url),
                ('Adicionar aplicativo…', 'application-x-executable', self.add_app)):
            add.addWidget(button(label, icon, callback))
        edit.addLayout(add)
        edit.addWidget(button('Remover ação selecionada', 'edit-delete', self.drop_action))
        columns.addLayout(edit, 2)
        layout.addLayout(columns, 1)
        self.status = plain_label('')
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        for label, icon, callback in (
                ('Novo', 'document-new', self.clear),
                ('Salvar no menu Iniciar', 'document-save', self.save),
                ('Abrir agora', 'media-playback-start', self.run),
                ('Excluir comando', 'edit-delete', self.delete),
                ('Fechar', 'window-close', self.reject)):
            actions.addWidget(button(label, icon, callback))
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        self.commands.blockSignals(True)
        self.commands.clear()
        for path in (data() / 'linuxbr/quick-commands').glob('*.json'):
            try:
                record = load(path.stem)
            except (OSError, ValueError, KeyError, TypeError):
                continue
            self.commands.addItem(record['name'])
            self.commands.item(self.commands.count() - 1).setData(Qt.ItemDataRole.UserRole, path.stem)
        self.commands.sortItems()
        self.commands.blockSignals(False)

    def select(self, item, _previous):
        if item is None:
            return
        try:
            self.identifier = item.data(Qt.ItemDataRole.UserRole)
            record = load(self.identifier)
            self.actions = record['actions']
            self.name.setText(record['name'])
            self.render_steps()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.status.setText(str(error))

    def render_steps(self):
        labels = {'folder': 'Pasta', 'url': 'Link', 'app': 'Aplicativo'}
        self.steps.clear()
        for kind, target in self.actions:
            self.steps.addItem(f'{labels[kind]} · {target}')

    def add(self, kind, target):
        try:
            action = checked_action((kind, target))
            if len(self.actions) >= 20:
                raise ValueError('Cada comando pode conter até 20 ações.')
            self.actions.append(action)
            self.render_steps()
            self.steps.setCurrentRow(len(self.actions) - 1)
            self.status.clear()
        except ValueError as error:
            self.status.setText(str(error))

    def add_folder(self):
        selected = QFileDialog.getExistingDirectory(self, 'Escolher pasta', str(Path.home()))
        if selected:
            self.add('folder', selected)

    def add_url(self):
        value, ok = QInputDialog.getText(self, 'Adicionar link', 'Endereço completo')
        if ok:
            self.add('url', value.strip())

    def add_app(self):
        values = {f'{name} · {key}': key for key, name in apps().items()}
        value, ok = QInputDialog.getItem(self, 'Adicionar aplicativo', 'Aplicativo', sorted(values), 0, False)
        if ok and value:
            self.add('app', values[value])

    def drop_action(self):
        row = self.steps.currentRow()
        if row >= 0:
            self.actions.pop(row)
            self.render_steps()
            self.steps.setCurrentRow(min(row, len(self.actions) - 1))

    def clear(self):
        self.identifier = None
        self.actions = []
        self.commands.clearSelection()
        self.name.clear()
        self.render_steps()
        self.status.clear()
        self.name.setFocus()

    def save(self):
        try:
            self.identifier = save(self.identifier, self.name.text(), self.actions)
            self.refresh()
            self.status.setText('Comando salvo. Pesquise pelo nome no menu Iniciar.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def run(self):
        try:
            errors = execute(checked_command(self.name.text(), self.actions))
            self.status.setText('\n'.join(errors) if errors else 'Ações abertas.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def delete(self):
        if not self.identifier:
            return
        if QMessageBox.question(self, 'Excluir comando', 'Remover este comando do menu Iniciar?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        try:
            launcher_path(self.identifier).unlink(missing_ok=True)
            record_path(self.identifier).unlink(missing_ok=True)
            self.clear()
            self.refresh()
        except (OSError, ValueError) as error:
            self.status.setText(str(error))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', metavar='COMANDO')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-quick-commands')
    app.setStyleSheet(BUTTONS)
    if os.geteuid() == 0:
        message(None, 'Conta pessoal necessária', 'Abra Comandos rápidos pela sua conta de usuário.', warning=True)
        return 1
    if args.run is not None:
        try:
            errors = execute(load(args.run))
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors = [str(error)]
        if errors:
            message(None, 'Ações pendentes', '\n\n'.join(errors), warning=True)
            return 1
        # Allow desktop launch requests queued by the platform plugin to reach the session.
        app.processEvents()
        return 0
    QuickCommands().exec()
    return 0


if __name__ == '__main__':
    sys.exit(main())
