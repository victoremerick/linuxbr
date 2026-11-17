"""Resume a document stored in a folder synchronized with another computer."""

import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from send_content import choose_device, share_file
from store_sources import atomic_write


TITLE = 'Continuar documento em outro computador'
EXTENSION = '.linuxbr-document'
SCHEMA = 'linuxbr-document-1'
DOCUMENTS = {'.pdf', '.txt', '.md', '.jpg', '.jpeg', '.png', '.odt', '.ods', '.docx', '.xlsx'}


def manifest(path, root):
    path = Path(path).resolve(strict=True)
    root = Path(root).resolve(strict=True)
    if not path.is_file() or not root.is_dir() or not path.is_relative_to(root):
        raise ValueError('Escolha um documento dentro da pasta sincronizada.')
    return dict(schema=SCHEMA, document=path.relative_to(root).as_posix())


def resolve_document(record, root):
    if (not isinstance(record, dict) or record.keys() != {'schema', 'document'} or record['schema'] != SCHEMA
            or not isinstance(record['document'], str)):
        raise ValueError('Arquivo de continuidade inválido.')
    value = record['document']
    if (not value or '\\' in value or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('O arquivo recebido contém um caminho inválido.')
    root = Path(root).resolve(strict=True)
    target = (root / PurePosixPath(value)).resolve(strict=True)
    if not root.is_dir() or not target.is_relative_to(root) or not target.is_file():
        raise ValueError('O documento não está na pasta sincronizada escolhida.')
    if target.suffix.lower() not in DOCUMENTS or target.stat().st_mode & 0o111:
        raise ValueError('Escolha um documento PDF, de texto, de escritório ou uma imagem PNG ou JPEG.')
    return target


def receive(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Escolha um arquivo de continuidade regular.')
        data = stream.read(8193)
    if len(data) > 8192:
        raise ValueError('O arquivo de continuidade excede o tamanho permitido.')
    record = json.loads(data)
    root = QFileDialog.getExistingDirectory(None, 'Escolher a cópia local da pasta sincronizada', str(Path.home()))
    if not root:
        return
    try:
        target = resolve_document(record, root)
    except FileNotFoundError as error:
        raise ValueError('O documento ainda não está disponível. Aguarde a sincronização e tente novamente.') from error
    box = QMessageBox(QMessageBox.Icon.Question, TITLE, str(target),
                      QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Cancel)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    if box.exec() == QMessageBox.StandardButton.Open and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
        raise ValueError('Não foi possível abrir o documento.')


def send(path):
    root = QFileDialog.getExistingDirectory(None, 'Escolher a pasta sincronizada com o destinatário', str(Path.home()))
    if not root:
        return
    send_from(path, root)


def send_from(path, root):
    record = manifest(path, root)
    resolve_document(record, root)
    target = choose_device(None)
    if target is None:
        return
    filename, _ = QFileDialog.getSaveFileName(None, 'Salvar o atalho de continuidade', Path(path).name + EXTENSION,
                                             'Documento para continuar (*.linuxbr-document)')
    if not filename:
        return
    if not filename.endswith(EXTENSION):
        raise ValueError('Use a extensão ' + EXTENSION + ' para o atalho.')
    data = (json.dumps(record, ensure_ascii=False) + '\n').encode()
    if len(data) > 8192:
        raise ValueError('O caminho do documento excede o tamanho permitido.')
    atomic_write(Path(filename), data, 0o600)
    share_file(target[0], filename)
    QMessageBox.information(None, TITLE, 'Atalho salvo e entregue ao KDE Connect. O documento chega pela sincronização da pasta.')


def recent_documents(folder):
    root = Path(folder).resolve(strict=True)
    xdg = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    import xml.etree.ElementTree as ET
    from datetime import datetime

    recent = xdg / 'recently-used.xbel'
    try:
        with recent.open('rb') as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
    except FileNotFoundError:
        return []
    if len(data) > 2 * 1024 * 1024 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('O histórico de documentos recentes está fora do formato esperado.')
    rows = {}
    for bookmark in ET.fromstring(data).findall('bookmark'):
        url = QUrl(bookmark.get('href', ''))
        if not url.isLocalFile() or url.host():
            continue
        try:
            path = Path(url.toLocalFile()).resolve(strict=True)
            if not path.is_relative_to(root) or path.suffix.lower() not in DOCUMENTS or not path.is_file():
                continue
            stamp = datetime.fromisoformat(bookmark.get('visited') or bookmark.get('modified') or '')
            if stamp.tzinfo is not None:
                rows[path] = max(stamp.timestamp(), rows.get(path, 0))
        except (OSError, ValueError):
            continue
    return sorted(rows, key=rows.get, reverse=True)[:50]


def choose_recent():
    from xml.etree.ElementTree import ParseError

    folder = QFileDialog.getExistingDirectory(None, 'Escolher a pasta sincronizada', str(Path.home()))
    if not folder:
        return
    root = Path(folder).resolve(strict=True)
    try:
        paths = {str(path.relative_to(root)): path for path in recent_documents(root)}
    except ParseError as error:
        raise ValueError('Não foi possível ler a lista de documentos recentes.') from error
    if not paths:
        QMessageBox.information(None, TITLE, 'Nenhum documento recente encontrado nesta pasta. Você pode enviar um arquivo pelo Explorador.')
        return
    choice, accepted = QInputDialog.getItem(None, TITLE, 'Documento recente', list(paths), editable=False)
    if accepted:
        send_from(paths[choice], root)


def main():
    from subprocess import SubprocessError

    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-document-handoff')
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '--send':
            send(sys.argv[2])
        elif len(sys.argv) == 2:
            receive(sys.argv[1])
        elif len(sys.argv) == 1:
            choose_recent()
    except (OSError, ValueError, SubprocessError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'Confira o arquivo, a pasta sincronizada e o pareamento.'
        QMessageBox.warning(None, TITLE, detail)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
