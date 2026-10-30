"""Full-screen session actions using the desktop's native authentication paths."""
import os
import shutil
import sys

import dbus
from PyQt6.QtCore import QLockFile, QProcess, QStandardPaths, Qt
from PyQt6.QtGui import QCursor, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                            QVBoxLayout, QWidget)


def session_call(service, path, interface, method, system=False):
    bus = dbus.SystemBus() if system else dbus.SessionBus()
    proxy = bus.get_object(service, path, introspect=False)
    return getattr(dbus.Interface(proxy, interface), method)(timeout=5)


class SessionActions(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Opções da sessão — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('system-users'))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet('''
            QWidget { background: #075a9b; color: white; font-size: 16px; }
            QPushButton { border: 1px solid transparent; text-align: left;
                          padding: 12px 16px; background: transparent; }
            QPushButton:hover { background: #ffffff20; }
            QPushButton:focus { border: 1px solid white; background: #ffffff20; }
            QPushButton#cancel { background: #ffffff30; text-align: center; }
        ''')
        outer = QVBoxLayout(self); outer.addStretch()
        row = QHBoxLayout(); row.addStretch()
        column = QVBoxLayout(); column.setSpacing(6)
        actions = [('Bloquear', 'lock'), ('Trocar usuário', 'switch'), ('Sair', 'logout'),
                   ('Alterar uma senha', 'password'), ('Gerenciador de Tarefas', 'tasks')]
        self.buttons = []
        for title, action in actions:
            button = QPushButton(title); button.setMinimumWidth(320)
            button.clicked.connect(lambda checked=False, key=action: self.activate(key))
            column.addWidget(button); self.buttons.append(button)
        self.error = QLabel(); self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.TextFormat.PlainText); self.error.setMaximumWidth(350)
        self.error.hide(); column.addWidget(self.error)
        column.addSpacing(32)
        cancel = QPushButton('Cancelar'); cancel.setObjectName('cancel')
        cancel.clicked.connect(self.close); column.addWidget(cancel)
        row.addLayout(column); row.addStretch(); outer.addLayout(row); outer.addStretch()
        self.cancel_shortcut = QShortcut(QKeySequence('Escape'), self, activated=self.close)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

    def activate(self, action):
        for button in self.buttons: button.setEnabled(False)
        try:
            if action in ('lock', 'switch'):
                seat = os.environ.get('XDG_SEAT_PATH', '')
                if action == 'switch' and not seat.startswith('/org/freedesktop/DisplayManager/Seat'):
                    raise ValueError('A troca de usuário não está disponível nesta sessão. Use Bloquear para proteger o trabalho atual.')
                session_call('org.freedesktop.ScreenSaver', '/ScreenSaver',
                             'org.freedesktop.ScreenSaver', 'Lock')
                if action == 'switch':
                    session_call('org.freedesktop.DisplayManager', seat,
                                 'org.freedesktop.DisplayManager.Seat', 'SwitchToGreeter', system=True)
            elif action == 'logout':
                session_call('org.kde.LogoutPrompt', '/LogoutPrompt',
                             'org.kde.LogoutPrompt', 'promptLogout')
            else:
                command = ['kcmshell6', 'kcm_users'] if action == 'password' else ['linuxbr-task-manager']
                if not shutil.which(command[0]) or not QProcess.startDetached(command[0], command[1:])[0]:
                    raise ValueError('Não foi possível abrir a ferramenta solicitada.')
        except (dbus.DBusException, OSError, ValueError) as error:
            self.error.setText('Não foi possível concluir a ação. ' + str(error)); self.error.show()
            for button in self.buttons: button.setEnabled(True)
            return
        self.close()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and isinstance(self.focusWidget(), QPushButton):
            self.focusWidget().click(); event.accept(); return
        super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv); app.setDesktopFileName('linuxbr-session-actions')
    runtime = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    if not runtime:
        return 1
    lock = QLockFile(runtime + '/linuxbr-session-actions.lock')
    lock.setStaleLockTime(0)
    if not lock.tryLock(0): return 0
    window = SessionActions(); window.showFullScreen(); window.buttons[0].setFocus()
    result = app.exec(); lock.unlock(); return result


if __name__ == '__main__':
    sys.exit(main())
