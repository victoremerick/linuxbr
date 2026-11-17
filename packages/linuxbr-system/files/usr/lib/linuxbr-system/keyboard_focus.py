"""Optional high-contrast outline for the focused widget in Linux BR Settings."""
import os
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QWidget


def preference():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/keyboard-focus'


def set_preference(enabled):
    path = preference()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(descriptor)
    else:
        path.unlink(missing_ok=True)


class Outline(QWidget):
    def __init__(self, target):
        super().__init__(target)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(target.rect())
        target.installEventFilter(self)
        self.raise_()
        self.show()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(source.rect())
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        palette = self.palette()
        for inset, color, width in ((2, palette.windowText().color(), 3), (4, palette.highlight().color(), 2)):
            painter.setPen(QPen(color, width))
            painter.drawRect(self.rect().adjusted(inset, inset, -inset - 1, -inset - 1))


class KeyboardFocus(QObject):
    def __init__(self, app, enabled=None):
        super().__init__(app)
        self.app = app
        self.enabled = preference().is_file() if enabled is None else enabled
        self.outline = None
        app.focusChanged.connect(self.changed)
        if enabled is None:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(1000)
        self.changed(None, app.focusWidget())

    def refresh(self):
        preferred = preference().is_file()
        if self.enabled != preferred:
            self.enabled = preferred
            self.changed(None, self.app.focusWidget())

    def changed(self, old, target):
        if self.outline is not None and not sip.isdeleted(self.outline):
            self.outline.hide()
            self.outline.deleteLater()
        self.outline = Outline(target) if self.enabled and target is not None else None
