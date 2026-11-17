"""Monitor de controles de jogo SDL com ajustes de diagnóstico por dispositivo."""
import ctypes
import hashlib
import json
from math import copysign

from PyQt6.QtCore import QProcess, QSettings, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QProgressBar,
                             QPushButton, QSpinBox, QVBoxLayout, QWidget)


AXES = ('Direcional esquerdo, horizontal', 'Direcional esquerdo, vertical',
        'Direcional direito, horizontal', 'Direcional direito, vertical',
        'Gatilho esquerdo', 'Gatilho direito')
BUTTONS = ('A / Cruz', 'B / Círculo', 'X / Quadrado', 'Y / Triângulo', 'Voltar', 'Guia', 'Iniciar',
           'Clique esquerdo', 'Clique direito', 'L1', 'R1', 'Cima', 'Baixo', 'Esquerda', 'Direita',
           'Auxiliar', 'Pá 1', 'Pá 2', 'Pá 3', 'Pá 4', 'Touchpad')
DEFAULT_ZONE = 8


class JoystickGUID(ctypes.Structure):
    _fields_ = [('data', ctypes.c_ubyte * 16)]


class SDLController:
    def __init__(self):
        self.library = ctypes.CDLL('libSDL2-2.0.so.0')
        self.controller = None
        self.started = False
        pointer, integer, string = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
        bind = {
            'SDL_InitSubSystem': (integer, [ctypes.c_uint32]),
            'SDL_QuitSubSystem': (None, [ctypes.c_uint32]),
            'SDL_NumJoysticks': (integer, []),
            'SDL_IsGameController': (integer, [integer]),
            'SDL_GameControllerNameForIndex': (string, [integer]),
            'SDL_JoystickGetDeviceGUID': (JoystickGUID, [integer]),
            'SDL_GameControllerOpen': (pointer, [integer]),
            'SDL_GameControllerClose': (None, [pointer]),
            'SDL_GameControllerGetAttached': (integer, [pointer]),
            'SDL_GameControllerUpdate': (None, []),
            'SDL_GameControllerGetSerial': (string, [pointer]),
            'SDL_GameControllerGetAxis': (ctypes.c_int16, [pointer, integer]),
            'SDL_GameControllerGetButton': (ctypes.c_uint8, [pointer, integer]),
            'SDL_GameControllerRumble': (integer, [pointer, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint32]),
        }
        for name, (result, arguments) in bind.items():
            function = getattr(self.library, name)
            function.restype = result
            function.argtypes = arguments

    def devices(self):
        if not self.started:
            if self.library.SDL_InitSubSystem(0x2000) != 0:
                raise ValueError('O sistema não conseguiu iniciar a leitura de controles.')
            self.started = True
        self.library.SDL_GameControllerUpdate()
        return [(index, (self.library.SDL_GameControllerNameForIndex(index) or b'Gamepad').decode(errors='replace'))
                for index in range(self.library.SDL_NumJoysticks()) if self.library.SDL_IsGameController(index)]

    def open(self, index):
        self.close()
        device = self.library.SDL_GameControllerOpen(index)
        if not device:
            raise ValueError('Não foi possível usar este controle. Atualize a lista e tente novamente.')
        self.controller = device
        serial = self.library.SDL_GameControllerGetSerial(device)
        identifier = bytes(self.library.SDL_JoystickGetDeviceGUID(index).data)
        return hashlib.sha256(identifier + (serial or b'')).hexdigest(), bool(serial)

    def close(self):
        if self.controller:
            self.library.SDL_GameControllerClose(self.controller)
            self.controller = None

    def shutdown(self):
        self.close()
        if self.started:
            self.library.SDL_QuitSubSystem(0x2000)
            self.started = False

    def read(self):
        self.library.SDL_GameControllerUpdate()
        if not self.controller or not self.library.SDL_GameControllerGetAttached(self.controller):
            return None
        return ([self.library.SDL_GameControllerGetAxis(self.controller, index) for index in range(len(AXES))],
                [title for index, title in enumerate(BUTTONS)
                 if self.library.SDL_GameControllerGetButton(self.controller, index)])

    def rumble(self):
        return bool(self.controller and self.library.SDL_GameControllerRumble(
            self.controller, 0x4000, 0x4000, 300) == 0)


def adjusted(value, center, deadzone):
    value = max(-32768, min(32767, value))
    center = max(-32767, min(32766, center))
    fraction = (value - center) / (32767 - center if value >= center else 32768 + center)
    limit = min(0.4, max(0.0, deadzone / 100))
    output = copysign(max(0.0, abs(fraction) - limit) / (1 - limit), fraction)
    return round(100 * output)


