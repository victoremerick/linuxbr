"""Lock the current account's graphical session when its FIDO key is removed."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from store_sources import atomic_write


KEY = re.compile(r'[A-Za-z0-9_./:@+-]{1,320}')


def preferences():
    root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return root / 'linuxbr/key-lock.json'


def read():
    try:
        data = json.loads(preferences().read_text())
    except (OSError, ValueError):
        return ''
    target = data.get('key', '') if isinstance(data, dict) else ''
    return target if isinstance(target, str) and KEY.fullmatch(target) else ''


def command(*args):
    return subprocess.check_output(args, timeout=4, text=True, stderr=subprocess.DEVNULL)


def physical_keys():
    result = {}
    for path in sorted(Path('/sys/class/hidraw').glob('hidraw*'))[:48]:
        try:
            properties = dict(line.split('=', 1) for line in command(
                '/usr/bin/udevadm', 'info', '--query=property', '--path', str(path)).splitlines() if '=' in line)
        except (OSError, subprocess.SubprocessError):
            continue
        if properties.get('ID_FIDO_TOKEN') != '1':
            continue
        devpath = properties.get('DEVPATH', '').split('/hidraw/')[0]
        identity = properties.get('ID_PATH') or re.sub(r'\.[0-9A-Fa-f]+$', '', devpath)
        if not KEY.fullmatch(identity):
            continue
        name = ' '.join(filter(None, (properties.get('ID_VENDOR_FROM_DATABASE'),
                                      properties.get('ID_MODEL_FROM_DATABASE')))) or 'Chave de segurança FIDO'
        result[identity] = f'{name} · {path.name}'
    return result


def watch():
    target = ''
    seen = False
    missing = 0
    while True:
        configured = read()
        if configured != target:
            target, seen, missing = configured, False, 0
        if target and target in physical_keys():
            seen, missing = True, 0
        elif seen:
            missing += 1
            if missing >= 2:
                try:
                    command('/usr/bin/loginctl', 'lock-session', 'auto')
                except (OSError, subprocess.SubprocessError):
                    print('Não foi possível solicitar o bloqueio da sessão.', file=sys.stderr, flush=True)
                else:
                    seen, missing = False, 0
                    print('Sessão bloqueada após a remoção da chave FIDO.', flush=True)
        time.sleep(2 if target else 8)


def configure():
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                                 QLabel, QPushButton, QMessageBox, QVBoxLayout)
    from desktop_theme import initialize
    initialize()
    application = QApplication(sys.argv)
    dialog = QDialog()
    dialog.setWindowTitle('Bloqueio por chave de segurança')
    dialog.setWindowIcon(QIcon.fromTheme('security-high'))
    dialog.resize(575, 275)
    layout = QVBoxLayout(dialog)
    note = QLabel('Conecte uma chave FIDO e selecione a porta. Depois de detectar a chave, '
                  'o sistema bloqueia a sessão se ela for removida. Para voltar, use a autenticação configurada '
                  'na tela de bloqueio da sua conta.')
    note.setWordWrap(True)
    layout.addWidget(note)
    form = QFormLayout()
    choices = QComboBox()
    form.addRow('Chave e porta', choices)
    layout.addLayout(form)

    def reload():
        target = choices.currentData() or read()
        choices.clear()
        choices.addItem('Desativado', '')
        keys = physical_keys()
        if target and target not in keys:
            choices.addItem('Chave configurada · desconectada', target)
        for identity, label in keys.items():
            choices.addItem(label, identity)
        choices.setCurrentIndex(max(0, choices.findData(target)))

    search = QPushButton(QIcon.fromTheme('view-refresh'), 'Detectar chaves novamente')
    search.clicked.connect(reload)
    layout.addWidget(search)
    authentication = QPushButton(QIcon.fromTheme('preferences-desktop-user-password'), 'Configurações da tela de bloqueio')
    authentication.clicked.connect(lambda: subprocess.Popen(
        ['/usr/bin/kcmshell6', 'kcm_screenlocker'], start_new_session=True))
    layout.addWidget(authentication)
    controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    controls.rejected.connect(dialog.reject)
    layout.addWidget(controls)
    reload()

    def save():
        try:
            path = preferences()
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            atomic_write(path, json.dumps({'key': choices.currentData()}).encode(), 0o600)
            command('/usr/bin/systemctl', '--user', 'start', 'linuxbr-key-lock.service')
        except (OSError, subprocess.SubprocessError, ValueError):
            QMessageBox.warning(dialog, 'Bloqueio por chave', 'Confira se o serviço da sessão está disponível.')
            return
        dialog.accept()

    controls.accepted.connect(save)
    return dialog.exec()


if __name__ == '__main__':
    if sys.argv[1:] == ['--monitor']:
        watch()
    else:
        configure()
