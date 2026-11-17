"""Send a link or clipboard text to a paired device."""

import re
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox


TITLE = 'Enviar para outro dispositivo'
CLI = '/usr/bin/kdeconnect-cli'


def send_command(*args):
    return subprocess.run([CLI, *args], check=True, capture_output=True, text=True, timeout=8).stdout


def available_devices(output):
    devices = {}
    for row in output.splitlines():
        identifier, _, name = row.partition(' ')
        if re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identifier) and name.strip():
            devices[f'{name.strip()} ({identifier})'] = identifier
    return devices


def choose_device(parent):
    devices = available_devices(send_command('--list-available', '--id-name-only'))
    if not devices:
        QMessageBox.information(parent, TITLE, 'Abra Dispositivos conectados para parear outro computador.')
        return None
    name, accepted = QInputDialog.getItem(parent, TITLE, 'Dispositivo', list(devices), editable=False)
    return (devices[name], name) if accepted else None


def share_file(identifier, path):
    send_command('--device', identifier, '--share', Path(path).resolve(strict=True).as_uri())


def valid_link(value):
    try:
        url = urlsplit(value)
        return (url.scheme in ('https', 'http') and bool(url.hostname) and url.username is None
                and url.password is None and '\\' not in value
                and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value))
    except ValueError:
        return False


def main():
    app = QApplication(sys.argv)
    try:
        device = choose_device(None)
        if device is None:
            return 0
        items = ['Link para revisar ou guardar', 'Abrir link no outro dispositivo', 'Área de transferência']
        kind, accepted = QInputDialog.getItem(None, TITLE, 'Conteúdo a enviar', items, editable=False)
        if not accepted:
            return 0
        if kind in items[:2]:
            url, accepted = QInputDialog.getText(None, TITLE, 'Endereço da página')
            if not accepted:
                return 0
            url = url.strip()
            if not valid_link(url):
                raise ValueError('Informe um endereço HTTP ou HTTPS válido.')
            if kind == items[0]:
                from shared_links import SUFFIX, encode_link
                from store_sources import atomic_write

                filename, _ = QFileDialog.getSaveFileName(
                    None, TITLE, 'Link recebido' + SUFFIX, 'Link Linux BR (*.linuxbr-link)'
                )
                if not filename:
                    return 0
                path = Path(filename)
                if path.suffix != SUFFIX:
                    QMessageBox.warning(None, TITLE, 'Use a extensão ' + SUFFIX + ' para o arquivo.')
                    return 1
                atomic_write(path, encode_link(url), 0o600)
                share_file(device[0], path)
                QMessageBox.information(None, TITLE, 'Arquivo salvo e solicitação de envio entregue ao KDE Connect.')
                return 0
            args = ('--share', url)
        else:
            if not app.clipboard().text():
                raise ValueError('A área de transferência está sem texto.')
            if QMessageBox.question(None, TITLE, 'Enviar o texto copiado ao dispositivo selecionado?') != QMessageBox.StandardButton.Yes:
                return 0
            args = ('--send-clipboard',)
        send_command('--device', device[0], *args)
        QMessageBox.information(None, TITLE, 'Solicitação de envio entregue ao KDE Connect.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'Confira se o dispositivo está pareado e disponível.'
        QMessageBox.warning(None, TITLE, detail)
        return 1


if __name__ == '__main__':
    sys.exit(main())
