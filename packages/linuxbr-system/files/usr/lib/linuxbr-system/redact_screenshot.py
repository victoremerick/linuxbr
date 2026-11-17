"""Capture and prepare an opaque, flattened image for sharing."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PyQt6.QtCore import QPoint, QProcess, QRect, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QImageReader, QPainter, QPen
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QDialog, QFileDialog, QHBoxLayout,
    QInputDialog, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from file_tools import plain_label
from visual_style import BUTTONS


def render(image, crop, edits):
    """Return a fresh image containing exactly the selected, composited pixels."""
    safely_cropped = crop.intersected(image.rect())
    result = QImage(safely_cropped.size(), QImage.Format.Format_RGB32)
    result.fill(QColor('white'))
    with QPainter(result) as painter:
        painter.drawImage(result.rect(), image, safely_cropped)
        painter.translate(-safely_cropped.x(), -safely_cropped.y())
        for kind, bounds, annotation in edits:
            if kind == 'mask':
                painter.fillRect(bounds, QColor('black'))
            elif kind == 'text':
                painter.fillRect(bounds, QColor('#fff3bb'))
                painter.setPen(QColor('black'))
                painter.drawText(bounds.adjusted(4, 2, -4, -2), Qt.TextFlag.TextWordWrap.value, annotation)
    return result


class Canvas(QWidget):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.editor = dialog
        self.image = QImage()
        self.origin = None
        self.current = None
        self.image_area = QRect()
        self.setMinimumSize(340, 300)
        self.setAccessibleName('Região da imagem')

    def paintEvent(self, _event):
        with QPainter(self) as painter:
            painter.fillRect(self.rect(), self.palette().window())
            if self.image.isNull():
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Capture a tela ou abra uma imagem.')
                return
            size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            self.image_area = QRect(QPoint((self.width() - size.width()) // 2, (self.height() - size.height()) // 2), size)
            preview = render(self.image, self.image.rect(), self.editor.edits)
            painter.drawImage(self.image_area, preview)
            painter.setPen(QPen(QColor('#0786ff'), 2, Qt.PenStyle.DashLine))
            if self.editor.crop != self.image.rect():
                painter.drawRect(self.widget_rect(self.editor.crop))
            if self.origin is not None:
                painter.drawRect(QRect(self.origin, self.current).normalized())

    def widget_rect(self, native):
        area = self.image_area
        ratio = area.width() / self.image.width()
        return QRect(round(native.x() * ratio + area.x()), round(native.y() * ratio + area.y()),
                     round(native.width() * ratio), round(native.height() * ratio))

    def native_rect(self, selection):
        area = self.image_area
        picked = selection.intersected(area)
        scale = self.image.width() / area.width()
        left, top = int((picked.left() - area.left()) * scale), int((picked.top() - area.top()) * scale)
        right = round((picked.right() + 1 - area.left()) * scale)
        bottom = round((picked.bottom() + 1 - area.top()) * scale)
        return QRect(left, top, right - left, bottom - top).intersected(self.image.rect())

    def mousePressEvent(self, event):
        point = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton and self.image_area.contains(point):
            self.origin = self.current = point
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            selected = QRect(self.origin, event.position().toPoint()).normalized()
            self.origin = self.current = None
            if selected.width() > 3 and selected.height() > 3:
                self.editor.apply_selection(self.native_rect(selected))
            self.update()


class Editor(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Capturar e ocultar informações')
        self.setWindowIcon(QIcon.fromTheme('camera-photo'))
        self.resize(900, 700)
        self.edits = []
        self.crop = QRect()
        self.temporary = None
        self.process = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        controls = QHBoxLayout()
        for label, icon, action in (('Capturar região', 'camera-photo', self.capture),
                ('Abrir imagem…', 'document-open', self.open_image), ('Desfazer edição', 'edit-undo', self.undo)):
            button = QPushButton(QIcon.fromTheme(icon), label)
            button.clicked.connect(action)
            controls.addWidget(button)
        controls.addStretch()
        root.addLayout(controls)
        modes = QHBoxLayout()
        self.modes = {}
        self.group = QButtonGroup(self)
        for identity, label in (('crop', 'Recortar'), ('mask', 'Cobrir com preto'), ('text', 'Anotar')):
            option = QRadioButton(label)
            self.group.addButton(option)
            self.modes[identity] = option
            modes.addWidget(option)
        self.modes['mask'].setChecked(True)
        modes.addStretch()
        root.addLayout(modes)
        self.canvas = Canvas(self)
        root.addWidget(self.canvas, 1)
        self.status = plain_label('Arraste sobre a área que deseja cobrir, recortar ou anotar.')
        root.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch()
        self.output_buttons = []
        for label, icon, command in (('Copiar imagem final', 'edit-copy', self.copy),
                ('Salvar PNG…', 'document-save', self.save)):
            button = QPushButton(QIcon.fromTheme(icon), label)
            button.setEnabled(False)
            button.clicked.connect(command)
            actions.addWidget(button)
            self.output_buttons.append(button)
        root.addLayout(actions)

    def read_image(self, path):
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            self.status.setText(reader.errorString())
            return
        self.canvas.image = image
        self.edits.clear()
        self.crop = image.rect()
        for button in self.output_buttons:
            button.setEnabled(True)
        self.status.setText('Arraste sobre a área que deseja cobrir, recortar ou anotar.')
        self.canvas.update()

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir captura', str(Path.home()),
                                              'Imagens (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:
            self.read_image(path)

    def capture(self):
        if self.process is not None:
            return
        self.temporary = TemporaryDirectory(prefix='linuxbr-captura-')
        self.capture_path = Path(self.temporary.name) / 'captura.png'
        self.process = QProcess(self)
        self.process.finished.connect(self.capture_finished)
        self.process.errorOccurred.connect(self.capture_failed)
        self.hide()
        self.process.start('/usr/bin/spectacle', ['--background', '--nonotify', '--region', '--output', str(self.capture_path)])

    def capture_failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.capture_finished(1)

    def capture_finished(self, code):
        self.show()
        self.raise_()
        if code == 0 and self.capture_path.is_file():
            self.read_image(self.capture_path)
        else:
            self.status.setText('A captura não foi concluída. Tente novamente ou abra uma imagem.')
        self.temporary.cleanup()
        self.temporary = None
        self.process.deleteLater()
        self.process = None

    def apply_selection(self, selected):
        if selected.isEmpty():
            return
        if self.modes['crop'].isChecked():
            self.edits.append(('previous-crop', self.crop, ''))
            self.crop = selected
        elif self.modes['text'].isChecked():
            text, ok = QInputDialog.getText(self, 'Anotar imagem', 'Texto da anotação')
            if ok and text.strip():
                self.edits.append(('text', selected, text))
        else:
            self.edits.append(('mask', selected, ''))

    def undo(self):
        if self.edits:
            kind, bounds, _ = self.edits.pop()
            if kind == 'previous-crop':
                self.crop = bounds
            self.canvas.update()

    def rendered(self):
        return render(self.canvas.image, self.crop, self.edits)

    def copy(self):
        QApplication.clipboard().setImage(self.rendered())
        self.status.setText('Imagem final copiada.')

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Salvar imagem final', str(Path.home() / 'Captura.png'), 'PNG (*.png)')
        if path:
            self.status.setText('Imagem final salva.' if self.rendered().save(path, 'PNG') else 'Não foi possível salvar a imagem.')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-redact-screenshot')
    app.setStyleSheet(BUTTONS)
    Editor().exec()
