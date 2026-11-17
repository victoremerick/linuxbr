"""Desktop entry point for versioned backups on another computer."""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from desktop_jobs import Command
from backup_validation import CONFIG, RESULT, load
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
            ('Verificar integridade agora…', self.verify),
            ('Agendar verificação semanal…', self.schedule),
        ):
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _, callback=action: self.run(callback))
            body.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.verification_status = QLabel()
        self.verification_status.setTextFormat(Qt.TextFormat.PlainText)
        self.verification_status.setWordWrap(True)
        body.addWidget(self.verification_status)
        cancel_schedule = QPushButton('Desativar verificação semanal')
        cancel_schedule.clicked.connect(self.cancel_schedule)
        body.addWidget(cancel_schedule, alignment=Qt.AlignmentFlag.AlignLeft)
        self.cancel_button = cancel_schedule
        self.refresh_verification()
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

    def refresh_verification(self):
        configuration = load(CONFIG)
        self.cancel_button.setEnabled(bool(configuration))
        result = load(RESULT)
        lines = ['Verificação semanal configurada para esta conta.' if configuration else
                 'Verificação semanal desativada.']
        try:
            checked = datetime.fromisoformat(result['checked_at']).astimezone().strftime('%d/%m/%Y %H:%M')
            state = ('senha indisponível no cofre' if result.get('credential_unavailable') else
                     'índices e amostra conferidos, arquivo recuperado' if result.get('file') else
                     'arquivo de teste indisponível' if result.get('index_and_sample') else
                     'falha nos índices ou na amostra')
            lines.append(f'Última verificação em {checked} · {state}')
            if result.get('recovered_at'):
                recovered = datetime.fromisoformat(result['recovered_at']).astimezone().strftime('%d/%m/%Y %H:%M')
                lines.append(f'Última recuperação de teste em {recovered}')
        except (KeyError, TypeError, ValueError):
            pass
        self.verification_status.setText('\n'.join(lines))

    def verification(self, secret, action, title):
        source, accepted = QInputDialog.getText(
            self, title, 'Caminho absoluto de um arquivo pequeno presente na cópia mais recente.'
        )
        if not accepted:
            return
        path = absolute_path(source)
        self.password.clear()
        job = Command(title, ['/usr/bin/python3', '/usr/lib/linuxbr-system/backup_validation.py',
                              action, '--host', self.host.text(), '--user', self.user.text(),
                              '--port', str(self.port.value()), '--directory', self.directory.text(),
                              '--source', path], self, input_data=secret)
        job.setWindowModality(Qt.WindowModality.WindowModal)
        job.completed.connect(lambda _: self.refresh_verification())

    def verify(self, repo, secret):
        self.verification(secret, 'check', 'Verificar integridade do backup')

    def schedule(self, repo, secret):
        if QMessageBox.question(
                self, 'Agendar verificação semanal',
                'A senha do backup será guardada no cofre desta conta. A verificação usa a sessão desta conta '
                'e precisa que o cofre e o acesso SSH estejam disponíveis.'
        ) == QMessageBox.StandardButton.Yes:
            self.verification(secret, 'enable', 'Agendar verificação semanal')

    def cancel_schedule(self):
        job = Command('Desativar verificação semanal',
                      ['/usr/bin/python3', '/usr/lib/linuxbr-system/backup_validation.py', 'disable'], self)
        job.setWindowModality(Qt.WindowModality.WindowModal)
        job.completed.connect(lambda _: self.refresh_verification())

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
