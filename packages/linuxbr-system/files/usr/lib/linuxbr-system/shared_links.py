"""Review, save and open web links received as Linux BR link files."""

import json
import os
from pathlib import Path
import stat
from uuid import uuid4

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from send_content import valid_link
from store_sources import atomic_write


TITLE = 'Links recebidos'
SUFFIX = '.linuxbr-link'
SCHEMA = 'linuxbr-link-1'
LIMIT = 8192


def encode_link(url):
    if not isinstance(url, str) or not valid_link(url):
        raise ValueError('Informe um endereço HTTP ou HTTPS válido.')
    data = (json.dumps(dict(schema=SCHEMA, url=url), ensure_ascii=False) + '\n').encode()
    if len(data) > LIMIT:
        raise ValueError('O link excede o tamanho permitido.')
    return data


def load_link(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Escolha um arquivo de link regular.')
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('O arquivo de link excede o tamanho permitido.')
    item = json.loads(data)
    if not isinstance(item, dict) or item.keys() != {'schema', 'url'} or item['schema'] != SCHEMA:
        raise ValueError('Arquivo de link inválido.')
    encode_link(item['url'])
    return item['url']


def inbox():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'linuxbr/shared-links'


def review(path, saved=False):
    url = load_link(path)
    box = QMessageBox()
    box.setWindowTitle(TITLE)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(url)
    box.setStandardButtons(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    open_button = box.addButton('Abrir no navegador', QMessageBox.ButtonRole.ActionRole)
    save = box.addButton('Guardar para depois', QMessageBox.ButtonRole.ActionRole) if not saved else None
    box.exec()
    chosen = box.clickedButton()
    if chosen is open_button:
        if not QDesktopServices.openUrl(QUrl(url)):
            raise ValueError('Não foi possível abrir o navegador.')
    elif save is not None and chosen is save:
        directory = inbox()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_write(directory / (uuid4().hex + SUFFIX), encode_link(url), 0o600)
        QMessageBox.information(None, TITLE, 'Link guardado. Abra Links recebidos pelo menu Iniciar para encontrá-lo.')


def main():
    import sys

    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-shared-links')
    try:
        if len(sys.argv) == 2:
            review(Path(sys.argv[1]))
            return 0
        options = {'Abrir um arquivo recebido…': None}
        for path in sorted(inbox().glob('*' + SUFFIX), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                url = load_link(path)
            except (OSError, ValueError):
                continue
            options[f'{url[:180]} ({path.stem[:8]})'] = path
        choice, accepted = QInputDialog.getItem(None, TITLE, 'Escolher link', list(options), editable=False)
        if accepted:
            path = options[choice]
            if path is not None:
                review(path, saved=True)
            else:
                filename, _ = QFileDialog.getOpenFileName(None, TITLE, '', 'Link Linux BR (*.linuxbr-link)')
                if filename:
                    review(Path(filename))
    except (OSError, UnicodeError, ValueError):
        QMessageBox.warning(None, TITLE, 'Não foi possível ler ou guardar o link. Confira o arquivo recebido.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
