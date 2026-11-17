"""Playback and microphone controls for a task selected in Plasma."""
from pathlib import Path
import json
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QCheckBox, QDialog, QFormLayout, QHBoxLayout, QPushButton, QSlider, QVBoxLayout

from audio import pactl, percent
from file_tools import plain_label


OPERATIONS = {
    'sink-inputs': 'sink-input',
    'source-outputs': 'source-output',
}


def owned_process(pid, proc=Path('/proc')):
    if not isinstance(pid, int) or not 1 < pid < 4194304:
        return False
    try:
        return (proc / str(pid)).stat().st_uid == os.getuid()
    except OSError:
        return False


def belongs(candidate, target, proc=Path('/proc')):
    for _ in range(14):
        if not owned_process(candidate, proc):
            return False
        if candidate == target:
            return True
        try:
            lines = (proc / str(candidate) / 'status').read_text(encoding='utf-8').splitlines()
            candidate = int(next(line[5:].strip() for line in lines if line.startswith('PPid:')))
        except (OSError, ValueError, StopIteration):
            return False
    return False


def streams(pid):
    if not owned_process(pid):
        raise ValueError('A janela já foi fechada ou pertence a outra conta.')
    result = []
    for direction in OPERATIONS:
        rows = json.loads(pactl('-f', 'json', 'list', direction))
        for row in rows:
            properties = row.get('properties', {})
            try:
                candidate = int(properties.get('application.process.id', ''))
                index = int(row['index'])
            except (KeyError, TypeError, ValueError):
                continue
            if belongs(candidate, pid):
                result.append((direction, index, properties, bool(row.get('mute')), percent(row.get('volume'))))
    return result


def apply(pid, direction, index, operation, value):
    if not any(item[:2] == (direction, index) for item in streams(pid)):
        raise ValueError('O fluxo de áudio mudou. Atualize a lista.')
    if operation == 'mute' and type(value) is bool:
        argument = '1' if value else '0'
    elif operation == 'volume' and type(value) is int and 0 <= value <= 100:
        argument = str(value) + '%'
    else:
        raise ValueError('Controle inválido.')
    return pactl('set-' + OPERATIONS[direction] + '-' + operation, str(index), argument)


class AppAudio(QDialog):
    def __init__(self, pid):
        super().__init__()
        self.pid = pid
        self.setWindowTitle('Mídia e microfone do aplicativo')
        self.setWindowIcon(QIcon.fromTheme('audio-volume-high'))
        self.resize(650, 320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(plain_label('Ajuste os fluxos de reprodução e captura da janela selecionada.'))
        self.controls = QFormLayout()
        layout.addLayout(self.controls, 1)
        self.status = plain_label('')
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch()
        refresh = QPushButton(QIcon.fromTheme('view-refresh'), 'Atualizar')
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        close = QPushButton('Fechar')
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        while self.controls.rowCount():
            self.controls.removeRow(0)
        try:
            entries = streams(self.pid)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.status.setText(str(error))
            return
        for direction, index, props, muted, level in entries:
            label = 'Reprodução' if direction == 'sink-inputs' else 'Microfone'
            title = str(props.get('media.name') or props.get('application.name') or '')[:100]
            row = QHBoxLayout()
            volume = QSlider(Qt.Orientation.Horizontal)
            volume.setRange(0, 100)
            volume.setValue(level)
            volume.setAccessibleName('Volume de ' + label.lower())
            volume.sliderReleased.connect(lambda direction=direction, index=index, slider=volume:
                                          self.set_value(direction, index, 'volume', slider.value()))
            row.addWidget(volume, 1)
            mute = QCheckBox('Silenciar')
            mute.setChecked(muted)
            mute.toggled.connect(lambda checked, direction=direction, index=index:
                                 self.set_value(direction, index, 'mute', checked))
            row.addWidget(mute)
            self.controls.addRow(plain_label(f'{label} — {title}'), row)
        self.status.setText('Controles atualizados.' if entries else 'O aplicativo está sem fluxos de áudio ou microfone neste momento.')

    def set_value(self, direction, index, operation, value):
        try:
            apply(self.pid, direction, index, operation, value)
            self.status.setText('Áudio atualizado.')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.refresh()
            self.status.setText(str(error))
