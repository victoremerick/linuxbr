"""Keyboard activation shared by standalone configuration windows."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton


class EnterActivation:
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            if not event.isAutoRepeat():self.click()
            event.accept();return
        super().keyPressEvent(event)


class SettingsButton(EnterActivation,QPushButton):
    pass
