"""Relatórios locais de ensaios com Wine ou Proton."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)
from compatibility_records import current_version
from windows_runner import write_json


CHECKS = ('Abrir e fechar', 'Teclado, mouse ou controle', 'Som', 'Modo janela e tela cheia',
          'Minimizar, maximizar e restaurar', 'Atalhos de janelas', 'Autenticação',
          'Salvar e reabrir', 'Múltiplos monitores')
WINDOW_CHECKS = {
    'Modo janela e tela cheia':'Alterne entre janela e tela cheia e confira se a barra de tarefas volta a aparecer.',
    'Minimizar, maximizar e restaurar':'Minimize pelo botão ou pela barra de tarefas. Reabra, maximize e restaure pelo título.',
    'Atalhos de janelas':'Alterne para outro programa com Alt+Tab e confira se o foco volta à janela testada.',
    'Múltiplos monitores':'Mova a janela para outra tela ativa e repita o teste com os controles da janela.',
}


def gpu_inventory(base=Path('/sys/class/drm')):
    result = []
    for card in sorted(base.glob('card*')):
        if not re.fullmatch(r'card\d+', card.name):
            continue
        try:
            lines = (card/'device/uevent').read_text().splitlines()
        except OSError:
            continue
        values = dict(line.split('=', 1) for line in lines if '=' in line)
        result.append(dict(device=card.name, driver=values.get('DRIVER',''),
                           pci_id=values.get('PCI_ID',''), slot=values.get('PCI_SLOT_NAME','')))
    return result


def wine_version():
    try:
        result = subprocess.run(['/usr/bin/wine','--version'], check=True, text=True,
                                capture_output=True, timeout=3)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def proton_version(prefix):
    file = Path(prefix)/'version'
    try:
        if file.stat().st_size > 512:
            return ''
        return file.read_text(encoding='utf-8').strip()
    except (OSError, ValueError):
        return ''


def display_context():
    app = QApplication.instance()
    if app is None:
        return {'session':'', 'screens':[]}
    screens = [{'width':screen.size().width(), 'height':screen.size().height(),
                'scale':screen.devicePixelRatio()} for screen in app.screens()]
    return {'session':app.platformName(), 'screens':screens}


def report_document(name, application_version, executor, executor_version, checks, result, evidence):
    if executor not in ('Wine','Proton') or result not in ('Passou','Parcial','Falhou'):
        raise ValueError('Selecione o executor e o resultado do ensaio.')
    name, application_version, executor_version = (value.strip() for value in (name, application_version, executor_version))
    if not all(0 < len(value) <= 256 and '\n' not in value and '\r' not in value
               for value in (name, application_version, executor_version)):
        raise ValueError('Informe o aplicativo e as versões verificadas.')
    if not checks or any(check not in CHECKS for check in checks):
        raise ValueError('Selecione os recursos exercitados.')
    path = Path(evidence)
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Selecione um registro ou captura de evidência de até 64 MiB.')
    with path.open('rb') as file:
        evidence_hash = hashlib.file_digest(file, 'sha256').hexdigest()
    return dict(schema=1, date=datetime.now(timezone.utc).isoformat(), linuxbr=current_version(),
                application=dict(name=name, version=application_version),
                environment=dict(executor=executor, version=executor_version,
                                 gpus=gpu_inventory(), displays=display_context()),
                checks=list(checks), result=result, evidence=dict(file=path.name, sha256=evidence_hash))


class CompatibilityReport(QDialog):
    def __init__(self, name, executor, version, parent=None):
        super().__init__(parent)
        self.name = name
        self.executor = executor
        self.evidence = ''
        self.setWindowTitle('Registrar ensaio de compatibilidade')
        self.resize(630, 625)
        layout = QVBoxLayout(self)
        title = QLabel(name)
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        layout.addWidget(title)
        note = QLabel('Registre o resultado que você observou. O relatório guarda as versões, a GPU detectada e a impressão da evidência.')
        note.setWordWrap(True)
        layout.addWidget(note)
        display = display_context()
        sizes = ', '.join(f"{screen['width']} × {screen['height']}" for screen in display['screens'])
        self.session = QLabel(f"Sessão {display['session']} · Telas ativas: {sizes or 'nenhuma detectada'}")
        self.session.setWordWrap(True)
        layout.addWidget(self.session)
        form = QFormLayout()
        self.application_version = QLineEdit()
        self.executor_version = QLineEdit(version)
        self.result = QComboBox()
        self.result.addItems(('Passou','Parcial','Falhou'))
        form.addRow('&Versão do aplicativo', self.application_version)
        form.addRow('&Versão de '+executor, self.executor_version)
        form.addRow('&Resultado',self.result)
        layout.addLayout(form)
        self.checks = [QCheckBox(check) for check in CHECKS]
        for control in self.checks:
            guide = WINDOW_CHECKS.get(control.text())
            if guide:
                control.setToolTip(guide)
                control.setAccessibleDescription(guide)
            layout.addWidget(control)
        self.checks[-1].setEnabled(len(display['screens']) > 1)
        if len(display['screens']) < 2:
            self.checks[-1].setToolTip('Conecte e ative outra tela para executar esta verificação.')
        self.attachment = QPushButton('Selecionar captura ou registro…')
        self.attachment.clicked.connect(self.choose)
        layout.addWidget(self.attachment)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose(self):
        filename,_ = QFileDialog.getOpenFileName(self,'Selecionar evidência','','Todos os arquivos (*)')
        if filename:
            self.evidence = filename
            self.attachment.setText('Evidência selecionada')
            self.status.clear()

    def save(self):
        try:
            value = report_document(self.name, self.application_version.text(), self.executor,
                self.executor_version.text(), [item.text() for item in self.checks if item.isChecked()],
                self.result.currentText(), self.evidence)
            filename,_ = QFileDialog.getSaveFileName(self,'Exportar ensaio de compatibilidade',
                'linuxbr-compatibilidade.json','Relatório JSON (*.json)')
            if not filename:
                return
            if not filename.lower().endswith('.json'):
                filename += '.json'
            write_json(Path(filename),value)
        except (OSError,ValueError) as error:
            self.status.setText(str(error))
            return
        self.accept()
