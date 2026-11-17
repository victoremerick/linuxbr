"""Edit KWin's per-device libinput properties and exercise the current settings."""
import re
import sys

import dbus
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QIcon, QPainter
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QPushButton, QVBoxLayout, QWidget)

from file_tools import plain_label
from visual_style import BUTTONS


SERVICE = 'org.kde.KWin'
DEVICE_PATH = '/org/kde/KWin/InputDevice'
DEVICE = SERVICE + '.InputDevice'
MANAGER = DEVICE + 'Manager'
PROPERTIES = 'org.freedesktop.DBus.Properties'
TIMEOUT = 3
TOGGLES = {
    'tapToClick': ('Tocar para clicar', 'tapFingerCount', 'tapToClickEnabledByDefault'),
    'tapAndDrag': ('Tocar e arrastar', 'tapFingerCount', 'tapAndDragEnabledByDefault'),
    'tapDragLock': ('Continuar o arraste ao levantar o dedo', 'tapFingerCount', 'tapDragLockEnabledByDefault'),
    'lmrTapButtonMap': ('Toque de dois dedos para clique do meio', 'supportsLmrTapButtonMap', 'lmrTapButtonMapEnabledByDefault'),
    'naturalScroll': ('Rolar acompanhando o movimento dos dedos', 'supportsNaturalScroll', 'naturalScrollEnabledByDefault'),
    'disableWhileTyping': ('Evitar toques enquanto digita', 'supportsDisableWhileTyping', 'disableWhileTypingEnabledByDefault'),
}
SCROLL = {
    'scrollTwoFinger': ('Dois dedos', 'supportsScrollTwoFinger', 'scrollTwoFingerEnabledByDefault'),
    'scrollEdge': ('Borda do touchpad', 'supportsScrollEdge', 'scrollEdgeEnabledByDefault'),
    'scrollOnButtonDown': ('Ao manter o botão de rolagem pressionado', 'supportsScrollOnButtonDown', 'scrollOnButtonDownEnabledByDefault'),
}


def identity(device):
    return tuple(device[key] for key in ('name', 'vendor', 'product'))


def supported(device, options):
    return {key: item for key, item in options.items() if key in device and bool(device.get(item[1]))}


def scroll_method(device, defaults=False):
    return next((key for key, (_, _, original) in supported(device, SCROLL).items()
                 if device.get(original if defaults else key)), '')


class Touchpads:
    def __init__(self, bus):
        self.bus = bus

    def interface(self, name=''):
        if name and not re.fullmatch(r'event[0-9]+', name):
            raise ValueError('O identificador do touchpad não é válido.')
        return dbus.Interface(self.bus.get_object(SERVICE, DEVICE_PATH + ('/' + name if name else '')), PROPERTIES)

    def list(self):
        names = self.interface().Get(MANAGER, 'devicesSysNames', timeout=TIMEOUT)
        devices = {}
        for name in map(str, names):
            try:
                settings = self.read(name)
            except dbus.DBusException:
                continue  # A device can vanish between listing and reading it.
            if settings.get('touchpad'):
                devices[name] = settings
        return devices

    def read(self, name):
        return self.interface(name).GetAll(DEVICE, timeout=TIMEOUT)

    def write(self, interface, key, value):
        interface.Set(DEVICE, key, dbus.Boolean(value), timeout=TIMEOUT)
        if bool(interface.Get(DEVICE, key, timeout=TIMEOUT)) != value:
            raise ValueError('O touchpad recusou a alteração.')

    def apply(self, name, expected, values, mode):
        before = self.read(name)
        toggles = supported(before, TOGGLES)
        current_mode = scroll_method(before)
        if not before.get('touchpad') or identity(before) != expected:
            raise ValueError('O touchpad foi substituído. Atualize a lista de dispositivos.')
        if (values.keys() != toggles.keys() or any(type(value) is not bool for value in values.values())
                or (mode != '' and mode not in supported(before, SCROLL))):
            raise ValueError('O touchpad não oferece todos os ajustes selecionados.')
        interface = self.interface(name)
        changed = []
        try:
            for key, value in values.items():
                if bool(before[key]) != value:
                    changed.append(key)
                    self.write(interface, key, value)
            if mode != current_mode:
                changed.append(mode or current_mode)
                self.write(interface, mode or current_mode, bool(mode))
        except (ValueError, dbus.DBusException) as error:
            try:
                if mode != current_mode and changed and changed[-1] == (mode or current_mode):
                    touched = changed.pop()
                    self.write(interface, current_mode or touched, bool(current_mode))
                for key in reversed(changed):
                    self.write(interface, key, bool(before[key]))
            except (ValueError, dbus.DBusException) as rollback:
                raise ValueError('O touchpad pode ter sido desconectado. Confira os ajustes aplicados.') from rollback
            raise ValueError('O touchpad recusou as alterações. As preferências anteriores foram mantidas.') from error


