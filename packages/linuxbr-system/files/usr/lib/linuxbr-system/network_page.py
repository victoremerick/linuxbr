"""Windows-style adapter properties for NetworkManager connections."""
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,
    QLineEdit,QPushButton,QGroupBox,QMessageBox)
from network_ip import profiles,settings,validated


class IPPage(QWidget):
    def __init__(self):
        super().__init__()
        self.process=None
        body=QVBoxLayout(self);body.setContentsMargins(32,28,32,28);body.setSpacing(14)
        heading=QLabel('Endereços IP e DNS');heading.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(heading)
        note=QLabel('Escolha a conexão e configure DHCP ou endereços manuais. As alterações serão usadas na próxima conexão; reconectar uma conexão ativa pode interromper a rede.')
        note.setWordWrap(True);body.addWidget(note)
        bar=QHBoxLayout();self.profile=QComboBox();self.profile.currentIndexChanged.connect(self.load)
        bar.addWidget(self.profile,1);refresh=QPushButton('Atualizar');refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh);body.addLayout(bar)
        self.forms={}
        for family in (4,6):
            box=QGroupBox(f'IPv{family}');form=QFormLayout(box)
            method=QComboBox();method.addItem('Automático (DHCP/SLAAC)','auto');method.addItem('Manual','manual');method.addItem('Desativado','disabled')
            address=QLineEdit();address.setPlaceholderText('192.168.1.50/24' if family==4 else '2001:db8::50/64')
            gateway=QLineEdit();dns=QLineEdit();dns.setPlaceholderText('Servidores DNS separados por vírgula')
            form.addRow('Configuração',method);form.addRow('Endereço/prefixo',address)
            form.addRow('Gateway',gateway);form.addRow('DNS preferencial e alternativo',dns)
            method.currentIndexChanged.connect(lambda _,m=method,a=address,g=gateway:self.fields(m,a,g))
            self.forms[family]=(method,address,gateway,dns);body.addWidget(box)
        save=QPushButton('Salvar configuração');save.setDefault(True);save.clicked.connect(self.save);body.addWidget(save)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status);body.addStretch()
        self.refresh()

    @staticmethod
    def fields(method,address,gateway):
        manual=method.currentData()=='manual'
        address.setEnabled(manual);gateway.setEnabled(manual)
        if not manual:address.clear();gateway.clear()

    def refresh(self):
        try:rows=profiles()
        except Exception as error:self.status.setText('Não foi possível ler as conexões: '+str(error));return
        old=self.profile.currentData();self.profile.blockSignals(True);self.profile.clear()
        for row in rows:self.profile.addItem(row['name']+' · '+('Wi-Fi' if row['type'] in ('wifi','802-11-wireless') else 'Ethernet'),row['uuid'])
        if old:
            index=self.profile.findData(old)
            if index>=0:self.profile.setCurrentIndex(index)
        self.profile.blockSignals(False);self.load()

    def load(self):
        profile=self.profile.currentData()
        if not profile:return
        try:data=settings(profile)
        except Exception as error:self.status.setText('Não foi possível ler as propriedades: '+str(error));return
        for family,controls in self.forms.items():
            method,address,gateway,dns=controls
            current=data.get(f'ipv{family}.method','auto')
            index=method.findData(current);method.blockSignals(True);method.setCurrentIndex(max(0,index));method.blockSignals(False)
            address.setText(data.get(f'ipv{family}.addresses',''));gateway.setText(data.get(f'ipv{family}.gateway',''))
            dns.setText(data.get(f'ipv{family}.dns',''));self.fields_enabled(method,address,gateway)
        self.status.setText('Configuração atual carregada.')

    @staticmethod
    def fields_enabled(method,address,gateway):
        manual=method.currentData()=='manual';address.setEnabled(manual);gateway.setEnabled(manual)

    def save(self):
        if self.process is not None or not self.profile.currentData():return
        try:
            values={family:validated(family,control[0].currentData(),control[1].text().strip(),control[2].text().strip(),control[3].text())
                    for family,control in self.forms.items()}
        except ValueError as error:self.status.setText(str(error));return
        args=[]
        for family,data in values.items():
            for key,value in data.items():args.extend([f'ipv{family}.{key}',value])
        process=self.process=QProcess(self);process.setProgram('/usr/bin/nmcli')
        process.setArguments(['connection','modify',self.profile.currentData(),*args])
        process.finished.connect(lambda code,status:self.finished(process,code))
        process.errorOccurred.connect(lambda error:self.finished(process,1) if error==QProcess.ProcessError.FailedToStart else None)
        self.status.setText('Salvando configuração…');process.start()

    def finished(self,process,code):
        if self.process is not process:return
        self.process=None
        output=bytes(process.readAllStandardError()).decode(errors='replace').strip();process.deleteLater()
        self.status.setText('Configuração salva. Reconecte para aplicá-la.' if code==0 else
                            'Não foi possível salvar: '+(output or 'Verifique permissões e valores.'))
