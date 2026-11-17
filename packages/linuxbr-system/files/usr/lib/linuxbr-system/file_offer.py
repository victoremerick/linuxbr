"""Ask a paired device to approve a file transfer before sending its contents."""

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from time import time
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from send_content import choose_device, share_file
from store_sources import atomic_write


TITLE = 'Enviar arquivos com aceite'
SUFFIX = '.linuxbr-transfer'
TOKEN = re.compile('[0-9a-f]{32}')
DEVICE = re.compile('[A-Za-z0-9_-]{1,128}')


def directory():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'linuxbr/file-offers'


def read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Escolha um arquivo de transferência regular.')
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError('O pedido de transferência é muito grande.')
    record = json.loads(data)
    if not isinstance(record, dict):
        raise ValueError('Pedido de transferência inválido.')
    return record


def write(path, record):
    data = (json.dumps(record, ensure_ascii=False) + '\n').encode()
    if len(data) > 65536:
        raise ValueError('O pedido de transferência é muito grande.')
    atomic_write(path, data, 0o600)


def exchange(record, target, label):
    filename, _ = QFileDialog.getSaveFileName(None, TITLE, label + SUFFIX, 'Pedido de transferência (*' + SUFFIX + ')')
    if not filename:
        return False
    if not filename.endswith(SUFFIX):
        raise ValueError('Use a extensão ' + SUFFIX + ' para o pedido.')
    path = Path(filename)
    write(path, record)
    share_file(target, path)
    return True


def signature(path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Selecione somente arquivos regulares.')
    return dict(name=path.name, size=info.st_size, modified=info.st_mtime_ns,
                device=info.st_dev, inode=info.st_ino)


def ask(text, confirm_label):
    box = QMessageBox(QMessageBox.Icon.Question, TITLE, text, QMessageBox.StandardButton.Cancel)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    button = box.addButton(confirm_label, QMessageBox.ButtonRole.ActionRole)
    box.exec()
    return box.clickedButton() is button


def offer(files):
    if not 1 <= len(files) <= 20:
        raise ValueError('Selecione de 1 a 20 arquivos por pedido.')
    paths = [Path(path).resolve(strict=True) for path in files]
    entries = [dict(signature(path), path=str(path)) for path in paths]
    target = choose_device(None)
    if target is None:
        return
    token = uuid4().hex
    pending = directory()
    pending.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = pending / (token + '.json')
    for item in pending.glob('*.json'):
        if item.is_file() and not item.is_symlink() and time() - item.stat().st_mtime > 7 * 86400:
            item.unlink(missing_ok=True)
    write(state, dict(device=target[0], files=entries))
    request = dict(kind='linuxbr-file-offer-1', token=token, files=[
        dict(name=row['name'], size=row['size']) for row in entries
    ])
    try:
        sent = exchange(request, target[0], 'Pedido de arquivos')
    except Exception:
        state.unlink(missing_ok=True)
        raise
    if sent:
        QMessageBox.information(None, TITLE,
            'Pedido enviado. Ao receber a confirmação, abra o arquivo de aceite para enviar o conteúdo.')
    else:
        state.unlink()


def receive(path):
    message = read(path)
    token = message.get('token', '')
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise ValueError('Identificador de transferência inválido.')
    if message.get('kind') == 'linuxbr-file-offer-1':
        files = message.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= 20 or not all(
            isinstance(item, dict) and item.keys() == {'name', 'size'}
            and isinstance(item['name'], str) and 0 < len(item['name']) <= 255
            and type(item['size']) is int and item['size'] >= 0 for item in files
        ):
            raise ValueError('Lista de arquivos inválida.')
        preview = '\n'.join(f'{row["name"]!r} · {row["size"]:,} bytes' for row in files)
        if ask(preview, 'Aceitar arquivos'):
            sender = choose_device(None)
            if sender and exchange(dict(kind='linuxbr-file-accept-1', token=token), sender[0], 'Aceite de arquivos'):
                QMessageBox.information(None, TITLE, 'Aceite enviado. O remetente ainda precisa abrir a confirmação.')
        return
    if message.get('kind') != 'linuxbr-file-accept-1':
        raise ValueError('Tipo de transferência inválido.')
    state = directory() / (token + '.json')
    if time() - state.stat().st_mtime > 7 * 86400:
        raise ValueError('Este pedido expirou. Inicie uma nova transferência.')
    pending = read(state)
    device = pending['device']
    if not DEVICE.fullmatch(device):
        raise ValueError('Destinatário inválido.')
    paths = [Path(row['path']) for row in pending['files']]
    for path, previous in zip(paths, pending['files']):
        if signature(path) != {key: value for key, value in previous.items() if key != 'path'}:
            raise ValueError('Um arquivo mudou depois do pedido. Faça um novo pedido de transferência.')
    if not ask(f'Foi aberto um arquivo de aceite. Enviar {len(paths)} arquivo(s) ao dispositivo originalmente escolhido?', 'Enviar arquivos'):
        return
    from send_content import send_command

    uris = [path.as_uri() for path in paths]
    send_command('--device', device, '--share', *uris)
    state.unlink()
    QMessageBox.information(None, TITLE, 'Arquivos entregues ao KDE Connect. Acompanhe o progresso nas notificações.')


def main():
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-file-offer')
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == '--offer':
            offer(sys.argv[2:])
        elif len(sys.argv) == 2:
            receive(sys.argv[1])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        text = str(error) if isinstance(error, ValueError) else 'Confira o arquivo e se o dispositivo pareado está disponível.'
        QMessageBox.warning(None, TITLE, text)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
