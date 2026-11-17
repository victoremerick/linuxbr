"""A Plasma virtual screen delivered over SSH to a second computer."""

import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sys
from tempfile import TemporaryDirectory

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QMessageBox, QSpinBox, QVBoxLayout,
)

TITLE = 'Segunda tela pela rede'
SERVERS = ('/usr/bin/bwrap', '/usr/bin/socat', '/usr/bin/krfb-virtualmonitor')
RESOLUTIONS = ('1280x768', '1280x800', '1920x1080', '2560x1440')


def server_arguments(directory, resolution, password):
    if resolution not in RESOLUTIONS:
        raise ValueError('Resolução inválida.')
    return [
        SERVERS[0], '--unshare-net', '--die-with-parent', '--bind', '/', '/',
        '--dev-bind', '/dev', '/dev',
        '--', '/bin/sh', '-c',
        'socat "$1" TCP:127.0.0.1:5590 <&0 & proxy=$!; '
        'trap \'kill "$proxy" || true\' EXIT; '
        'krfb-virtualmonitor --name LinuxBR-Rede --resolution "$2" --port 5590 --password "$3"',
        'linuxbr-wireless-display', 'UNIX-LISTEN:' + str(directory / 'vnc') + ',fork,mode=0600',
        resolution, password,
    ]


def client_arguments(host, port, remote, local_port):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}@[A-Za-z0-9][A-Za-z0-9.-]{0,252}', host):
        raise ValueError('Informe o destino SSH no formato usuario@computador.')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]{1,90}/vnc', remote) or '..' in remote.split('/'):
        raise ValueError('Copie o endereço do soquete que aparece no computador de origem.')
    if not 1 <= port <= 65535 or not 1024 <= local_port <= 65535:
        raise ValueError('Informe uma porta SSH válida.')
    return ['/usr/bin/ssh', '-N', '-o', 'StrictHostKeyChecking=yes', '-o', 'ExitOnForwardFailure=yes',
            '-o', 'BatchMode=yes', '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
            '-p', str(port), '-L', f'127.0.0.1:{local_port}:' + remote, '--', host]


def host_display():
    if os.environ.get('XDG_SESSION_TYPE') != 'wayland':
        raise ValueError('Abra uma sessão Plasma Wayland para criar uma tela virtual.')
    if not all(shutil.which(binary) for binary in SERVERS):
        raise ValueError('Ative Segunda tela pela rede em Recursos opcionais.')
    from PyQt6.QtWidgets import QInputDialog

    resolution, accepted = QInputDialog.getItem(None, TITLE, 'Resolução da tela adicional', RESOLUTIONS, editable=False)
    if not accepted:
        return
    with TemporaryDirectory(prefix='linuxbr-screen-', dir='/tmp') as folder:
        path = Path(folder)
        password = secrets.token_urlsafe(6)
        dialog = QDialog()
        dialog.setWindowTitle(TITLE)
        layout = QVBoxLayout(dialog)
        instructions = QLabel(
            'Na outra máquina, escolha Conectar a uma tela e use sua conta SSH deste computador, '
            'o soquete e o código abaixo. Mantenha esta janela aberta durante o uso.'
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        form = QFormLayout()
        layout.addLayout(form)
        for label, value in [('Soquete', str(path / 'vnc')), ('Código VNC', password)]:
            field = QLineEdit(value)
            field.setReadOnly(True)
            field.setMinimumWidth(360)
            form.addRow(label, field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        from PyQt6.QtCore import QProcess

        server = QProcess(dialog)
        server.finished.connect(lambda *_: instructions.setText(
            'A tela virtual foi encerrada. Confira se a sessão permite criar monitores e isolar a rede.'
        ))
        server.errorOccurred.connect(lambda _: instructions.setText('Falha ao iniciar a tela virtual.'))
        argv = server_arguments(path, resolution, password)
        server.start(argv[0], argv[1:])
        dialog.exec()
        if server.state() != QProcess.ProcessState.NotRunning:
            server.terminate()
            if not server.waitForFinished(2000):
                server.kill()
                server.waitForFinished(1000)


def connect_display():
    dialog = QDialog()
    dialog.setWindowTitle('Conectar a uma tela')
    layout = QVBoxLayout(dialog)
    form = QFormLayout()
    layout.addLayout(form)
    host = QLineEdit()
    host.setPlaceholderText('usuario@computador')
    port = QSpinBox()
    port.setRange(1, 65535)
    port.setValue(22)
    remote = QLineEdit()
    form.addRow('Computador e conta SSH', host)
    form.addRow('Porta SSH', port)
    form.addRow('Soquete da tela', remote)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        local_port = listener.getsockname()[1]
    argv = client_arguments(host.text().strip(), port.value(), remote.text().strip(), local_port)
    if not shutil.which('konsole') or not shutil.which('krdc'):
        raise ValueError('Instale Konsole e KRDC neste computador.')
    from PyQt6.QtCore import QProcess

    script = (
        'port=$1; shift; '
        'trap \'kill "$tunnel" 2>/dev/null || true\' EXIT; '
        'trap \'exit 0\' HUP INT TERM; '
        '"$@" & tunnel=$!; '
        'for attempt in 1 2 3 4 5 6 7 8 9 10; do '
        'kill -0 "$tunnel" 2>/dev/null || break; '
        'if python3 -c \'import socket,sys; s=socket.create_connection(("127.0.0.1",int(sys.argv[1])), .4); s.settimeout(.4); assert s.makefile("rb").read(4)==b"RFB "\' "$port" 2>/dev/null; then '
        'kill -0 "$tunnel" 2>/dev/null && krdc "vnc://127.0.0.1:$port"; break; fi; sleep 1; done; '
        'printf "\\nPressione Enter para fechar a conexão.\\n"; read -r result'
    )
    if not QProcess.startDetached('/usr/bin/konsole',
            ['--separate', '-e', '/bin/sh', '-c', script, 'tela', str(local_port), *argv])[0]:
        raise ValueError('Não foi possível abrir o cliente de tela.')


def main():
    from PyQt6.QtWidgets import QInputDialog

    app = QApplication(sys.argv)
    options = ['Criar tela para outro computador', 'Conectar a uma tela']
    choice, accepted = QInputDialog.getItem(None, TITLE, 'O que deseja fazer?', options, editable=False)
    if not accepted:
        return 0
    try:
        (host_display if choice == options[0] else connect_display)()
    except (OSError, ValueError) as error:
        QMessageBox.warning(None, TITLE, str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
