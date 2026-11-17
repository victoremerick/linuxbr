"""Diagnóstico local de caminhos de retorno de login sem inspecionar conteúdo."""
import ipaddress
import os
from pathlib import Path
import re
import struct
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


SOCKET = re.compile(r'socket:\[(\d+)\]')
SCHEME = re.compile(r'[a-z][a-z0-9+.-]{1,31}')
DURATION = 90


def handlers(scheme):
    from gi.repository import Gio
    normalized = scheme.strip().casefold().removesuffix(':')
    if not SCHEME.fullmatch(normalized) or normalized in ('https','http','file','mailto'):
        raise ValueError('Informe um protocolo específico do aplicativo sem endereço, código ou parâmetros.')
    handler = Gio.AppInfo.get_default_for_uri_scheme(normalized)
    if not handler:
        return 'Este protocolo ainda não tem um aplicativo associado no Linux BR.'
    return 'Destino configurado: '+handler.get_display_name()


def loopback(raw):
    if len(raw) == 8:
        value = ipaddress.IPv4Address(struct.pack('=I', int(raw, 16)))
    elif len(raw) == 32:
        value = ipaddress.IPv6Address(struct.pack('=IIII', *(int(raw[index:index+8], 16) for index in range(0,32,8))))
        value = value.ipv4_mapped or value
    else:
        raise ValueError('Endereço inválido.')
    return value.is_loopback, value.is_unspecified


def socket_owners(prefix, proc):
    expected = b'WINEPREFIX='+os.fsencode(prefix)
    owned = set()
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            with (process/'environ').open('rb') as stream:
                if expected not in stream.read(512*1024).split(b'\0'):
                    continue
            for descriptor in (process/'fd').iterdir():
                try:
                    target = os.readlink(descriptor)
                except OSError:
                    continue
                match = SOCKET.fullmatch(target)
                if match:
                    owned.add(match[1])
        except OSError:
            continue
    return owned


def transport(prefix, proc=Path('/proc')):
    """Return only TCP ports, with no contents or external endpoint identities."""
    owned = socket_owners(prefix, proc)
    listening, connected = set(), set()
    if owned:
        has_tables = False
        for name in ('tcp','tcp6'):
            try:
                table = (proc/'net'/name).read_text().splitlines()
            except OSError:
                continue
            has_tables |= bool(table)
            for line in table[1:]:
                fields = line.split()
                if len(fields) < 10 or fields[9] not in owned:
                    continue
                try:
                    local, port = fields[1].split(':')
                    remote = fields[2].split(':')[0]
                    local_loopback, any_interface = loopback(local)
                    if fields[3] == '0A' and (local_loopback or any_interface):
                        listening.add(int(port, 16))
                    if fields[3] in ('01','08') and local_loopback and loopback(remote)[0]:
                        connected.add(int(port, 16))
                except ValueError:
                    continue
        if not has_tables:
            raise OSError('A sessão não fornece as tabelas TCP locais.')
    return listening, connected


class LoginDiagnostics(QDialog):
    def __init__(self, name, prefix, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Retorno do navegador para '+name)
        self.resize(620, 385)
        self.prefix = prefix
        self.listened = set()
        self.observed = set()
        self.deadline = 0
        layout = QVBoxLayout(self)
        intro = QLabel('Acompanhe uma tentativa de entrada. A observação verifica conexões locais do ambiente Wine. O aplicativo confirma se o login foi aceito.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.callback_status = QLabel('Inicie a observação antes de concluir o login no navegador.')
        self.callback_status.setTextFormat(Qt.TextFormat.PlainText)
        self.callback_status.setWordWrap(True)
        self.callback_status.setAccessibleName('Retorno local do navegador')
        layout.addWidget(self.callback_status)
        row = QHBoxLayout()
        self.observe = QPushButton('Observar retorno local')
        self.observe.clicked.connect(self.start)
        row.addWidget(self.observe)
        self.stop = QPushButton('Encerrar observação')
        self.stop.clicked.connect(self.finish)
        self.stop.setEnabled(False)
        row.addWidget(self.stop)
        layout.addLayout(row)
        note = QLabel('Se o fornecedor informar um protocolo próprio, consulte separadamente o aplicativo associado.')
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.scheme = QLineEdit()
        self.scheme.setMaxLength(32)
        form.addRow('&Protocolo do aplicativo', self.scheme)
        lookup = QPushButton('Consultar associação no Linux BR')
        lookup.clicked.connect(self.lookup)
        form.addRow(lookup)
        layout.addLayout(form)
        self.route_status = QLabel('')
        self.route_status.setTextFormat(Qt.TextFormat.PlainText)
        self.route_status.setWordWrap(True)
        layout.addWidget(self.route_status)
        layout.addStretch()
        done = QPushButton('Fechar')
        done.clicked.connect(self.reject)
        layout.addWidget(done)
        self.timer = QTimer(self)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.sample)

    def start(self):
        self.listened.clear()
        self.observed.clear()
        self.deadline = time.monotonic() + DURATION
        self.observe.setEnabled(False)
        self.stop.setEnabled(True)
        self.timer.start()
        self.sample()

    def sample(self):
        try:
            listeners, connections = transport(self.prefix)
        except OSError:
            self.finish()
            self.callback_status.setText('A sessão não permite consultar os soquetes locais deste ambiente.')
            return
        left = max(0, int(self.deadline-time.monotonic()))
        self.listened.update(listeners)
        self.observed.update(self.listened & connections)
        if self.observed or not left:
            self.finish()
        elif self.listened:
            self.callback_status.setText(f'Porta local encontrada. Aguardando o navegador · {left} s.')
        else:
            self.callback_status.setText(f'Aguardando uma porta de retorno no ambiente Wine · {left} s.')

    def finish(self):
        self.timer.stop()
        self.observe.setEnabled(True)
        self.stop.setEnabled(False)
        if self.observed:
            ports = ', '.join(map(str, sorted(self.observed)))
            self.callback_status.setText('A conexão de retorno chegou ao ambiente Wine pela porta '+ports+
                                         '. Confira o resultado da entrada no próprio aplicativo.')
        else:
            self.callback_status.setText('Nenhuma conexão de retorno local foi observada neste intervalo.')

    def lookup(self):
        try:
            text = handlers(self.scheme.text())
        except (OSError, ValueError, ImportError) as error:
            text = str(error)
        self.route_status.setText(text)

    def done(self, result):
        self.timer.stop()
        super().done(result)
