"""Firewall page: effective zone rules and listening applications."""
import json
from pathlib import Path
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,
    QTableWidgetItem,QHeaderView,QPushButton,QLineEdit,QComboBox,QTabWidget,QMessageBox)
from firewall_backend import validate


class Firewall(QWidget):
    def __init__(self):
        super().__init__()
        self.process = None; self.running = False
        body=QVBoxLayout(self); body.setContentsMargins(32,28,32,28); body.setSpacing(14)
        title=QLabel('Firewall e segurança de rede'); title.setStyleSheet('font-size:26px;font-weight:600'); body.addWidget(title)
        self.status=QLabel(); self.status.setWordWrap(True); body.addWidget(self.status)
        self.zone=QComboBox();self.zone.currentIndexChanged.connect(self.show_zone);body.addWidget(self.zone)
        note=QLabel('As regras liberam portas e serviços na zona padrão. A lista de aplicações mostra processos com portas abertas; ela não representa uma permissão exclusiva por aplicativo.')
        note.setWordWrap(True); body.addWidget(note)
        buttons=QHBoxLayout(); self.toggle=QPushButton(); self.toggle.clicked.connect(self.toggle_firewall); buttons.addWidget(self.toggle)
        refresh=QPushButton('Atualizar'); refresh.clicked.connect(self.refresh); buttons.addWidget(refresh); buttons.addStretch(); body.addLayout(buttons)
        tabs=QTabWidget(); body.addWidget(tabs,1)
        rules=QWidget(); rule_layout=QVBoxLayout(rules)
        self.services=QLabel(); self.services.setWordWrap(True); rule_layout.addWidget(self.services)
        self.ports=QTableWidget(0,3); self.ports.setHorizontalHeaderLabels(['Origem','Porta/regra','Ação'])
        self.ports.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ports.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); rule_layout.addWidget(self.ports)
        add=QHBoxLayout(); self.number=QLineEdit(); self.number.setPlaceholderText('Porta, de 1 a 65535'); add.addWidget(self.number)
        self.protocol=QComboBox(); self.protocol.addItems(['TCP','UDP']); add.addWidget(self.protocol)
        self.add_rule=QPushButton('Liberar porta'); self.add_rule.clicked.connect(self.allow); add.addWidget(self.add_rule); rule_layout.addLayout(add)
        tabs.addTab(rules,'Regras permitidas')
        listeners=QWidget(); listener_layout=QVBoxLayout(listeners)
        self.apps=QTableWidget(0,3); self.apps.setHorizontalHeaderLabels(['Aplicação','Endereço e porta','Protocolo'])
        self.apps.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.apps.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); listener_layout.addWidget(self.apps)
        tabs.addTab(listeners,'Aplicações com portas abertas')
        self.refresh()

    def refresh(self):
        from firewall_backend import state
        try: data=state()
        except Exception as error:
            self.status.setText('Não foi possível ler o firewall: '+str(error))
            self.toggle.setEnabled(False);self.add_rule.setEnabled(False);return
        self.toggle.setEnabled(True)
        self.running=data['running']; self.toggle.setText('Desativar firewall' if self.running else 'Ativar firewall')
        self.status.setText(('Ativo · zona padrão: '+data['zone']) if self.running else 'Firewall desativado. As regras salvas não estão sendo aplicadas.')
        previous=self.zone.currentText();self.zone.blockSignals(True);self.zone.clear();self.zone.addItems(data['zones'])
        if previous in data['zones']:self.zone.setCurrentText(previous)
        self.zone.blockSignals(False);self.data=data;self.show_zone()
        self.apps.setRowCount(len(data['listeners']))
        for i,entry in enumerate(data['listeners']):
            for j,key in enumerate(('app','address','protocol')):
                self.apps.setItem(i,j,QTableWidgetItem(entry[key]))
        self.add_rule.setEnabled(self.running)

    def show_zone(self):
        zone=self.zone.currentText();details=self.data.get('details',{}).get(zone,{})
        self.services.setText('Serviços liberados: '+(', '.join(details.get('services',[])) or 'nenhum'))
        rows=[]
        for service in details.get('services',[]):
            rows.append(('Serviço '+service,', '.join(details['service_ports'].get(service,[])) or 'definido pelo serviço',None))
        rows += [('Porta',port,port) for port in details.get('ports',[])]
        rows += [('Regra avançada',rule,None) for rule in details.get('rich',[])]
        rows += [('Redirecionamento',rule,None) for rule in details.get('forward',[])]
        self.ports.setRowCount(len(rows))
        for i,(source,description,port) in enumerate(rows):
            self.ports.setItem(i,0,QTableWidgetItem(source));self.ports.setItem(i,1,QTableWidgetItem(description))
            if port:
                button=QPushButton('Remover');button.clicked.connect(lambda checked=False,p=port:self.change('remove',p))
                self.ports.setCellWidget(i,2,button)

    def toggle_firewall(self):
        action='disable' if self.running else 'enable'
        if action == 'disable' and QMessageBox.question(self,'Desativar firewall',
                'Desativar a proteção de rede deste computador?') != QMessageBox.StandardButton.Yes: return
        self.change(action)

    def allow(self):
        try: port=validate(self.number.text().strip()+'/'+self.protocol.currentText().lower())
        except ValueError as error: self.status.setText(str(error)); return
        self.change('allow',port)

    def change(self,action,port=''):
        if self.process is not None: return
        if action == 'remove' and QMessageBox.question(self,'Remover regra',
                'Remover a liberação de '+port+'?') != QMessageBox.StandardButton.Yes: return
        self.status.setText('Aguardando autenticação administrativa…')
        process=self.process=QProcess(self)
        process.setProgram('/usr/bin/pkexec')
        args=['/usr/bin/python3',str(Path(__file__).with_name('firewall_backend.py')),action]
        if action in ('allow','remove'):args.extend([port,self.zone.currentText()])
        process.setArguments(args)
        process.finished.connect(lambda code,status:self.finished(process,code))
        process.errorOccurred.connect(lambda error:self.finished(process,1) if error == QProcess.ProcessError.FailedToStart else None)
        process.start()

    def finished(self,process,code):
        if self.process is not process:return
        self.process=None
        message=bytes(process.readAllStandardError()).decode(errors='replace').strip()
        process.deleteLater(); self.refresh()
        if code:self.status.setText('Não foi possível aplicar a alteração. '+(message or 'Verifique a autenticação.'))
