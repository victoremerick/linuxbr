"""Familiar Run dialog: fixed Windows aliases, URLs and explicit argv, no shell."""
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from PyQt6.QtCore import QProcess, QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                            QHBoxLayout, QLabel, QPushButton, QVBoxLayout)


ALIASES = {
    'control': ['linuxbr-system'],
    'appwiz.cpl': ['plasma-discover', '--mode', 'Installed'],
    'calc': ['kcalc'],
    'notepad': ['kate'],
    'mspaint': ['kolourpaint'],
    'write': ['libreoffice', '--writer'],
    'cmd': ['konsole'],
    'explorer': ['dolphin', 'linuxbr:/'],
    'taskmgr': ['linuxbr-task-manager'],
    'winver': ['linuxbr-system', '--page', 'Sistema'],
    'devmgmt.msc': ['linuxbr-system', '--page', 'Dispositivos'],
    'diskmgmt.msc': ['linuxbr-system', '--page', 'Armazenamento'],
    'ncpa.cpl': ['linuxbr-system', '--page', 'Endereços IP e DNS'],
    'mmsys.cpl': ['linuxbr-system', '--page', 'Áudio'],
    'powercfg.cpl': ['linuxbr-system', '--page', 'Energia e bateria'],
    'timedate.cpl': ['kcmshell6', 'kcm_clock'],
    'intl.cpl': ['kcmshell6', 'kcm_regionandlang'],
    'main.cpl': ['kcmshell6', 'kcm_mouse'],
    'desk.cpl': ['linuxbr-system', '--page', 'Telas'],
    'firewall.cpl': ['linuxbr-system', '--page', 'Firewall'],
    'netplwiz': ['linuxbr-system', '--page', 'Usuários'],
    'msconfig': ['kcmshell6', 'kcm_autostart'],
    'shell:startup': ['kcmshell6', 'kcm_autostart'],
    'shell:appsfolder': ['linuxbr-store'],
    'ms-settings:': ['linuxbr-system'],
    'ms-settings:windowsupdate': ['plasma-discover', '--mode', 'Update'],
    'ms-settings:appsfeatures': ['plasma-discover', '--mode', 'Installed'],
    'ms-settings:display': ['linuxbr-system', '--page', 'Telas'],
    'ms-settings:sound': ['linuxbr-system', '--page', 'Áudio'],
    'ms-settings:network': ['linuxbr-system', '--page', 'Rede'],
    'ms-settings:personalization': ['linuxbr-system', '--page', 'Personalização'],
    'ms-settings:bluetooth': ['kcmshell6', 'kcm_bluetooth'],
    'ms-settings:printers': ['kcmshell6', 'kcm_printer_manager'],
    'ms-settings:defaultapps': ['kcmshell6', 'kcm_componentchooser'],
}


def start(command):
    if not shutil.which(command[0]):
        raise ValueError('O aplicativo não está instalado: ' + command[0] + '. Procure-o na Loja Linux BR.')
    if not QProcess.startDetached(command[0], command[1:])[0]:
        raise ValueError('Não foi possível iniciar o aplicativo.')


def open_url(url):
    if not url.isValid() or url.isEmpty():
        raise ValueError('O endereço ou caminho informado é inválido.')
    if not QDesktopServices.openUrl(url):
        raise ValueError('Não foi possível abrir este endereço ou arquivo.')


def expand_path(value):
    # Only documented, local aliases. Never evaluate shell substitutions.
    variables = {
        'USERPROFILE': str(Path.home()), 'HOME': str(Path.home()),
        'TEMP': tempfile.gettempdir(), 'TMP': tempfile.gettempdir(),
        'APPDATA': os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')),
        'LOCALAPPDATA': os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')),
    }
    value = re.sub(r'%([A-Za-z]+)%', lambda m: variables.get(m[1].upper(), m[0]), value)
    return os.path.expanduser(value)


