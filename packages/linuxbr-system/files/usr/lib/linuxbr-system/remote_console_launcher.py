"""Open the selected server directly in the browser."""

import ipaddress
import re
import sys
from urllib.parse import urlsplit

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox


def server_url(value):
    value = value.strip()
    if not value or any(character.isspace() for character in value):
        raise ValueError('Informe o nome ou o IP do servidor.')
    if '://' not in value:
        value = 'https://' + value
    address = urlsplit(value)
    if (address.scheme != 'https' or not address.hostname or address.username is not None
            or address.password is not None or address.path not in ('', '/')
            or address.query or address.fragment):
        raise ValueError('Use apenas o nome ou IP do servidor e a porta HTTPS opcional.')
    host = address.hostname
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', host):
            raise ValueError('Nome do servidor inválido.') from None
    port = address.port
    if port == 0:
        raise ValueError('Porta inválida.')
    if ':' in host:
        host = '[' + host + ']'
    return f'https://{host}:{port or 9090}/'


def main():
    app = QApplication(sys.argv)
    title = 'Central de Administração Remota'
    value = 'localhost'
    while True:
        value, accepted = QInputDialog.getText(None, title, 'Nome ou IP do servidor', text=value)
        if not accepted:
            return 0
        try:
            target = server_url(value)
        except ValueError as error:
            QMessageBox.warning(None, title, str(error))
            continue
        if QDesktopServices.openUrl(QUrl(target)):
            return 0
        QMessageBox.warning(None, title, 'Não foi possível abrir o navegador.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
