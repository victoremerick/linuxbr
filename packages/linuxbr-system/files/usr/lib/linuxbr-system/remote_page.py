"""Remote access host configuration inside the System Center."""
import sys
from pathlib import Path
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QGroupBox,QLabel,QSpinBox,
    QCheckBox,QPushButton,QLineEdit,QMessageBox)
from remote_backend import rdp_settings,vnc_settings


class RemoteAccess(QWidget):
    def __init__(self):
        super().__init__();self.process=None
        body=QVBoxLayout(self);body.setContentsMargins(32,28,32,28);body.setSpacing(14)
        title=QLabel('Acesso remoto');title.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(title)
        note=QLabel('Permita conexões à sessão atual deste computador. RDP usa a conta da sessão no Plasma Wayland; VNC exige a senha exibida abaixo e confirmação local de cada conexão.')
        note.setWordWrap(True);body.addWidget(note)
        self.rdp=QGroupBox('Área de trabalho remota · RDP');rdp_form=QFormLayout(self.rdp)
        self.rdp_on=QCheckBox('Permitir acesso por RDP');rdp_form.addRow('',self.rdp_on)
        self.rdp_port=QSpinBox();self.rdp_port.setRange(1024,65535);rdp_form.addRow('Porta',self.rdp_port)
        self.rdp_apply=QPushButton('Aplicar RDP');self.rdp_apply.clicked.connect(lambda:self.apply('rdp'));rdp_form.addRow('',self.rdp_apply)
        body.addWidget(self.rdp)
        self.vnc=QGroupBox('Compartilhamento de tela · VNC');vnc_form=QFormLayout(self.vnc)
        self.vnc_on=QCheckBox('Permitir acesso por VNC');vnc_form.addRow('',self.vnc_on)
        self.vnc_port=QSpinBox();self.vnc_port.setRange(1024,65535);vnc_form.addRow('Porta',self.vnc_port)
        self.password=QLineEdit();self.password.setReadOnly(True);self.password.setEchoMode(QLineEdit.EchoMode.Password)
        vnc_form.addRow('Senha da sessão',self.password)
        show=QCheckBox('Mostrar senha');show.toggled.connect(lambda checked:self.password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        vnc_form.addRow('',show)
        self.vnc_apply=QPushButton('Aplicar VNC');self.vnc_apply.clicked.connect(lambda:self.apply('vnc'));vnc_form.addRow('',self.vnc_apply)
        body.addWidget(self.vnc)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status);body.addStretch()
        self.refresh()

    def refresh(self):
        try:
            rdp=rdp_settings();vnc=vnc_settings()
            self.rdp_on.setChecked(rdp['active']);self.rdp_port.setValue(rdp['port'])
            self.vnc_on.setChecked(vnc['active']);self.vnc_port.setValue(vnc['port'])
            self.password.setText(vnc['password'] if vnc['active'] else '')
        except (OSError,ValueError) as error:self.status.setText('Não foi possível consultar o acesso remoto: '+str(error))

    def apply(self,kind):
        if self.process is not None:return
        on=self.rdp_on.isChecked() if kind=='rdp' else self.vnc_on.isChecked()
        if on and QMessageBox.question(self,'Permitir acesso remoto',
                'Ativar o compartilhamento desta sessão para computadores que alcancem esta rede?')!=QMessageBox.StandardButton.Yes:return
        port=self.rdp_port.value() if kind=='rdp' else self.vnc_port.value()
        process=self.process=QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments([str(Path(__file__).with_name('remote_backend.py')),kind,'enable' if on else 'disable',str(port)])
        process.finished.connect(lambda code,status:self.finished(process,code,kind,on))
        process.errorOccurred.connect(lambda error:self.finished(process,1,kind,on) if error==QProcess.ProcessError.FailedToStart else None)
        self.rdp_apply.setEnabled(False);self.vnc_apply.setEnabled(False)
        self.status.setText('Aplicando configuração de acesso remoto…');process.start()

    def finished(self,process,code,kind,on):
        if self.process is not process:return
        self.process=None;self.rdp_apply.setEnabled(True);self.vnc_apply.setEnabled(True)
        output=bytes(process.readAllStandardOutput()).decode(errors='replace').strip()
        error=bytes(process.readAllStandardError()).decode(errors='replace').strip();process.deleteLater()
        self.refresh()
        if code:self.status.setText('Não foi possível configurar '+kind.upper()+': '+(error or 'serviço indisponível.'))
        else:
            if kind=='vnc' and on:self.password.setText(output)
            self.status.setText(kind.upper()+(' ativado para esta sessão.' if on else ' desativado.'))
