"""Local camera preview and microphone level test."""
import math
import struct

from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QAudio, QAudioFormat, QAudioSource, QCamera, QMediaCaptureSession, QMediaDevices
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


def microphone_level(data, sample_format):
    layouts = {QAudioFormat.SampleFormat.UInt8: ('B', 128, 128),
               QAudioFormat.SampleFormat.Int16: ('h', 0, 32768),
               QAudioFormat.SampleFormat.Int32: ('i', 0, 2147483648),
               QAudioFormat.SampleFormat.Float: ('f', 0, 1)}
    if sample_format not in layouts:
        return 0
    code, offset, scale = layouts[sample_format]
    size = struct.calcsize('=' + code)
    data = data[:len(data) - len(data) % size]
    if not data:
        return 0
    average = sum(((sample - offset) / scale) ** 2 for sample, in struct.iter_unpack('=' + code, data))
    rms = math.sqrt(average / (len(data) // size))
    return min(100, round(rms * 100)) if math.isfinite(rms) else 0


class MediaTest(QWidget):
    def __init__(self):
        super().__init__()
        self.camera = None
        self.audio = None
        self.session = QMediaCaptureSession(self)
        self.devices = QMediaDevices(self)
        self.devices.videoInputsChanged.connect(self.refresh)
        self.devices.audioInputsChanged.connect(self.refresh)
        body = QVBoxLayout(self)
        title = QLabel('Testar câmera e microfone')
        title.setStyleSheet('font-size:26px;font-weight:600')
        body.addWidget(title)
        note = QLabel('Escolha a câmera e o microfone. A prévia e o medidor ficam nesta janela.')
        note.setWordWrap(True)
        body.addWidget(note)
        form = QFormLayout()
        self.cameras = QComboBox()
        self.inputs = QComboBox()
        form.addRow('&Câmera', self.cameras)
        form.addRow('&Microfone', self.inputs)
        body.addLayout(form)
        self.preview = QVideoWidget()
        self.preview.setMinimumHeight(180)
        self.session.setVideoOutput(self.preview)
        body.addWidget(self.preview, 1)
        self.level = QProgressBar()
        self.level.setAccessibleName('Nível do microfone')
        self.level.setRange(0, 100)
        self.level.setValue(0)
        self.level_label = QLabel('Nível do microfone')
        body.addWidget(self.level_label)
        body.addWidget(self.level)
        row = QHBoxLayout()
        self.start_button = QPushButton('Iniciar teste')
        self.start_button.clicked.connect(self.start)
        row.addWidget(self.start_button)
        self.stop_button = QPushButton('Encerrar teste')
        self.stop_button.clicked.connect(self.stop)
        row.addWidget(self.stop_button)
        body.addLayout(row)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        self.refresh()

    def refresh(self):
        self.stop()
        for combo, devices, default in (
            (self.cameras, self.devices.videoInputs(), self.devices.defaultVideoInput()),
            (self.inputs, self.devices.audioInputs(), self.devices.defaultAudioInput()),
        ):
            selected = combo.currentData()
            selected_id = (selected or default).id()
            combo.clear()
            for index, device in enumerate(devices):
                combo.addItem(device.description(), device)
                if device.id() == selected_id:
                    combo.setCurrentIndex(index)
            if not devices:
                combo.addItem('Nenhum dispositivo disponível')
            combo.setEnabled(bool(devices))
        available = self.available()
        self.preview.setVisible(self.cameras.currentData() is not None)
        self.level.setVisible(self.inputs.currentData() is not None)
        self.level_label.setVisible(self.inputs.currentData() is not None)
        self.start_button.setEnabled(available)
        self.status.setText('Pronto para testar.' if available else 'Nenhuma câmera ou entrada de áudio foi encontrada.')

    def available(self):
        return self.cameras.currentData() is not None or self.inputs.currentData() is not None

    def start(self):
        self.status.setText('Teste em andamento.')
        camera_device = self.cameras.currentData()
        if camera_device is not None:
            self.camera = QCamera(camera_device, self)
            self.camera.errorOccurred.connect(lambda _, message: self.status.setText('Câmera: ' + message))
            self.session.setCamera(self.camera)
            self.camera.start()
        microphone = self.inputs.currentData()
        if microphone is not None:
            self.audio = QAudioSource(microphone, self)
            self.audio.stateChanged.connect(self.audio_state_changed)
            source = self.audio.start()
            if source is not None:
                sample_format = self.audio.format().sampleFormat()
                source.readyRead.connect(lambda: self.level.setValue(microphone_level(bytes(source.readAll()), sample_format)))
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.cameras.setEnabled(False)
        self.inputs.setEnabled(False)

    def audio_state_changed(self, state):
        if state == QAudio.State.StoppedState and self.audio and self.audio.error() != QAudio.Error.NoError:
            self.status.setText('Não foi possível acessar o microfone selecionado.')

    def stop(self):
        if self.camera:
            self.camera.stop()
            self.session.setCamera(None)
            self.camera.deleteLater()
            self.camera = None
        if self.audio:
            self.audio.stop()
            self.audio.deleteLater()
            self.audio = None
        self.level.setValue(0)
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(self.available())
        self.cameras.setEnabled(self.cameras.currentData() is not None)
        self.inputs.setEnabled(self.inputs.currentData() is not None)
        self.status.setText('Teste encerrado.')

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)
