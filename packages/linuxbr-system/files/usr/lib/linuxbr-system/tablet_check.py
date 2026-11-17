"""Exercise position and pressure from a tablet using the regular graphical session."""
import sys

from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QIcon, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QProgressBar,
                             QPushButton, QVBoxLayout, QWidget)


class Pad(QWidget):
    def __init__(self, report):
        super().__init__()
        self.report = report
        self.traces = []
        self.previous = None
        self.setMinimumSize(330, 230)
        self.setTabletTracking(True)
        self.setAccessibleName('Área de teste da caneta')

    def tabletEvent(self, event):
        point = event.position()
        pressure = min(1., max(0., event.pressure()))
        self.report(f'Posição na área · {point.x():.0f}, {point.y():.0f} · Pressão · {pressure:.0%}', pressure)
        if pressure > 0:
            if self.previous is not None:
                self.traces.append((self.previous, point, 1 + pressure * 8))
                if len(self.traces) > 5000:
                    del self.traces[:1000]
            self.previous = point
        else:
            self.previous = None
        event.accept()
        self.update()

    def reset(self):
        self.traces.clear()
        self.previous = None
        self.update()

    def paintEvent(self, _event):
        palette = self.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), palette.brush(QPalette.ColorRole.Base))
        painter.setPen(palette.color(QPalette.ColorRole.Mid))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        for left, right, size in self.traces:
            pen = QPen(palette.color(QPalette.ColorRole.Highlight))
            pen.setWidthF(size)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(left, right)


def main():
    from desktop_theme import initialize
    initialize()
    app = QApplication(sys.argv)
    dialog = QDialog()
    dialog.setWindowTitle('Calibrar mesa digitalizadora')
    dialog.setWindowIcon(QIcon.fromTheme('input-tablet'))
    dialog.resize(645, 465)
    layout = QVBoxLayout(dialog)
    note = QLabel('Selecione sua mesa e configure a área ativa, o monitor, os botões e a curva de pressão '
                  'no painel do Plasma. Use a caneta abaixo para conferir o resultado.')
    note.setWordWrap(True)
    layout.addWidget(note)
    status = QLabel('Aproxime a caneta da área de teste.')
    status.setAccessibleName('Posição e pressão da caneta')
    progress = QProgressBar()
    progress.setAccessibleName('Pressão recebida da caneta')

    def report(message, pressure):
        status.setText(message)
        progress.setValue(round(pressure * 100))

    pad = Pad(report)
    layout.addWidget(pad, 1)
    layout.addWidget(status)
    layout.addWidget(progress)
    tools = QHBoxLayout()
    settings = QPushButton(QIcon.fromTheme('configure'), 'Abrir configuração da mesa')
    settings.clicked.connect(lambda: QProcess.startDetached('/usr/bin/kcmshell6', ['kcm_tablet']))
    tools.addWidget(settings)
    clear = QPushButton(QIcon.fromTheme('edit-clear'), 'Limpar área de teste')
    clear.clicked.connect(pad.reset)
    tools.addWidget(clear)
    layout.addLayout(tools)
    controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    controls.rejected.connect(dialog.reject)
    layout.addWidget(controls)
    dialog.exec()


if __name__ == '__main__':
    main()