class Practice(QWidget):
    def __init__(self, status):
        super().__init__()
        self.status = status
        self.setMinimumHeight(116)
        self.setAccessibleName('Área para experimentar cliques, arraste, rolagem ou pinça')
        self.origin = None
        self.offset = QPoint()
        self.zoom = 1.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.alternateBase())
        painter.setPen(palette.highlight().color())
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -3, -3), 10, 10)
        center = self.rect().center() + self.offset
        radius = round(18 * self.zoom)
        painter.setBrush(palette.highlight())
        painter.drawEllipse(center, radius, radius)
        painter.setPen(palette.highlightedText().color())
        painter.drawText(center.x() - 3, center.y() + 4, '↕')

    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        self.offset = QPoint()
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.origin is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        movement = event.position().toPoint() - self.origin
        self.offset = QPoint(min(120, max(-120, movement.x())), min(35, max(-35, movement.y())))
        self.update()

    def mouseReleaseEvent(self, event):
        button = {Qt.MouseButton.LeftButton: 'principal', Qt.MouseButton.RightButton: 'secundário',
                  Qt.MouseButton.MiddleButton: 'do meio'}.get(event.button())
        if button:
            self.status.setText('Arraste detectado.' if self.offset.manhattanLength() >= QApplication.startDragDistance()
                                else 'Clique ' + button + ' detectado.')
        self.origin = None
        event.accept()

    def wheelEvent(self, event):
        movement = event.pixelDelta() or event.angleDelta()
        if movement.x() or movement.y():
            vertical = abs(movement.y()) >= abs(movement.x())
            direction = ('para cima' if movement.y() > 0 else 'para baixo') if vertical else (
                        'para a esquerda' if movement.x() > 0 else 'para a direita')
            self.status.setText('Rolagem ' + direction + ' detectada.')
            self.offset = QPoint(0, -18 if movement.y() > 0 else 18) if vertical else QPoint(
                          -50 if movement.x() > 0 else 50, 0)
            self.update()
        event.accept()

    def event(self, event):
        if event.type() == QEvent.Type.NativeGesture and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.zoom = min(2, max(0.5, self.zoom * (1 + event.value())))
            self.status.setText(f'Pinça detectada. Ampliação de {self.zoom:.0%}.')
            self.update()
            return True
        return super().event(event)


class TouchpadDialog(QDialog):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.setWindowTitle('Configurar e testar o touchpad')
        self.setWindowIcon(QIcon.fromTheme('input-touchpad'))
        self.setMinimumWidth(580)
        layout = QVBoxLayout(self)
        layout.addWidget(plain_label('Os ajustes de toque e rolagem são salvos pelo Plasma para o dispositivo selecionado.'))
        header = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setAccessibleName('Touchpad conectado')
        self.devices.currentIndexChanged.connect(self.select)
        header.addWidget(self.devices, 1)
        reload_button = QPushButton(QIcon.fromTheme('view-refresh'), 'Atualizar lista')
        reload_button.clicked.connect(self.refresh)
        header.addWidget(reload_button)
        layout.addLayout(header)
        self.form_container = QWidget()
        form = QFormLayout(self.form_container)
        self.toggles = {}
        for key, (label, _, _) in TOGGLES.items():
            toggle = QCheckBox(label)
            self.toggles[key] = toggle
            form.addRow(toggle)
        self.scroll = QComboBox()
        form.addRow('Modo de rolagem', self.scroll)
        layout.addWidget(self.form_container)
        self.status = plain_label('')
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.defaults = QPushButton('Carregar padrões do dispositivo')
        self.defaults.clicked.connect(lambda: self.populate(True))
        controls.addWidget(self.defaults)
        controls.addStretch()
        self.apply = QPushButton(QIcon.fromTheme('dialog-ok-apply'), 'Aplicar')
        self.apply.clicked.connect(self.store)
        controls.addWidget(self.apply)
        layout.addLayout(controls)
        layout.addWidget(plain_label('Experimente um clique, arraste, rolagem ou pinça dentro da área.'))
        practice_status = plain_label('Aguardando interação.')
        layout.addWidget(Practice(practice_status))
        layout.addWidget(practice_status)
        close = QPushButton('Fechar')
        close.clicked.connect(self.reject)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self):
        selected = self.devices.currentData()
        message = ''
        try:
            self.connected = self.backend.list()
        except dbus.DBusException:
            self.connected = {}
            message = 'Os ajustes por dispositivo precisam de uma sessão Plasma Wayland com suporte a libinput.'
        self.devices.blockSignals(True)
        self.devices.clear()
        for name, device in self.connected.items():
            self.devices.addItem(f'{device["name"]} · {name}', name)
        index = self.devices.findData(selected)
        if index >= 0:
            self.devices.setCurrentIndex(index)
        self.devices.blockSignals(False)
        self.select()
        self.status.setText(message or ('' if self.connected else 'Nenhum touchpad compatível conectado.'))

    def select(self):
        device = self.connected.get(self.devices.currentData())
        self.form_container.setEnabled(bool(device))
        self.apply.setEnabled(bool(device))
        self.defaults.setEnabled(bool(device))
        if device:
            self.populate()

    def populate(self, defaults=False):
        device = self.connected[self.devices.currentData()]
        available = supported(device, TOGGLES)
        for key, control in self.toggles.items():
            control.setEnabled(key in available)
            control.setChecked(bool(device.get(TOGGLES[key][2] if defaults else key)))
        self.scroll.clear()
        self.scroll.addItem('Desativada', '')
        for key, (label, _, _) in supported(device, SCROLL).items():
            self.scroll.addItem(label, key)
        self.scroll.setCurrentIndex(self.scroll.findData(scroll_method(device, defaults)))
        self.scroll.setEnabled(self.scroll.count() > 1)
        self.status.setText('Padrões carregados. Aplique para atualizar o dispositivo.' if defaults else '')

    def store(self):
        name = self.devices.currentData()
        device = self.connected[name]
        try:
            self.backend.apply(name, identity(device), {key: self.toggles[key].isChecked()
                               for key in supported(device, TOGGLES)}, self.scroll.currentData())
            self.connected[name] = self.backend.read(name)
            self.populate()
            self.status.setText('Preferências atualizadas. Experimente os gestos na área abaixo.')
        except (ValueError, dbus.DBusException) as error:
            self.status.setText(str(error))


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(BUTTONS)
    app.setDesktopFileName('linuxbr-touchpad')
    TouchpadDialog(Touchpads(dbus.SessionBus())).exec()
    return 0


if __name__ == '__main__':
    sys.exit(main())
