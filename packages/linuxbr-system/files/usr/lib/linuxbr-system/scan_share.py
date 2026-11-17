"""Scan one page with SANE and share the saved image with a paired device."""

from pathlib import Path
import shutil
from subprocess import SubprocessError
import sys
from tempfile import TemporaryDirectory

from PyQt6.QtCore import QMarginsF, QProcess, QRect, QTimer, Qt
from PyQt6.QtGui import QImageReader, QPageLayout, QPageSize, QPainter, QPdfWriter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog, QInputDialog,
    QLabel, QMessageBox, QVBoxLayout,
)

from desktop_jobs import Command
from send_content import choose_device, share_file
from store_sources import atomic_write


TITLE = 'Digitalizar e enviar'
SCANNER = '/usr/bin/scanimage'
MAX_IMAGE = 64 * 1024 * 1024


def scanner_list(output):
    devices = {}
    for line in output.splitlines():
        identifier, tab, label = line.partition('\t')
        if tab and identifier and not any(ord(char) < 32 for char in identifier):
            devices[f'{label.strip()} ({identifier})'] = identifier
    return devices


def scan_pdf(image, output):
    reader = QImageReader(str(image), b'png')
    dimensions = reader.size()
    dimensions.scale(2480, 3508, Qt.AspectRatioMode.KeepAspectRatio)
    reader.setScaledSize(dimensions)
    page = reader.read()
    if page.isNull():
        raise ValueError('Não foi possível preparar o PDF da digitalização.')
    writer = QPdfWriter(str(output))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)
    painter = QPainter(writer)
    if not painter.isActive():
        raise ValueError('Não foi possível criar o PDF da digitalização.')
    size = page.size()
    size.scale(writer.width(), writer.height(), Qt.AspectRatioMode.KeepAspectRatio)
    painter.drawImage(QRect((writer.width() - size.width()) // 2, (writer.height() - size.height()) // 2,
                            size.width(), size.height()), page)
    painter.end()


def preview_and_share(parent, image):
    if not 0 < image.stat().st_size <= MAX_IMAGE:
        raise ValueError('A imagem está vazia ou excede 64 MB. Use o Skanpage para digitalizações maiores.')
    reader = QImageReader(str(image), b'png')
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 40_000_000:
        raise ValueError('O scanner gerou uma imagem inválida ou acima de 40 megapixels.')
    size.scale(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
    reader.setScaledSize(size)
    thumbnail = reader.read()
    if thumbnail.isNull():
        raise ValueError('Não foi possível visualizar o arquivo do scanner.')
    review = QDialog(parent)
    review.setWindowTitle('Revisar digitalização')
    layout = QVBoxLayout(review)
    label = QLabel()
    label.setPixmap(QPixmap.fromImage(thumbnail))
    layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    save = buttons.addButton('Salvar e escolher destinatário…', QDialogButtonBox.ButtonRole.AcceptRole)
    save.setAutoDefault(False)
    layout.addWidget(buttons)
    buttons.accepted.connect(review.accept)
    buttons.rejected.connect(review.reject)
    if review.exec() != QDialog.DialogCode.Accepted:
        return
    destination, _ = QFileDialog.getSaveFileName(
        parent, 'Salvar digitalização', str(Path.home() / 'Digitalização.pdf'), 'Documento PDF (*.pdf)'
    )
    if not destination:
        return
    if Path(destination).suffix.lower() != '.pdf':
        raise ValueError('Use a extensão .pdf para salvar a digitalização.')
    pdf = image.with_suffix('.pdf')
    scan_pdf(image, pdf)
    atomic_write(Path(destination), pdf.read_bytes(), 0o600)
    try:
        target = choose_device(parent)
        if target is not None:
            share_file(target[0], destination)
            QMessageBox.information(parent, TITLE, 'PDF salvo. Solicitação de envio entregue ao KDE Connect.')
    except (OSError, SubprocessError):
        QMessageBox.warning(parent, TITLE, 'O PDF foi salvo. Confira se o outro dispositivo está pareado e disponível.')


def main():
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-scan-share')
    if not shutil.which(SCANNER):
        QMessageBox.information(None, TITLE, 'Instale Impressão e digitalização em Recursos opcionais.')
        return 1

    progress = QDialog()
    progress.setWindowTitle(TITLE)
    layout = QVBoxLayout(progress)
    layout.addWidget(QLabel('Procurando scanners locais e de rede…'))
    process = QProcess(progress)
    process.finished.connect(lambda code, status: progress.done(
        1 if code == 0 and status == QProcess.ExitStatus.NormalExit else 2
    ))
    process.errorOccurred.connect(lambda error: progress.done(2)
                                  if error == QProcess.ProcessError.FailedToStart else None)
    timer = QTimer(progress)
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: progress.done(2))
    process.start(SCANNER, ['--formatted-device-list=%d\t%v %m%n'])
    timer.start(35000)
    status = progress.exec()
    timer.stop()
    if process.state() != QProcess.ProcessState.NotRunning:
        process.blockSignals(True)
        process.kill()
        process.waitForFinished(1000)
    if status == 2:
        QMessageBox.warning(None, TITLE, 'Não foi possível consultar os scanners. Confira a conexão e tente novamente.')
        return 1
    if status != QDialog.DialogCode.Accepted:
        return 0
    result = scanner_list(bytes(process.readAllStandardOutput()).decode(errors='replace'))
    if not result:
        QMessageBox.information(None, TITLE, 'Nenhum scanner disponível.')
        return 0
    name, accepted = QInputDialog.getItem(None, TITLE, 'Scanner', list(result), editable=False)
    if not accepted:
        return 0
    with TemporaryDirectory(prefix='linuxbr-scan-') as folder:
        image = Path(folder) / 'Digitalização.png'
        job = Command(
            'Digitalizar uma página',
            ['/usr/bin/timeout', '120', SCANNER, '--device-name=' + result[name],
             '--format=png', '--output-file=' + str(image)],
            success_message='Digitalização concluída. Feche esta janela para revisar a imagem.'
        )
        outcomes = []
        job.completed.connect(outcomes.append)
        job.exec()
        if outcomes == [0]:
            try:
                preview_and_share(None, image)
            except (OSError, ValueError) as error:
                box = QMessageBox(QMessageBox.Icon.Warning, TITLE, str(error), QMessageBox.StandardButton.Ok)
                box.setTextFormat(Qt.TextFormat.PlainText)
                box.exec()
                return 1
    return 0 if outcomes == [0] else 1


if __name__ == '__main__':
    sys.exit(main())