class ControllerTest(QWidget):
    def __init__(self, backend=None, settings=None):
        super().__init__()
        self.backend = backend
        self.settings = settings or QSettings('LinuxBR', 'Controles de jogos')
        self.profile = None
        self.centers = [0] * 4
        self.raw = None
        body = QVBoxLayout(self)
        body.setContentsMargins(28, 22, 28, 22)
        body.setSpacing(11)
        title = QLabel('Controles de jogos')
        title.setStyleSheet('font-size:26px;font-weight:600')
        body.addWidget(title)
        description = QLabel('Conecte o controle por USB ou Bluetooth. Mova os direcionais e pressione os botões para conferir a resposta.')
        description.setWordWrap(True)
        body.addWidget(description)
        devices = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setAccessibleName('Controle')
        self.devices.currentIndexChanged.connect(self.select_control)
        devices.addWidget(self.devices, 1)
        devices.addWidget(self.button('Atualizar controles', 'view-refresh', self.refresh))
        body.addLayout(devices)
        axes = QFormLayout()
        self.axes = []
        for index, name in enumerate(AXES):
            meter = QProgressBar()
            meter.setRange(-100 if index < 4 else 0, 100)
            meter.setValue(0)
            meter.setAccessibleName(name)
            axes.addRow(name, meter)
            self.axes.append(meter)
        self.buttons = QLabel('Nenhum')
        self.buttons.setWordWrap(True)
        axes.addRow('Botões pressionados', self.buttons)
        self.zone = QSpinBox()
        self.zone.setRange(0, 40)
        self.zone.setSuffix('%')
        self.zone.setValue(DEFAULT_ZONE)
        axes.addRow('Zona morta dos direcionais', self.zone)
        body.addLayout(axes)
        controls = QHBoxLayout()
        self.rumble_button = self.button('Testar vibração', 'notifications', self.rumble)
        self.center_button = self.button('Capturar repouso', 'crosshairs', self.capture_rest)
        self.save_button = self.button('Salvar perfil', 'document-save', self.save)
        controls.addWidget(self.rumble_button)
        controls.addWidget(self.center_button)
        controls.addWidget(self.save_button)
        controls.addStretch()
        body.addLayout(controls)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Estado do controle')
        body.addWidget(self.status)
        calibration = self.button('Abrir calibração do KDE…', 'configure', self.open_calibration)
        body.addWidget(calibration, 0, Qt.AlignmentFlag.AlignLeft)
        tip = QLabel('O perfil ajusta as leituras mostradas nesta página. Jogos e emuladores também podem oferecer seus próprios ajustes.')
        tip.setWordWrap(True)
        body.addWidget(tip)
        body.addStretch()
        self.timer = QTimer(self)
        self.timer.setInterval(36)
        self.timer.timeout.connect(self.update_state)
        self.update_controls()

    @staticmethod
    def button(title, icon, action):
        button = QPushButton(QIcon.fromTheme(icon), title)
        button.clicked.connect(action)
        return button

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        if self.backend:
            self.backend.shutdown()
        super().hideEvent(event)

    def refresh(self):
        self.timer.stop()
        self.devices.blockSignals(True)
        self.devices.clear()
        try:
            if self.backend is None:
                self.backend = SDLController()
            for index, name in self.backend.devices():
                self.devices.addItem(name, index)
        except (OSError, ValueError, AttributeError):
            self.status.setText('A leitura SDL de controles está indisponível. Abra a calibração do KDE para consultar os dispositivos.')
            self.devices.blockSignals(False)
            self.reset()
            return
        self.devices.blockSignals(False)
        self.select_control()

    def reset(self):
        if self.backend:
            self.backend.close()
        self.profile, self.raw = None, None
        self.centers = [0] * 4
        self.buttons.setText('Nenhum')
        for meter in self.axes:
            meter.setValue(0)
            meter.setFormat('—')
        self.update_controls()

    def select_control(self, *_):
        self.timer.stop()
        self.reset()
        index = self.devices.currentData()
        if index is None:
            self.status.setText('Nenhum controle compatível com o mapeamento SDL foi encontrado.')
            return
        try:
            self.profile, has_serial = self.backend.open(index)
            self.load()
        except ValueError as error:
            self.status.setText(str(error))
            return
        message = 'Perfil individual do dispositivo.' if has_serial else 'Perfil do modelo. Controles iguais sem número de série compartilham os ajustes.'
        self.status.setText(message + ' Mantenha os direcionais em repouso antes de capturar o centro.')
        self.update_state()
        if self.profile:
            self.timer.start()
        self.update_controls()

    def update_controls(self):
        active = self.profile is not None
        self.zone.setEnabled(active)
        self.center_button.setEnabled(active)
        self.rumble_button.setEnabled(active)
        self.save_button.setEnabled(active)

    def update_state(self):
        state = self.backend.read()
        if state is None:
            self.timer.stop()
            self.reset()
            self.status.setText('Controle desconectado. Atualize a lista após reconectar.')
            return
        self.raw, pressed = state
        for index, meter in enumerate(self.axes):
            raw = self.raw[index]
            value = adjusted(raw, self.centers[index], self.zone.value()) if index < 4 else round(100 * max(0, raw) / 32767)
            meter.setValue(value)
            meter.setFormat(f'{value}%  •  bruto {raw}')
        self.buttons.setText(', '.join(pressed) or 'Nenhum')

    def capture_rest(self):
        if self.raw is not None:
            self.centers = self.raw[:4]
            self.update_state()
            self.status.setText('Centro capturado. Mova os direcionais para conferir a resposta e salve o perfil.')

    def load(self):
        raw = self.settings.value('profile/' + self.profile, '', str)
        self.zone.setValue(DEFAULT_ZONE)
        try:
            values = json.loads(raw)
            centers = values['centers']
            if len(centers) == 4 and all(type(value) is int and -32768 <= value <= 32767 for value in centers):
                self.centers = centers
                self.zone.setValue(int(values['zone']))
        except (ValueError, TypeError, KeyError):
            pass

    def save(self):
        if not self.profile:
            return
        self.settings.setValue('profile/' + self.profile, json.dumps(dict(centers=self.centers, zone=self.zone.value())))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            self.status.setText('Não foi possível salvar o perfil.')
        else:
            self.status.setText('Perfil do controle salvo. Os ajustes serão carregados ao selecionar o dispositivo.')

    def rumble(self):
        self.status.setText('Teste curto de vibração enviado.' if self.backend and self.backend.rumble()
                            else 'Este controle ou a conexão atual não oferece vibração pelo SDL.')

    def open_calibration(self):
        if not QProcess.startDetached('/usr/bin/kcmshell6', ['kcm_gamecontroller'])[0]:
            self.status.setText('A calibração do KDE está indisponível nesta sessão.')
