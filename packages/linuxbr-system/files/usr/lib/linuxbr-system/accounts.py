"""Local accounts and enterprise membership pages for the system hub."""
import json
from pathlib import Path
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox, QTabWidget)


class AccountsPage(QWidget):
    def __init__(self, organization, launch):
        super().__init__()
        self.organization = organization
        self.launch = launch
        self.process = None
        self.loaded = False
        body = QVBoxLayout(self); body.setContentsMargins(32,28,32,28); body.setSpacing(16)
        title = QLabel('Organização' if organization else 'Usuários')
        title.setStyleSheet('font-size:26px;font-weight:600'); body.addWidget(title)
        description = QLabel('Conecte este computador ao Active Directory da empresa. Use o DNS corporativo e mantenha data e hora sincronizadas. Uma conta local administrativa continuará disponível.' if organization else 'Contas deste computador. Crie usuários, altere senhas e escolha entre acesso padrão e administrativo nas configurações de contas.')
        description.setWordWrap(True); body.addWidget(description)
        self.controls = QWidget(); controls = QVBoxLayout(self.controls); controls.setContentsMargins(0,0,0,0)
        row = QHBoxLayout()
        if organization:
            self.domain = QLineEdit(); self.domain.setPlaceholderText('Domínio: empresa.com.br'); self.domain.setAccessibleName('Domínio da empresa')
            controls.addWidget(self.domain)
            self.button(row, 'Localizar domínio', lambda: self.run('discover', domain=self.domain.text()))
            self.button(row, 'Conectar…', lambda: self.credentials('join'))
            self.button(row, 'Desconectar…', lambda: self.credentials('leave'))
        else:
            self.button(row, 'Gerenciar contas e senhas…', lambda: self.launch(['kcmshell6', 'kcm_users']))
        self.button(row, 'Atualizar', self.refresh); row.addStretch(); controls.addLayout(row)
        body.addWidget(self.controls)
        self.table = QTableWidget(0,4); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(['Domínio','Estado','Formato de login','Política de acesso'] if organization else ['Usuário','Nome completo','Tipo','Estado'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        if organization:
            body.addWidget(self.table,1)
            self.groups = None
        else:
            from groups import GroupsPage
            tabs=QTabWidget();tabs.addTab(self.table,'Usuários locais')
            self.groups=GroupsPage();tabs.addTab(self.groups,'Grupos locais')
            body.addWidget(tabs,1)
        self.status = QLabel(''); self.status.setWordWrap(True); body.addWidget(self.status)
        if organization:
            note = QLabel('Após conectar, encerre a sessão e use o formato de login indicado. O primeiro acesso requer conexão com a empresa. As políticas de acesso são administradas pelo domínio; ingressar não concede privilégios de administrador local.')
            note.setWordWrap(True); body.addWidget(note)

    def button(self, row, text, callback):
        button = QPushButton(text); button.clicked.connect(callback); row.addWidget(button)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded:
            self.loaded = True
            self.refresh()

    def refresh(self):
        self.run('realms' if self.organization else 'users')

    def run(self, action, **values):
        if self.process is not None:
            return
        self.controls.setEnabled(False); self.status.setText('Consultando…' if action in ('users','realms','discover') else 'Aplicando alteração. Aguarde a autenticação administrativa e a conclusão…')
        process = self.process = QProcess(self)
        process.setProgram('/usr/bin/python3')
        process.setArguments([str(Path(__file__).with_name('accounts_backend.py'))])
        payload = json.dumps(dict(action=action, **values)).encode()
        def started():
            process.write(payload); process.closeWriteChannel()
            process.started.disconnect(started)
        process.started.connect(started)
        process.finished.connect(lambda code, status: self.finished(process, action))
        process.errorOccurred.connect(lambda error: self.failed_start(process) if error == QProcess.ProcessError.FailedToStart else None)
        process.start()

    def failed_start(self, process):
        if self.process is process:
            self.process = None; self.controls.setEnabled(True)
            self.status.setText('Não foi possível iniciar o serviço de contas. Verifique a instalação do Linux BR.'); process.deleteLater()

    def finished(self, process, action):
        if self.process is not process:
            return
        self.process = None; self.controls.setEnabled(True)
        try:
            result = json.loads(bytes(process.readAllStandardOutput()))
        except (ValueError, UnicodeError):
            result = {'ok':False, 'error':'O serviço não respondeu corretamente. Atualize a lista para conferir o estado antes de tentar novamente.'}
        process.deleteLater()
        if not result['ok']:
            self.status.setText('Não foi possível concluir: ' + result['error']); return
        data = result['data']; self.table.setRowCount(len(data))
        for i, entry in enumerate(data):
            cells = [entry['name'], 'Conectado' if entry['configured'] else 'Disponível', ', '.join(entry['formats']), entry['policy']] if self.organization else [entry['name'], entry['full'], 'Administrador' if entry['admin'] else 'Padrão', 'Bloqueado' if entry['locked'] else 'Ativo']
            for j, text in enumerate(cells):
                self.table.setItem(i,j,QTableWidgetItem(text))
        self.status.setText('Operação concluída.' if action in ('join','leave') else ('Lista atualizada.' if data else 'Nenhum domínio conectado.' if self.organization else 'Nenhuma conta local encontrada.'))

    def credentials(self, action):
        from accounts_backend import domain_name
        try:
            domain = domain_name(self.domain.text())
        except ValueError as error:
            QMessageBox.warning(self,'Domínio',str(error)); return
        dialog = QDialog(self); dialog.setWindowTitle('Conectar ao domínio' if action == 'join' else 'Desconectar do domínio')
        form = QFormLayout(dialog)
        note = QLabel(('Ingressar em ' if action == 'join' else 'Remover a associação com ') + domain + '.\nUse uma conta autorizada pela empresa. A autenticação local pode ser solicitada também.')
        note.setWordWrap(True); form.addRow(note)
        username = QLineEdit(); password = QLineEdit(); password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Conta do domínio',username); form.addRow('Senha',password)
        extra = QLineEdit()
        form.addRow('OU (opcional)' if action == 'join' else 'Digite o domínio para confirmar',extra)
        if action == 'leave':
            warning = QLabel('O acesso com contas da empresa poderá deixar de funcionar. Confirme que possui uma conta local administrativa.'); warning.setWordWrap(True); form.addRow(warning)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not username.text().strip() or not password.text() or (action == 'leave' and extra.text().strip().lower() != domain):
                QMessageBox.warning(self,'Dados incompletos','Informe conta, senha e a confirmação solicitada.'); password.clear(); return
            self.run(action,domain=domain,username=username.text(),password=password.text(),ou=extra.text() if action=='join' else '')
        password.clear(); dialog.deleteLater()
