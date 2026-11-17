"""Leitura local com Speech Dispatcher e eSpeak NG."""
import json
import os
import select
import sys
import threading

from PyQt6.QtCore import QProcess, Qt, QTimer
from PyQt6.QtGui import QClipboard, QIcon
from PyQt6.QtWidgets import (QApplication, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                             QPushButton, QSlider, QVBoxLayout, QWidget)


MAX_TEXT = 10000


def speech_worker():
    """Privacidade da leitura e comandos de controle ficam no pipe da ferramenta."""
    import speechd

    request = json.loads(sys.stdin.buffer.readline(MAX_TEXT * 8 + 4096))
    text, rate = request['text'], request['rate']
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_TEXT or not -50 <= rate <= 60:
        raise ValueError('Leitura inválida.')

    done = threading.Event()
    client = speechd.SSIPClient('LinuxBR')
    client.set_output_module('espeak-ng')
    client.set_language('pt-br')
    client.set_rate(rate)

    def callback(_, **kwargs):
        done.set()

    try:
        client.speak(text, callback=callback,
                     event_types=(speechd.CallbackType.END, speechd.CallbackType.CANCEL))
        print('ready', flush=True)
        buffered = b''
        operations = {b'pause': client.pause, b'resume': client.resume}
        while not done.is_set():
            readable, _, _ = select.select([0], [], [], 0.12)
            if not readable:
                continue
            chunk = os.read(0, 1024)
            if not chunk:
                break
            buffered += chunk
            while b'\n' in buffered:
                line, buffered = buffered.split(b'\n', 1)
                if line == b'stop':
                    return
                if line in operations:
                    operations[line]()
    finally:
        client.cancel()
        client.close()


class ReadAloud(QWidget):
    def __init__(self):
        super().__init__()
        self.speaker = None
        self.paused = False
        self.stopping = False
        self.ready = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)
        title = QLabel('Leitura em voz alta')
        title.setStyleSheet('font-size:26px;font-weight:600')
        layout.addWidget(title)
        introduction = QLabel('Selecione ou copie texto em outro aplicativo. Confira o conteúdo antes de iniciar a leitura.')
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        sources = QHBoxLayout()
        self.selection = QPushButton(QIcon.fromTheme('edit-select-text'), 'Usar seleção')
        self.selection.clicked.connect(lambda: self.paste(QClipboard.Mode.Selection))
        sources.addWidget(self.selection)
        self.copy = QPushButton(QIcon.fromTheme('edit-paste'), 'Usar texto copiado')
        self.copy.clicked.connect(lambda: self.paste(QClipboard.Mode.Clipboard))
        sources.addWidget(self.copy)
        sources.addStretch()
        layout.addLayout(sources)
        self.text = QPlainTextEdit()
        self.text.setAccessibleName('Texto para leitura')
        self.text.setPlaceholderText('Digite, selecione ou cole o texto para ouvir em português.')
        self.text.textChanged.connect(self.update_controls)
        layout.addWidget(self.text, 1)
        options = QFormLayout()
        self.rate = QSlider(Qt.Orientation.Horizontal)
        self.rate.setRange(-50, 60)
        self.rate.setAccessibleName('Velocidade da leitura')
        options.addRow('&Velocidade', self.rate)
        self.rate_info = QLabel('Normal')
        self.rate.valueChanged.connect(lambda value: self.rate_info.setText(f'{value:+d}' if value else 'Normal'))
        options.addRow('Ritmo', self.rate_info)
        layout.addLayout(options)
        actions = QHBoxLayout()
        self.start = QPushButton(QIcon.fromTheme('media-playback-start'), 'Ler em voz alta')
        self.start.clicked.connect(self.play)
        actions.addWidget(self.start)
        self.pause = QPushButton(QIcon.fromTheme('media-playback-pause'), 'Pausar')
        self.pause.clicked.connect(self.toggle_pause)
        actions.addWidget(self.pause)
        self.stop = QPushButton(QIcon.fromTheme('media-playback-stop'), 'Parar')
        self.stop.clicked.connect(self.stop_reading)
        actions.addWidget(self.stop)
        actions.addStretch()
        layout.addLayout(actions)
        self.status = QLabel('Voz local em português do Brasil.')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Estado da leitura')
        layout.addWidget(self.status)
        self.update_controls()

    def update_controls(self):
        busy = self.speaker is not None
        supported = QApplication.clipboard().supportsSelection()
        self.selection.setEnabled(supported and not busy)
        if not supported:
            self.selection.setToolTip('Use texto copiado nesta sessão.')
        self.copy.setEnabled(not busy)
        self.text.setReadOnly(busy)
        self.rate.setEnabled(not busy)
        self.start.setEnabled(not busy and 1 <= len(self.text.toPlainText().strip()) <= MAX_TEXT)
        self.pause.setEnabled(self.ready and not self.stopping)
        self.stop.setEnabled(busy and not self.stopping)

    def paste(self, mode):
        clipboard = QApplication.clipboard().text(mode)
        if clipboard.strip():
            self.text.setPlainText(clipboard[:MAX_TEXT])
            self.status.setText('Texto carregado. Selecione Ler em voz alta para ouvir.')
        else:
            self.status.setText('A seleção está vazia. Você pode copiar ou digitar um texto.')

    def play(self):
        text = self.text.toPlainText().strip()
        if self.speaker or not 1 <= len(text) <= MAX_TEXT:
            return
        self.speaker = child = QProcess(self)
        self.ready = self.stopping = self.paused = False
        payload = json.dumps(dict(text=text, rate=self.rate.value()), ensure_ascii=False).encode() + b'\n'
        child.started.connect(lambda: child.write(payload))
        child.readyReadStandardOutput.connect(lambda: self.speech_event(child))
        child.finished.connect(lambda code, _: self.finished(child, code))
        child.errorOccurred.connect(
            lambda error: self.finished(child, 1) if error == QProcess.ProcessError.FailedToStart else None)
        child.start(sys.executable, [__file__])
        self.status.setText('Preparando a voz local…')
        self.update_controls()

    def speech_event(self, child):
        if self.speaker is child and child.canReadLine():
            if bytes(child.readLine()).strip() == b'ready' and not self.stopping:
                self.ready = True
                self.status.setText('Leitura em andamento.')
                self.update_controls()

    def toggle_pause(self):
        if self.ready and not self.stopping:
            self.paused = not self.paused
            self.speaker.write(b'pause\n' if self.paused else b'resume\n')
            self.pause.setText('Continuar' if self.paused else 'Pausar')
            self.status.setText('Leitura pausada.' if self.paused else 'Leitura em andamento.')

    def stop_reading(self):
        if self.speaker and not self.stopping:
            self.stopping = True
            child = self.speaker
            child.write(b'stop\n')
            QTimer.singleShot(1500, lambda: child.kill() if self.speaker is child else None)
            self.update_controls()

    def finished(self, child, code):
        if self.speaker is not child:
            return
        self.speaker = None
        self.ready = False
        self.pause.setText('Pausar')
        self.status.setText('Leitura interrompida.' if self.stopping else 'Leitura concluída.' if code == 0
                            else 'Não foi possível usar a voz local. Confira o Speech Dispatcher e a saída de áudio.')
        self.stopping = False
        self.update_controls()
        child.deleteLater()

    def hideEvent(self, event):
        self.stop_reading()
        super().hideEvent(event)


if __name__ == '__main__':
    try:
        speech_worker()
    except Exception:
        raise SystemExit(1)
