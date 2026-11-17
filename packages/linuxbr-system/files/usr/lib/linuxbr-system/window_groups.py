"""Capture and restore windows on the current Plasma desktop through KWin."""
import json
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

from PyQt6.QtCore import QEventLoop, QObject, QTimer, pyqtClassInfo, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusMessage
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QHBoxLayout, QInputDialog, QMessageBox, QPushButton, QVBoxLayout

from file_tools import message, plain_label
import quick_commands
from visual_style import BUTTONS


def location():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/window-groups.json'


def groups():
    try:
        value = json.loads(location().read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError('O arquivo de grupos de janelas é inválido.')
    return value


def plan(rows, available):
    if not isinstance(rows, list):
        raise ValueError('Posições de janelas inválidas.')
    result = []
    for entry in rows[:50]:
        if not isinstance(entry, dict):
            continue
        app, monitor = entry.get('application'), entry.get('monitor')
        if (not isinstance(app, str) or app not in available or app == 'linuxbr-window-groups.desktop'
                or not quick_commands.APP_ID.fullmatch(app)
                or not isinstance(monitor, str) or len(monitor) > 150 or type(entry.get('minimized')) is not bool
                or any(type(entry.get(key)) is not int for key in ('x', 'y', 'width', 'height', 'maximize'))):
            continue
        if not (0 < entry['width'] <= 16384 and 0 < entry['height'] <= 16384
                and -32768 <= entry['x'] <= 32768 and -32768 <= entry['y'] <= 32768
                and 0 <= entry['maximize'] <= 3):
            continue
        result.append({key: entry[key] for key in ('application', 'monitor', 'x', 'y', 'width', 'height', 'maximize', 'minimized')})
    return result


@pyqtClassInfo('D-Bus Interface', 'org.linuxbr.WindowGroups')
class Receiver(QObject):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.payload = None

    @pyqtSlot(str)
    def complete(self, value):
        if len(value) <= 64000 and self.payload is None:
            self.payload = value
            self.finished.emit()


def call(bus, path, interface, method, arguments, timeout=3500):
    request = QDBusMessage.createMethodCall('org.kde.KWin', path, interface, method)
    request.setArguments(arguments)
    result = bus.call(request, timeout=timeout)
    if result.type() == QDBusMessage.MessageType.ErrorMessage:
        raise ValueError('O serviço de janelas do KWin não respondeu: ' + result.errorMessage())
    return result.arguments()


def query_windows(layout):
    suffix = uuid4().hex
    plugin = 'linuxbr-window-groups-' + suffix
    service = 'org.linuxbr.WindowGroups.i' + suffix
    bus = QDBusConnection.sessionBus()
    receiver = Receiver()
    route = '/WindowGroups'
    connection_flags = QDBusConnection.RegisterOption.ExportAllSlots
    if not bus.registerService(service):
        raise ValueError('Não foi possível abrir o canal de resposta do KWin.')
    if not bus.registerObject(route, receiver, connection_flags):
        bus.unregisterService(service)
        raise ValueError('Já existe uma consulta de janelas em andamento.')
    developer = 'org.kde.kwin.Scripting'
    script_id = -1
    loop = QEventLoop()
    receiver.finished.connect(loop.quit)
    try:
        with tempfile.TemporaryDirectory(prefix='linuxbr-window-groups-') as temporary:
            path = Path(temporary) / 'apply.js'
            source = Path(__file__).with_name('window-groups-kwin.js').read_text(encoding='utf-8')
            path.write_text('const linuxbrReceiver = ' + json.dumps(service) +
                            ';\nconst linuxbrPlan = ' + json.dumps(layout) + ';\n' + source, encoding='utf-8')
            script_id, = call(bus, '/Scripting', developer, 'loadScript', [str(path), plugin])
            if script_id < 0:
                raise ValueError('O KWin não carregou o grupo de janelas.')
            call(bus, '/Scripting/Script' + str(script_id), 'org.kde.kwin.Script', 'run', [])
            if receiver.payload is None:
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(loop.quit)
                timer.start(3500)
                loop.exec()
            if receiver.payload is None:
                raise ValueError('O KWin não retornou as posições solicitadas.')
            return json.loads(receiver.payload)
    finally:
        if script_id >= 0:
            try:
                call(bus, '/Scripting', developer, 'unloadScript', [plugin], timeout=1000)
            except ValueError:
                pass
        bus.unregisterObject(route)
        bus.unregisterService(service)


class WindowGroups(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Grupos de janelas')
        self.setWindowIcon(QIcon.fromTheme('window-duplicate'))
        self.resize(640, 275)
        body = QVBoxLayout(self)
        body.setContentsMargins(20, 18, 20, 18)
        body.addWidget(plain_label('Salve os aplicativos e posições das janelas na área ativa e restaure o grupo em outra sessão. Os aplicativos abrem pelos atalhos instalados.'))
        self.saved = QComboBox()
        self.saved.setAccessibleName('Grupos salvos')
        body.addWidget(self.saved)
        buttons = QHBoxLayout()
        for name, control in [('Salvar janelas atuais…', self.capture), ('Restaurar grupo', self.restore),
                              ('Remover grupo…', self.remove), ('Fechar', self.reject)]:
            button = QPushButton(name)
            button.clicked.connect(control)
            button.setAutoDefault(False)
            buttons.addWidget(button)
        body.addLayout(buttons)
        self.status = plain_label('')
        body.addWidget(self.status)
        body.addStretch()
        self.refresh()

    def refresh(self, selected=''):
        self.saved.clear()
        self.saved.addItems(sorted(groups(), key=str.casefold))
        if selected:
            self.saved.setCurrentText(selected)

    def capture(self):
        name, accepted = QInputDialog.getText(self, 'Salvar grupo de janelas', 'Nome')
        if not accepted:
            return
        name = name.strip()
        if not name or len(name) > 80 or not all(char.isprintable() for char in name):
            self.status.setText('Informe um nome de até 80 caracteres.')
            return
        try:
            saved = groups()
            if name in saved and QMessageBox.question(self, 'Salvar grupo', 'Substituir o grupo existente?') != QMessageBox.StandardButton.Yes:
                return
            snapshot = plan(query_windows([]), quick_commands.apps())
            if not snapshot:
                raise ValueError('Nenhuma janela da área ativa corresponde a um aplicativo conhecido.')
            saved[name] = snapshot
            quick_commands.atomic_write(location(), json.dumps(saved, ensure_ascii=False))
            self.refresh(name)
            self.status.setText(f'{len(snapshot)} janelas gravadas no grupo.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def restore(self):
        name = self.saved.currentText()
        if not name:
            return
        self.setEnabled(False)
        try:
            entries = plan(groups()[name], quick_commands.apps())
            if not entries:
                raise ValueError('Os aplicativos deste grupo não estão disponíveis.')
            pending = query_windows(entries)
            if pending:
                launch_errors = quick_commands.execute({'actions': [('app', app) for app in pending]})
                attempts = 0
                while pending and attempts < 4 and not launch_errors:
                    loop = QEventLoop()
                    QTimer.singleShot(1200, loop.quit)
                    loop.exec()
                    pending = query_windows(entries)
                    attempts += 1
            self.status.setText(f'{len(entries) - len(pending)} janelas restauradas.'
                                + (f' {len(pending)} janelas ainda dependem da abertura do aplicativo.' if pending else ''))
        except (OSError, ValueError, KeyError) as error:
            self.status.setText(str(error))
        finally:
            self.setEnabled(True)

    def remove(self):
        name = self.saved.currentText()
        if not name or QMessageBox.question(self, 'Remover grupo', 'Remover o grupo selecionado?') != QMessageBox.StandardButton.Yes:
            return
        try:
            saved = groups()
            saved.pop(name, None)
            quick_commands.atomic_write(location(), json.dumps(saved, ensure_ascii=False))
            self.refresh()
            self.status.setText('Grupo removido.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-window-groups')
    app.setStyleSheet(BUTTONS)
    try:
        WindowGroups().exec()
    except (OSError, ValueError) as error:
        message(None, 'Grupos de janelas', str(error), warning=True)
        sys.exit(1)
