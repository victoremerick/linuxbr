#!/usr/bin/python3
"""Verify LUKS recovery passphrases and store or export encrypted copies."""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


UUID = re.compile(r'[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}')
TOOL = '/usr/lib/linuxbr-system/recovery_keys.py'


def volumes():
    result = subprocess.run(['/usr/bin/lsblk', '--json', '--paths', '--list',
                             '--output', 'PATH,FSTYPE,UUID,SIZE,LABEL'],
                            capture_output=True, check=True, timeout=8)
    return [item for item in json.loads(result.stdout)['blockdevices']
            if item.get('fstype') == 'crypto_LUKS' and isinstance(item.get('uuid'), str)
            and UUID.fullmatch(item['uuid'])]


def verify(identifier, phrase):
    if os.geteuid() != 0 or not UUID.fullmatch(identifier) or not 0 < len(phrase) <= 4096:
        raise ValueError('Volume ou frase de recuperação inválida.')
    device = Path('/dev/disk/by-uuid') / identifier
    if not stat.S_ISBLK(device.stat().st_mode):
        raise ValueError('O volume selecionado não está disponível.')
    program = shutil.which('cryptsetup', path='/usr/sbin:/usr/bin')
    if not program:
        raise ValueError('Instale o pacote cryptsetup-bin para conferir a frase.')
    result = subprocess.run([program, 'open', '--type', 'luks', '--test-passphrase',
                             '--batch-mode', '--disable-external-tokens', '--key-file', '-', str(device)],
                            input=phrase, capture_output=True, timeout=30,
                            env={'PATH': '/usr/sbin:/usr/bin', 'LC_ALL': 'C'})
    if result.returncode:
        raise ValueError('O volume não aceitou a frase de recuperação informada.')


def vault(identifier, phrase=None):
    import gi
    gi.require_version('Secret', '1')
    from gi.repository import Secret

    schema = Secret.Schema.new('org.linuxbr.RecoveryKeys', Secret.SchemaFlags.NONE,
                               {'volume': Secret.SchemaAttributeType.STRING})
    fields = {'volume': identifier}
    if phrase is None:
        return Secret.password_lookup_sync(schema, fields, None)
    return Secret.password_store_sync(schema, fields, Secret.COLLECTION_DEFAULT,
                                      'Frase de recuperação LUKS · ' + identifier, phrase, None)


def export(identifier, phrase, password, destination):
    from store_sources import atomic_write

    encoded = password.encode('utf-8')
    if not UUID.fullmatch(identifier) or not 0 < len(encoded) <= 1024 or b'\n' in encoded or b'\0' in encoded:
        raise ValueError('Informe uma senha válida para proteger a cópia.')
    document = json.dumps(dict(schema=1, volume=identifier, type='LUKS', recovery_passphrase=phrase),
                          ensure_ascii=False).encode('utf-8')
    read_fd, write_fd = os.pipe()
    try:
        with os.fdopen(write_fd, 'wb') as key:
            key.write(encoded + b'\n')
        result = subprocess.run(['/usr/bin/gpg', '--batch', '--no-tty', '--no-options',
                                 '--pinentry-mode', 'loopback', '--no-symkey-cache',
                                 '--passphrase-fd', str(read_fd), '--symmetric',
                                 '--cipher-algo', 'AES256', '--output', '-'],
                                input=document, pass_fds=(read_fd,),
                                capture_output=True, timeout=30, check=True)
    finally:
        os.close(read_fd)
    atomic_write(destination, result.stdout, 0o600)