def open_value(raw):
    value = raw.strip()
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError('Digite um aplicativo, caminho ou endereço válido.')
    alias = value.casefold()
    if alias in ALIASES:
        start(ALIASES[alias]); return
    special = {
        'shell:desktop': QStandardPaths.StandardLocation.DesktopLocation,
        'shell:personal': QStandardPaths.StandardLocation.DocumentsLocation,
        'shell:downloads': QStandardPaths.StandardLocation.DownloadLocation,
        'shell:mypictures': QStandardPaths.StandardLocation.PicturesLocation,
        'shell:mymusic': QStandardPaths.StandardLocation.MusicLocation,
        'shell:myvideo': QStandardPaths.StandardLocation.MoviesLocation,
    }
    if alias in special:
        path = QStandardPaths.writableLocation(special[alias])
        if not path or not Path(path).is_dir():
            raise ValueError('Esta pasta pessoal ainda não existe.')
        open_url(QUrl.fromLocalFile(path)); return
    # Accept a whole quoted path before tokenizing commands; spaces are common.
    if (len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'")
            and value[0] not in value[1:-1]):
        value = value[1:-1]
    value = expand_path(value)
    # Familiar bare .exe aliases apply only when there is no real file with that
    # name in the current directory. Explicit paths always keep Windows handling.
    exe_aliases = {'calc', 'notepad', 'mspaint', 'explorer', 'cmd', 'taskmgr', 'winver', 'write'}
    exe_name = value.casefold()
    if (exe_name.endswith('.exe') and exe_name[:-4] in exe_aliases
            and not Path(value).is_file()):
        start(ALIASES[exe_name[:-4]]); return
    if Path(value).exists():
        path = Path(value).resolve()
        if path.suffix.casefold() in ('.exe', '.msi') and path.is_file():
            start(['linuxbr-windows', str(path)])
        else:
            open_url(QUrl.fromLocalFile(str(path)))
        return
    if value.startswith('\\\\'):
        from sys import path as module_paths
        if '/usr/lib/linuxbr-drive-manager' not in module_paths:
            module_paths.insert(0, '/usr/lib/linuxbr-drive-manager')
        from core import smb_url
        open_url(QUrl(smb_url(value))); return
    # Letters refer to the same Linux BR drive service used by Dolphin.
    match = re.fullmatch(r'([C-Zc-z]):[\\/]?', value)
    if match:
        start(['dolphin', 'linuxbr:/' + match[1].upper()]); return
    if re.match(r'^[A-Za-z]:[\\/]', value):
        raise ValueError('Para abrir uma unidade, digite a letra (por exemplo, D:). '
                         'Para um arquivo, use Procurar ou seu caminho Linux.')
    parsed = urlsplit(value)
    if parsed.scheme in ('https', 'http', 'smb', 'file', 'linuxbr'):
        if parsed.scheme in ('https', 'http', 'smb') and not parsed.hostname:
            raise ValueError('O endereço precisa conter o nome do site ou servidor.')
        if parsed.username is not None or parsed.password is not None:
            raise ValueError('Não inclua usuário nem senha no endereço.')
        open_url(QUrl(value)); return
    if value.startswith('www.') and ' ' not in value:
        url = QUrl('https://' + value)
        if not url.host() or url.userInfo():
            raise ValueError('Digite um site válido, sem usuário nem senha no endereço.')
        open_url(url); return
    if parsed.scheme:
        raise ValueError('Endereço não reconhecido. Para sites, use https://.')
    try:
        parts = shlex.split(value)
    except ValueError as error:
        raise ValueError('Confira as aspas do comando.') from error
    if not parts:
        raise ValueError('Digite o nome de um programa.')
    if any(token in ('|', '||', '&', '&&', ';', '>', '>>', '<') for token in parts):
        raise ValueError('Abra cmd ou konsole para usar comandos com redirecionamento ou encadeamento.')
    # Aliases with arguments are restricted to applications which accept files.
    executable_aliases = {'notepad': 'kate', 'calc': 'kcalc', 'cmd': 'konsole',
                          'explorer': 'dolphin', 'mspaint': 'kolourpaint'}
    parts[0] = executable_aliases.get(parts[0].casefold(), parts[0])
    if Path(parts[0]).suffix.casefold() in ('.exe', '.msi'):
        if len(parts) != 1:
            raise ValueError('Selecione o programa Windows sem argumentos; o gerenciador abrirá as opções de execução.')
        start(['linuxbr-windows', str(Path(parts[0]).resolve())]); return
    start(parts)


class RunDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Executar — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('system-run'))
        self.setMinimumWidth(510)
        body = QVBoxLayout(self)
        heading = QLabel('Digite o nome de um programa, pasta, documento ou site.')
        heading.setWordWrap(True); body.addWidget(heading)
        row = QHBoxLayout(); label = QLabel('&Abrir:'); row.addWidget(label)
        self.entry = QComboBox(); self.entry.setEditable(True)
        self.entry.addItems(['', 'control', 'explorer', 'notepad', 'calc', 'cmd', 'taskmgr',
                             'appwiz.cpl', 'winver', '%USERPROFILE%', 'shell:downloads'])
        self.entry.setAccessibleName('Programa, caminho ou endereço')
        self.entry.lineEdit().setPlaceholderText('Ex.: notepad, D:, https://…')
        self.entry.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        label.setBuddy(self.entry); row.addWidget(self.entry, 1); body.addLayout(row)
        hint = QLabel('Nomes familiares do Windows abrem as ferramentas equivalentes do Linux BR.')
        hint.setWordWrap(True); body.addWidget(hint)
        self.error = QLabel(); self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True); self.error.hide(); body.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Abrir')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        browse = buttons.addButton('Procurar…', QDialogButtonBox.ButtonRole.ActionRole)
        browse.clicked.connect(self.browse)
        buttons.accepted.connect(self.open); buttons.rejected.connect(self.reject); body.addWidget(buttons)
        self.entry.setFocus()
        # Deliberately no command history: typed URLs may contain private tokens.

    def browse(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Escolher arquivo', str(Path.home()))
        if filename:
            self.entry.setEditText(filename)

    def open(self):
        try:
            open_value(self.entry.currentText())
        except (OSError, ValueError) as error:
            self.error.setText(str(error)); self.error.show(); self.entry.setFocus(); return
        self.accept()


def run_dialog():
    RunDialog().exec()
