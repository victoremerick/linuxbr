"""Familiar file actions using desktop links and the existing drive service."""
import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PyQt6.QtCore import QStandardPaths, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)
from visual_style import BUTTONS


def plain_label(text, parent=None):
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def message(parent, title, text, warning=False):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Information)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def desktop_value(text):
    """Escape a string value, never an executable command or shell expression."""
    return text.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


def desktop_folder():
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    return Path(path) if path else Path.home() / 'Área de trabalho'


def network_api():
    location = '/usr/lib/linuxbr-drive-manager'
    if location not in sys.path:
        sys.path.insert(0, location)
    from client import ServiceStore
    from core import smb_url
    return ServiceStore, smb_url


def network_connector(parent):
    network_api()
    from network_access import NetworkAccess
    return NetworkAccess(parent)


def validated_target(text):
    """Return a normalized link URL and friendly suggestion without opening it."""
    text = text.strip()
    if not text or len(text) > 8192 or any(ord(char) < 32 for char in text):
        raise ValueError('Informe um arquivo, uma pasta ou um endereço válido.')
    if text.startswith('\\\\') or text.lower().startswith('smb://'):
        _store, smb_url = network_api()
        value = smb_url(text)
        return value, unquote(urlsplit(value).path.rstrip('/').rsplit('/', 1)[-1]), 'folder-network'
    if re.match(r'^[A-Za-z]:[\\/]', text):
        raise ValueError('Escolha a unidade em Este computador para localizar esse arquivo no Linux BR.')
    if text.startswith(('/', '~')):
        path = Path(text).expanduser().absolute()
        if not path.exists():
            raise ValueError('Este arquivo ou pasta não existe. Escolha um local disponível.')
        return path.as_uri(), path.name or 'Sistema', 'folder' if path.is_dir() else 'text-x-generic'
    url = QUrl(text, QUrl.ParsingMode.StrictMode)
    if not url.isValid():
        raise ValueError('O endereço informado é inválido.')
    if url.scheme().lower() == 'file':
        if url.host() and url.host().lower() != 'localhost':
            raise ValueError('Para uma pasta de rede, use \\\\servidor\\pasta ou smb://servidor/pasta.')
        return validated_target(url.toLocalFile())
    if url.scheme().lower() == 'linuxbr':
        parts = [part for part in url.path().split('/') if part]
        if (url.host() or url.query() or url.fragment() or '..' in parts or '.' in parts
                or any(ord(char) < 32 for char in url.path())
                or (parts and not re.fullmatch(r'[C-Z]', parts[0]))):
            raise ValueError('Selecione um local válido em Este computador.')
        name = ('Este computador' if not parts else 'Unidade ' + parts[0]
                if len(parts) == 1 else parts[-1])
        return url.toString(QUrl.ComponentFormattingOption.FullyEncoded), name, 'drive-harddisk'
    if url.scheme().lower() not in ('http', 'https') or not url.host() or url.userInfo():
        raise ValueError('Use um endereço http:// ou https:// sem usuário e senha, ou escolha um arquivo ou pasta.')
    return url.toString(QUrl.ComponentFormattingOption.FullyEncoded), url.host(), 'internet-web-browser'


def write_shortcut(target, name, folder):
    url, _suggestion, icon = validated_target(target)
    name = name.strip()
    if (not name or len(name) > 100 or name in ('.', '..') or name.startswith('.')
            or any(char in name for char in '/\\<>:"|?*')
            or any(ord(char) < 32 for char in name)):
        raise ValueError('Escolha um nome de até 100 caracteres, sem barras, dois-pontos ou caracteres especiais de arquivo.')
    destination = Path(folder).expanduser()
    if not destination.is_absolute() or not destination.is_dir():
        raise ValueError('Escolha uma pasta existente para salvar o atalho.')
    filename = name[:-8] if name.lower().endswith('.desktop') else name
    if not filename:
        raise ValueError('Informe um nome para o atalho.')
    content = ('[Desktop Entry]\nType=Link\nVersion=1.5\n'
               + 'Name=' + desktop_value(name) + '\n'
               + 'URL=' + desktop_value(url) + '\nIcon=' + icon + '\n')
    for number in range(1, 1001):
        suffix = '' if number == 1 else f' ({number})'
        path = destination / (filename + suffix + '.desktop')
        try:
            # O_EXCL also refuses existing symlinks. Existing documents are never overwritten.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
        except OSError:
            path.unlink(missing_ok=True)
            raise
        return path
    raise ValueError('Já existem muitos atalhos com esse nome. Escolha outro nome.')