def window():
    from PyQt6.QtCore import QProcess
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFormLayout,
                                 QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout)
    from desktop_theme import initialize
    initialize()
    application = QApplication(sys.argv)
    dialog = QDialog()
    dialog.setWindowTitle('Chaves de recuperação')
    dialog.setWindowIcon(QIcon.fromTheme('security-high'))
    dialog.resize(620, 325)
    layout = QVBoxLayout(dialog)
    note = QLabel('Selecione um volume LUKS. Confira a frase existente, guarde-a no cofre da sua conta '
                  'ou exporte uma cópia OpenPGP com senha própria.')
    note.setWordWrap(True)
    layout.addWidget(note)
    form = QFormLayout()
    choices = QComboBox()
    form.addRow('Volume LUKS', choices)
    phrase = QLineEdit()
    phrase.setEchoMode(QLineEdit.EchoMode.Password)
    form.addRow('Frase de recuperação', phrase)
    layout.addLayout(form)
    message = QLabel()
    message.setWordWrap(True)
    layout.addWidget(message)
    verify_button = QPushButton(QIcon.fromTheme('dialog-ok-apply'), 'Verificar frase')
    store_button = QPushButton(QIcon.fromTheme('document-save'), 'Verificar e guardar no cofre')
    export_button = QPushButton(QIcon.fromTheme('document-export'), 'Exportar cópia do cofre…')
    for control in (verify_button, store_button, export_button):
        layout.addWidget(control)
    try:
        for item in volumes():
            choices.addItem(' · '.join(filter(None, (item['path'], item.get('label'), item.get('size')))), item['uuid'])
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        message.setText('Falha ao consultar os volumes locais.')
    if not choices.count():
        for control in (verify_button, store_button, export_button):
            control.setEnabled(False)
        if not message.text():
            message.setText('Nenhum volume LUKS foi encontrado.')

    process = QProcess(dialog)

    def check(save):
        if process.state() != QProcess.ProcessState.NotRunning:
            return
        secret, identifier = phrase.text(), choices.currentData()
        if not 0 < len(secret.encode('utf-8')) <= 4096:
            message.setText('Informe a frase de recuperação do volume.')
            return
        phrase.clear()
        verify_button.setEnabled(False); store_button.setEnabled(False)
        message.setText('Aguardando autorização para verificar o volume…')

        def submit():
            process.write(secret.encode('utf-8'))
            process.closeWriteChannel()

        def finished(code, *_):
            verify_button.setEnabled(True); store_button.setEnabled(True)
            try:
                if code != 0:
                    message.setText('A frase não foi verificada. Confira a autorização, a frase e o dispositivo.')
                elif save and not vault(identifier, secret):
                    message.setText('A frase foi verificada. O cofre não confirmou o armazenamento.')
                else:
                    message.setText('Frase verificada e guardada no cofre.' if save else 'Frase aceita pelo volume.')
            except Exception:
                message.setText('A frase foi verificada. O cofre da conta está indisponível.')
            finally:
                process.started.disconnect(submit)
                process.finished.disconnect(finished)
                process.errorOccurred.disconnect(failed)

        def failed(error):
            if error == QProcess.ProcessError.FailedToStart:
                finished(1)

        process.started.connect(submit)
        process.finished.connect(finished)
        process.errorOccurred.connect(failed)
        process.start('/usr/bin/pkexec', [TOOL, '--verify', identifier])

    def save_copy():
        identifier = choices.currentData()
        try:
            secret = vault(identifier)
            if not secret:
                message.setText('Verifique e guarde a frase deste volume no cofre antes de exportar.')
                return
            first, ok = QInputDialog.getText(dialog, 'Proteger cópia', 'Senha do arquivo OpenPGP',
                                              QLineEdit.EchoMode.Password)
            if not ok or not first:
                return
            second, ok = QInputDialog.getText(dialog, 'Confirmar senha', 'Repita a senha do arquivo',
                                               QLineEdit.EchoMode.Password)
            if not ok or first != second:
                message.setText('As senhas informadas precisam coincidir.')
                return
            target, _ = QFileDialog.getSaveFileName(dialog, 'Salvar cópia protegida',
                str(Path.home() / ('recuperacao-' + identifier[:8] + '.gpg')), 'OpenPGP (*.gpg)')
            if target:
                export(identifier, secret, first, Path(target))
                message.setText('Cópia criptografada salva. Guarde-a separada do volume.')
        except Exception:
            QMessageBox.warning(dialog, 'Cópia protegida', 'Não foi possível consultar o cofre ou salvar a cópia.')

    verify_button.clicked.connect(lambda: check(False))
    store_button.clicked.connect(lambda: check(True))
    export_button.clicked.connect(save_copy)
    dialog.exec()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--verify':
        try:
            verify(sys.argv[2], sys.stdin.buffer.read(4097))
        except (OSError, ValueError, subprocess.SubprocessError):
            sys.exit(1)
    elif len(sys.argv) == 1 and os.geteuid() != 0:
        window()
    else:
        sys.exit(2)
