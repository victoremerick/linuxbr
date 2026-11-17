"""Cópia de texto temporária que conserva os demais itens da sessão."""
import secrets

from PyQt6.QtCore import QMimeData, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QClipboard


SECRET_FORMAT = 'x-kde-passwordManagerHint'
ITEM_FORMAT = 'application/x-linuxbr-temporary-clipboard'
DURATIONS = (15,30,60,120)


class TemporaryClipboard(QObject):
    status = pyqtSignal(str)

    def __init__(self, clipboard, parent=None):
        super().__init__(parent)
        self.clipboard = clipboard
        self.item = b''
        self.changing = False
        self.timer = QTimer(self,singleShot=True)
        self.timer.timeout.connect(self.expire)
        self.clipboard.changed.connect(self.changed)

    def copy(self, text, seconds):
        if not text or len(text)>4096 or type(seconds) is not int or seconds not in DURATIONS:
            raise ValueError('Digite até 4.096 caracteres e selecione um prazo.')
        mime = QMimeData()
        mime.setText(text)
        mime.setData(SECRET_FORMAT,b'secret')
        self.item = secrets.token_bytes(24)
        mime.setData(ITEM_FORMAT,self.item)
        self.changing = True
        try:
            self.clipboard.setMimeData(mime,QClipboard.Mode.Clipboard)
        finally:
            self.changing = False
        self.timer.start(seconds*1000)
        self.status.emit(f'Texto copiado por até {seconds} segundos. Ao fechar Configurações, a cópia é retirada.')

    def ours(self):
        if not self.item or not self.clipboard.ownsClipboard():
            return False
        mime = self.clipboard.mimeData(QClipboard.Mode.Clipboard)
        return bool(mime and mime.hasFormat(ITEM_FORMAT) and bytes(mime.data(ITEM_FORMAT))==self.item)

    def changed(self, mode):
        if mode==QClipboard.Mode.Clipboard and self.item and not self.changing and not self.ours():
            self.timer.stop()
            self.item = b''
            self.status.emit('O texto temporário foi substituído por outra cópia.')

    def expire(self):
        current = self.ours()
        self.timer.stop()
        self.item = b''
        if current:
            self.clipboard.clear(QClipboard.Mode.Clipboard)
            self.status.emit('Texto temporário retirado da área de transferência.')
