"""Desktop entry point for versioned backups on another computer."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from desktop_jobs import Command
from network_backup import absolute_path, command, password_input, repository, restore_args


class NetworkBackupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Backup em outro computador')
        self.setMinimumWidth(520)
        body = QVBoxLayout(self)
        help_text = QLabel(
            'Escolha um computador com SFTP e uma pasta dedicada a este backup. '
            'O acesso requer uma chave SSH autorizada e um servidor já reconhecido nesta conta. '
            'Guarde a senha do backup para recuperar seus arquivos.'
        )
        help_text.setWordWrap(True)
        body.addWidget(help_text)
        form = QFormLayout()
        body.addLayout(form)
        self.host = QLineEdit()
        self.user = QLineEdit()
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(22)
        self.directory = QLineEdit()
        self.directory.setPlaceholderText('/home/usuario/backup')
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Computador', self.host)
        form.addRow('Usuário SSH', self.user)
        form.addRow('Porta SSH', self.port)
        form.addRow('Pasta remota', self.directory)
        form.addRow('Senha do backup', self.password)
        for title, action in (
            ('Criar repositório nesta pasta…', self.initialize),
            ('Fazer backup de arquivos…', self.backup),
            ('Listar versões disponíveis', self.versions),
            ('Restaurar arquivo, pasta ou versão…', self.restore),
        ):
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _, callback=action: self.run(callback))
            body.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        body.addWidget(close)

    def run(self, action):
        try:
            repo = repository(self.host.text(), self.user.text(), self.port.value(), self.directory.text())
            secret = password_input(self.password.text())
            action(repo, secret)
        except (OSError, UnicodeError, ValueError) as error:
            box = QMessageBox(QMessageBox.Icon.Warning, self.windowTitle(), str(error),
                              QMessageBox.StandardButton.Ok, self)
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.exec()

    def start(self, title, repo, secret, *args, **kwargs):
        self.password.clear()
        job = Command(title, command(repo, *args), self, input_data=secret, **kwargs)
        job.setWindowModality(Qt.WindowModality.WindowModal)
        return job

    def initialize(self, repo, secret):
        repeated, accepted = QInputDialog.getText(
            self, 'Criar repositório', 'Repita a senha do novo backup', QLineEdit.EchoMode.Password
        )
        if accepted:
            if password_input(repeated) != secret:
                raise ValueError('As senhas digitadas são diferentes.')
            self.start('Criar repositório', repo, secret, 'init')

    def backup(self, repo, secret):
        options = ['Pasta', 'Arquivo']
        kind, accepted = QInputDialog.getItem(
            self, 'Fazer backup', 'O que deseja copiar?', options, editable=False
        )
        if not accepted:
            return
        if kind == options[0]:
            source = QFileDialog.getExistingDirectory(self, 'Escolher pasta', str(Path.home()))
        else:
            source, _ = QFileDialog.getOpenFileName(self, 'Escolher arquivo', str(Path.home()))
        if source:
            self.start('Fazer backup', repo, secret, 'backup', '--', absolute_path(source))

    def versions(self, repo, secret):
        self.start('Versões disponíveis', repo, secret, 'snapshots')

    def restore(self, repo, secret):
        snapshot, accepted = QInputDialog.getText(
            self, 'Restaurar backup', 'Identificador exibido em Versões disponíveis ou latest', text='latest'
        )
        if not accepted:
            return
        source, accepted = QInputDialog.getText(
            self, 'Restaurar backup',
            'Caminho original completo do arquivo ou da pasta. Deixe vazio para recuperar a versão inteira.'
        )
        if not accepted:
            return
        directory = QFileDialog.getExistingDirectory(self, 'Escolher onde criar a pasta restaurada', str(Path.home()))
        if not directory:
            return
        args, target = restore_args(snapshot.strip(), source, directory)
        job = self.start('Restaurar backup', repo, secret, *args)

        def report(code):
            if code:
                job.output.appendPlainText(f'Local da tentativa de restauração\n{target}')
                return
            if not any(Path(target).iterdir()):
                job.status.setText('Nenhum arquivo encontrado para a seleção informada.')
                return
            job.output.appendPlainText(f'Arquivos restaurados em\n{target}')

        job.completed.connect(report)