class ShortcutDialog(QDialog):
    def __init__(self, target='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Criar atalho — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('emblem-symbolic-link'))
        self.resize(640, 340)
        layout = QVBoxLayout(self)
        heading = plain_label('Onde está o item?')
        heading.setStyleSheet('font-size:24px;font-weight:600')
        layout.addWidget(heading)
        layout.addWidget(plain_label('Crie um atalho para abrir um arquivo, uma pasta, uma unidade de rede ou um site. O item original permanece no lugar.'))
        form = QFormLayout()
        self.target = QLineEdit(target)
        self.target.setPlaceholderText('Arquivo, pasta, https://site.com ou \\\\servidor\\pasta')
        self.target.setMaxLength(8192)
        form.addRow('Local do item:', self.target)
        browse = QHBoxLayout()
        for title, action in [('Escolher arquivo…', self.select_file), ('Escolher pasta…', self.select_folder)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            browse.addWidget(button)
        form.addRow('', browse)
        self.name = QLineEdit()
        self.name.setMaxLength(100)
        form.addRow('Nome do atalho:', self.name)
        row = QHBoxLayout()
        self.folder = QLineEdit(str(desktop_folder()))
        row.addWidget(self.folder)
        choose = QPushButton('Alterar…')
        choose.clicked.connect(self.select_destination)
        row.addWidget(choose)
        form.addRow('Salvar em:', row)
        layout.addLayout(form)
        self.error = plain_label('')
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        create = self.buttons.addButton('Criar atalho', QDialogButtonBox.ButtonRole.AcceptRole)
        create.setProperty('primary', True)
        self.buttons.accepted.connect(self.create)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.target.editingFinished.connect(self.suggest_name)
        self.suggest_name()

    def suggest_name(self):
        if self.name.text().strip():
            return
        try:
            _url, name, _icon = validated_target(self.target.text())
            self.name.setText(re.sub(r'[/\\<>:"|?*]', ' ', name).strip('.')[:100])
        except (ValueError, OSError, ImportError):
            pass

    def select_file(self):
        path, _filter = QFileDialog.getOpenFileName(self, 'Escolher arquivo', str(Path.home()))
        if path:
            self.target.setText(path)
            self.suggest_name()

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Escolher pasta', str(Path.home()))
        if path:
            self.target.setText(path)
            self.suggest_name()

    def select_destination(self):
        path = QFileDialog.getExistingDirectory(self, 'Salvar atalho em', self.folder.text())
        if path:
            self.folder.setText(path)

    def create(self):
        try:
            destination = Path(self.folder.text()).expanduser()
            # Create only the standard personal Desktop, if not already initialized by XDG.
            if destination == desktop_folder() and not destination.exists():
                destination.mkdir(mode=0o700, parents=True)
            result = write_shortcut(self.target.text(), self.name.text(), str(destination))
        except (ValueError, OSError, ImportError) as error:
            self.error.setText(str(error))
            return
        message(self, 'Atalho criado', 'O atalho foi salvo em:\n' + str(result))
        self.accept()


def readable_location(value):
    if any(ord(char) < 32 for char in value):
        raise ValueError('Um dos caminhos contém caracteres de controle e não pode ser copiado como texto.')
    url = QUrl(value)
    if url.isLocalFile():
        location = url.toLocalFile()
        if any(ord(char) < 32 for char in location):
            raise ValueError('Um dos caminhos contém caracteres de controle e não pode ser copiado como texto.')
        return location
    if not url.scheme():
        return str(Path(value).expanduser().absolute())
    # A URL containing authentication can come from an external file manager.
    # Never copy credentials along with a location.
    url.setUserInfo('')
    return url.toDisplayString()


def windows_network_location(value):
    url = QUrl(value)
    if url.scheme().lower() != 'smb' or not url.host() or ':' in url.host() or url.port() != -1:
        return readable_location(value)
    decoded = url.path()
    if any(ord(char) < 32 for char in decoded):
        raise ValueError('Um dos caminhos de rede contém caracteres de controle.')
    return '\\\\' + url.host() + decoded.replace('/', '\\')


class CopyPathsDialog(QDialog):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Copiar caminho — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('edit-copy'))
        self.resize(650, 300)
        self.values = values
        layout = QVBoxLayout(self)
        layout.addWidget(plain_label('Os caminhos abaixo foram copiados. Use Ctrl+V para colá-los em uma mensagem ou documento.'))
        self.text = QPlainTextEdit('\n'.join(readable_location(value) for value in values))
        self.text.setReadOnly(True)
        self.text.setAccessibleName('Caminhos dos itens selecionados')
        layout.addWidget(self.text)
        if any(QUrl(value).scheme().lower() == 'smb' for value in values):
            windows = QCheckBox('Usar formato Windows nos caminhos de rede (\\\\servidor\\pasta)')
            windows.toggled.connect(self.change_format)
            layout.addWidget(windows)
        layout.addWidget(plain_label('Copiar o caminho não envia os arquivos. Outras pessoas precisam ter acesso ao mesmo local.'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('Fechar')
        copy = buttons.addButton('Copiar novamente', QDialogButtonBox.ButtonRole.ActionRole)
        copy.clicked.connect(self.copy)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.copy()

    def copy(self):
        QApplication.clipboard().setText(self.text.toPlainText())

    def change_format(self, windows):
        try:
            formatter = windows_network_location if windows else readable_location
            value = '\n'.join(formatter(item) for item in self.values)
        except ValueError as error:
            message(self, 'Caminho não disponível', str(error), warning=True)
            return
        self.text.setPlainText(value)
        self.copy()


class MapNetworkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Mapear unidade de rede — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('folder-network'))
        self.resize(640, 350)
        self.connection = network_connector(self)
        self.connection.finished.connect(self.network_finished)
        layout = QVBoxLayout(self)
        heading = plain_label('Adicionar uma pasta compartilhada')
        heading.setStyleSheet('font-size:23px;font-weight:600')
        layout.addWidget(heading)
        layout.addWidget(plain_label('A pasta aparecerá em Este computador e no Explorador de arquivos com uma letra de unidade. O endereço ficará salvo para os próximos acessos.'))
        form = QFormLayout()
        self.location = QLineEdit()
        self.location.setMaxLength(2048)
        self.location.setPlaceholderText('\\\\servidor\\compartilhamento')
        form.addRow('Pasta de rede:', self.location)
        self.name = QLineEdit()
        self.name.setMaxLength(80)
        self.name.setPlaceholderText('Ex.: Documentos do escritório')
        form.addRow('Nome para exibição:', self.name)
        layout.addLayout(form)
        layout.addWidget(plain_label('Também aceita smb://servidor/compartilhamento. O sistema solicita a conta ao conectar. Para lembrar a senha, use a opção de salvar no Cofre de senhas do KDE quando oferecida. A senha não faz parte do endereço nem do cadastro da unidade. A letra pode ser alterada em Gerenciamento de discos.'))
        self.open_now = QCheckBox('Abrir a pasta após adicionar')
        self.open_now.setChecked(True)
        layout.addWidget(self.open_now)
        self.error = plain_label('')
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        self.map_button = buttons.addButton('Adicionar unidade', QDialogButtonBox.ButtonRole.AcceptRole)
        self.map_button.setProperty('primary', True)
        buttons.accepted.connect(self.map_share)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def map_share(self):
        if self.connection.busy:
            return
        try:
            store_type, smb_url = network_api()
            url = smb_url(self.location.text())
            name = self.name.text().strip() or unquote(urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1])
            if any(ord(char) < 32 for char in name):
                raise ValueError('Use um nome sem quebras de linha ou caracteres de controle.')
            self.map_button.setEnabled(False)
            data = store_type().add_share(url, name)
            letter = data.get('letters', {}).get('smb:' + url)
        except (ValueError, OSError, ImportError) as error:
            self.map_button.setEnabled(True)
            self.error.setText('Não foi possível adicionar a unidade. ' + str(error))
            return
        if self.open_now.isChecked():
            try:
                self.connection.start(url)
            except ValueError as error:
                self.map_button.setEnabled(True)
                self.error.setText('A unidade foi salva. ' + str(error))
                return
            self.error.setText('Unidade salva. Conectando… Informe a conta na janela do sistema, se solicitado.')
            return
        else:
            label = name + (f' ({letter}:)' if letter else '')
            message(self, 'Unidade adicionada', label + ' aparecerá em Este computador.')
        self.accept()

    def network_finished(self, url, success, text):
        self.map_button.setEnabled(True)
        if success:
            if not QDesktopServices.openUrl(QUrl(url)):
                message(self, 'Unidade adicionada', 'O acesso foi confirmado. Abra Este computador para acessar a unidade.')
            self.accept()
        else:
            self.error.setText('A unidade já está salva. ' + text)
            self.map_button.setText('Reconectar')

    def reject(self):
        self.connection.cancel()
        super().reject()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Arquivos e atalhos — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('system-file-manager'))
        self.resize(700, 540)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        heading = plain_label('Arquivos e atalhos')
        heading.setStyleSheet('font-size:27px;font-weight:600')
        layout.addWidget(heading)
        layout.addWidget(plain_label('Seus arquivos, pastas e locais de rede, com ações familiares.'))
        for title, detail, action in [
                ('Criar atalho…', 'Coloque um arquivo, uma pasta ou um site na área de trabalho.', self.shortcut),
                ('Mapear unidade de rede…', 'Acesse pastas compartilhadas de computadores Windows ou servidores.', self.map_network),
                ('Este computador', 'Abra discos, pendrives, unidades de rede e pastas pessoais.', self.computer),
                ('Lixeira', 'Consulte itens removidos e use Restaurar para recuperá-los.', self.trash)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            layout.addWidget(button)
            layout.addWidget(plain_label(detail))
        layout.addSpacing(12)
        layout.addWidget(plain_label('No Explorador: clique com o botão direito para Criar atalho ou Copiar caminho. Em uma pasta, use Criar novo para começar um documento de texto ou uma lista.'))
        layout.addWidget(plain_label('Atalhos úteis: F2 renomeia • Ctrl+C copia • Ctrl+X recorta • Ctrl+V cola • Ctrl+Z desfaz • Ctrl+L mostra o endereço • Alt+↑ abre a pasta anterior na hierarquia.'))
        layout.addStretch()

    def shortcut(self):
        ShortcutDialog(parent=self).exec()

    def map_network(self):
        MapNetworkDialog(self).exec()

    def computer(self):
        QDesktopServices.openUrl(QUrl('linuxbr:/'))

    def trash(self):
        QDesktopServices.openUrl(QUrl('trash:/'))


def main():
    parser = argparse.ArgumentParser(description='Arquivos e atalhos do Linux BR')
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--shortcut', metavar='ITEM', nargs='?', const='')
    options.add_argument('--copy-path', metavar='ITEM', nargs='+')
    options.add_argument('--map-network', action='store_true')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName('Arquivos e atalhos')
    app.setDesktopFileName('linuxbr-file-tools')
    app.setStyleSheet(BUTTONS)
    if os.geteuid() == 0:
        message(None, 'Conta pessoal necessária', 'Abra esta ferramenta pela sua conta de usuário, sem sudo.', warning=True)
        return 1
    try:
        if args.shortcut is not None:
            ShortcutDialog(args.shortcut).exec()
            return 0
        if args.copy_path:
            CopyPathsDialog(args.copy_path).exec()
            return 0
        if args.map_network:
            MapNetworkDialog().exec()
            return 0
        window = Window()
        window.show()
        return app.exec()
    except (ValueError, OSError, ImportError) as error:
        message(None, 'Ação não concluída', str(error), warning=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
