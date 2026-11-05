"""Explicit SMB reconnection using the desktop's authentication and wallet."""
import shutil

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from core import smb_url


UNAVAILABLE = ('Não foi possível acessar a unidade. Confira a conexão de rede ou VPN, '
               'se o computador está ligado e se a pasta continua compartilhada. '
               'Se o acesso foi negado, confira a conta e a permissão da pasta. '
               'O endereço e a letra foram preservados. Use Reconectar para tentar novamente.')


def wallet_command():
    return next((path for name in ('kwalletmanager5', 'kwalletmanager6', 'kwalletmanager')
                 if (path := shutil.which(name))), None)


class NetworkAccess(QObject):
    finished = pyqtSignal(str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.url = ''
        self.timed_out = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.expire)

    @property
    def busy(self):
        return self.process is not None

    def start(self, location):
        if self.busy:
            raise ValueError('Aguarde a tentativa de conexão em andamento.')
        self.url = smb_url(location)
        program = next((path for name in ('kioclient6', 'kioclient')
                        if (path := shutil.which(name))), None)
        if not program:
            raise ValueError('O componente de acesso à rede não está instalado. Reinstale kde-cli-tools e kio-extras.')
        self.timed_out = False
        process = QProcess(self)
        # KIO owns all authentication dialogs and optional encrypted KWallet storage.
        # Neither passwords nor the command's output are read or saved here.
        # Listing a share triggers the SMB worker's initial authentication path.
        # A metadata-only stat can fail before asking for credentials.
        process.setStandardOutputFile(QProcess.nullDevice())
        process.setStandardErrorFile(QProcess.nullDevice())
        process.finished.connect(lambda code, status: self.complete(process, code, status))
        process.errorOccurred.connect(lambda error: self.failed(process, error))
        self.process = process
        self.timer.start(120000)
        process.start(program, ['--interactive', 'ls', self.url])

    def failed(self, process, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.complete(process, 1, QProcess.ExitStatus.CrashExit)

    def expire(self):
        if self.process:
            self.timed_out = True
            self.process.kill()

    def cancel(self):
        if self.process:
            self.timer.stop()
            process, self.process = self.process, None
            process.finished.connect(process.deleteLater)
            process.kill()

    def complete(self, process, code, status):
        if self.process is not process:
            return
        self.timer.stop()
        process, self.process = self.process, None
        process.deleteLater()
        success = code == 0 and status == QProcess.ExitStatus.NormalExit
        text = ('Acesso confirmado nesta tentativa.' if success else
                ('O tempo de conexão terminou. ' if self.timed_out else '') + UNAVAILABLE)
        self.finished.emit(self.url, success, text)
