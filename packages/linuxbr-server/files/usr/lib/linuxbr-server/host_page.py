"""Host identity, local accounts, time and remote administration."""
import json
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QTabWidget,QLabel,QLineEdit,
    QPushButton,QCheckBox,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox)
from desktop_jobs import Query,Command
import host_backend as backend


class Host(QWidget):
    def __init__(self,section=0):
        super().__init__();self.setWindowTitle('Linux BR — Configuração do servidor');self.setWindowIcon(QIcon.fromTheme('network-server'));self.jobs=set();self.commands=[];self.data={}
        layout=QVBoxLayout(self);title=QLabel('Configuração do servidor');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        identity=QWidget();form=QFormLayout(identity);self.hostname=QLineEdit();form.addRow('Nome do computador',self.hostname)
        change=QPushButton('Aplicar nome…');change.clicked.connect(lambda:self.apply(dict(action='hostname',hostname=self.hostname.text()),'Alterar o nome deste computador?'));form.addRow(change);self.tabs.addTab(identity,'Computador')
        users=QWidget();form=QFormLayout(users);self.users=QTableWidget(0,3);self.users.setHorizontalHeaderLabels(['Usuário','Nome completo','Tipo']);self.users.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.users.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);form.addRow(self.users)
        self.user=QLineEdit();self.full=QLineEdit();self.secret=QLineEdit();self.secret.setEchoMode(QLineEdit.EchoMode.Password);self.admin=QCheckBox('Administrador local')
        form.addRow('Usuário',self.user);form.addRow('Nome completo (nova conta)',self.full);form.addRow('Senha (mínimo 12 caracteres)',self.secret);form.addRow(self.admin)
        create=QPushButton('Criar conta…');create.clicked.connect(lambda:self.account(True));form.addRow(create)
        reset=QPushButton('Alterar senha da conta…');reset.clicked.connect(lambda:self.account(False));form.addRow(reset);self.tabs.addTab(users,'Usuários')
        timing=QWidget();form=QFormLayout(timing);self.zone=QComboBox();self.zone.setEditable(True)
        self.zone.addItems(['America/Sao_Paulo','America/Manaus','America/Cuiaba','America/Rio_Branco','America/Noronha','UTC']);self.ntp=QCheckBox('Sincronizar automaticamente pela rede');self.manual=QLineEdit();self.manual.setPlaceholderText('AAAA-MM-DD HH:MM:SS');form.addRow('Fuso horário',self.zone);form.addRow(self.ntp);form.addRow('Data/hora manual (opcional)',self.manual)
        save=QPushButton('Aplicar data e hora…');save.clicked.connect(lambda:self.apply(dict(action='time',timezone=self.zone.currentText(),ntp=self.ntp.isChecked(),manual=self.manual.text()),'Alterar data, hora e sincronização?'));form.addRow(save);self.tabs.addTab(timing,'Data e hora')
        remote=QWidget();form=QFormLayout(remote);note=QLabel('O SSH permite administrar este computador pela rede. Habilite somente quando necessário e use contas com senhas fortes ou chaves. As regras do firewall são administradas separadamente.');note.setWordWrap(True);form.addRow(note);self.remote_state=QLabel();form.addRow(self.remote_state)
        self.remote_buttons=[]
        for label,enabled in [('Habilitar SSH e iniciar com o sistema…',True),('Desabilitar SSH e parar agora…',False)]:
            button=QPushButton(label);button.clicked.connect(lambda _,value=enabled:self.apply(dict(action='ssh',enabled=value),'Habilitar acesso remoto por SSH? Confira as regras do firewall.' if value else 'Interromper o SSH? Conexões remotas poderão ser encerradas.'));form.addRow(button);self.remote_buttons.append(button)
        self.tabs.addTab(remote,'Acesso remoto');self.tabs.setCurrentIndex(section)
        refresh=QPushButton('Atualizar informações');refresh.clicked.connect(self.refresh);layout.addWidget(refresh);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status);self.refresh()

    def refresh(self):
        if self.jobs:return
        job=Query(backend.state);self.jobs.add(job);job.result.connect(self.loaded);job.failed.connect(self.status.setText);job.finished.connect(lambda:self.jobs.discard(job));job.start()

    def loaded(self,data):
        self.data=data;self.hostname.setText(data['hostname']);self.zone.setCurrentText(data['time'].get('Timezone','America/Sao_Paulo'));self.ntp.setChecked(data['time'].get('NTP')=='yes')
        self.ntp.setEnabled(not data.get('restricted'))
        if data.get('restricted'):self.ntp.setChecked(False)
        self.users.setRowCount(len(data['users']))
        for i,row in enumerate(data['users']):
            for j,value in enumerate([row['name'],row['full'],'Administrador' if row['admin'] else 'Padrão']):self.users.setItem(i,j,QTableWidgetItem(value))
        self.remote_state.setText('SSH ativo' if data['ssh_active'] else 'SSH parado' if data['ssh_installed'] else 'SSH não instalado: adicione o recurso Administração SSH.');self.status.setText('Informações atualizadas.')
        for button in self.remote_buttons:button.setEnabled(data['ssh_installed'] and not data.get('restricted'))
        if data.get('restricted'):self.remote_state.setText('Acesso remoto bloqueado neste modo de inicialização.')

    def account(self,create):
        try:backend.username(self.user.text());backend.password(self.secret.text())
        except ValueError as error:QMessageBox.warning(self,'Conta',str(error));return
        request=dict(action='create-user' if create else 'password',username=self.user.text(),full=self.full.text(),password=self.secret.text(),admin=self.admin.isChecked())
        self.apply(request,('Criar conta '+self.user.text()+(' com permissão administrativa?' if self.admin.isChecked() else '?')) if create else 'Alterar a senha de '+self.user.text()+'?');self.secret.clear()

    def apply(self,request,message):
        if QMessageBox.question(self,'Confirmar alteração',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        dialog=Command('Configurar servidor',['/usr/bin/pkexec','/usr/bin/python3',str(Path(__file__).with_name('host_backend.py'))],self,json.dumps(request).encode());self.commands.append(dialog);dialog.completed.connect(lambda _:self.refresh());dialog.show()
