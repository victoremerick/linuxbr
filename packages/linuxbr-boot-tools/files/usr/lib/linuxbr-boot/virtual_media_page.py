"""Redeem a delegated media code without an administrative libvirt session."""

import sys
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QLabel,
                             QLineEdit, QPushButton, QVBoxLayout)


class MediaDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Anexar mídia autorizada')
        self.setWindowIcon(QIcon.fromTheme('media-optical'))
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        intro = QLabel('Informe o código entregue pelo administrador deste hospedeiro.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.code = QLineEdit()
        self.code.setAccessibleName('Código de autorização')
        self.code.setEchoMode(QLineEdit.EchoMode.Password)
        self.code.setMaxLength(32)
        self.code.returnPressed.connect(self.redeem)
        layout.addWidget(self.code)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.attach = QPushButton(QIcon.fromTheme('media-optical'), 'Anexar ISO')
        self.attach.clicked.connect(self.redeem)
        self.attach.setEnabled(False)
        self.code.textChanged.connect(lambda text: self.attach.setEnabled(len(text) == 32))
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(self.attach)
        layout.addWidget(close)
        self.process = None

    def redeem(self):
        if self.process is not None or len(self.code.text()) != 32:
            return
        code = self.code.text().encode('utf-8')
        self.code.clear()
        self.code.setEnabled(False)
        self.status.setText('Aguarde a autenticação e a conferência da mídia…')
        process = self.process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.started.connect(lambda: (process.write(code + b'\n'), process.closeWriteChannel()))

        def finished(number):
            if self.process is not process:
                return
            content = bytes(process.readAllStandardOutput()).decode('utf-8', 'replace').strip()
            self.status.setText(content[:800] or ('ISO anexada.' if number == 0 else 'A autorização não foi concluída.'))
            self.code.setEnabled(True)
            self.process = None
            process.deleteLater()

        process.finished.connect(lambda number, _: finished(number))
        process.errorOccurred.connect(lambda error: finished(1) if error == QProcess.ProcessError.FailedToStart else None)
        process.start('/usr/bin/pkexec', ['/usr/bin/linuxbr-vm-media-attach'])

    def reject(self):
        if self.process is None:
            super().reject()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    MediaDialog().exec()
