#!/usr/bin/python3
"""Qt hardware manager. Read-only inventory; explicit polkit firmware installation."""
import json
from pathlib import Path
import sys
from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QLineEdit,QComboBox,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,
    QAbstractItemView,QPlainTextEdit,QSplitter,QMessageBox,QFileDialog,QCheckBox,QToolButton,QFrame)

class Devices(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.process=None; self.installing=False; self.data={}; self.visible=[]; self.software_rows=[]; self.device_filter=None
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24)
        layout.setSpacing(16)
        heading=QLabel('Dispositivos e drivers');heading.setStyleSheet('font-size:26px;font-weight:600')
        layout.addWidget(heading)
        description=QLabel('Hardware, módulos do kernel, firmware e diagnósticos do Linux BR')
        description.setWordWrap(True);layout.addWidget(description)
        bar=QHBoxLayout();self.refresh_button=self.tool_button('Atualizar dispositivos','view-refresh');self.export_button=self.tool_button('Exportar relatório…','document-export')
        self.refresh_button.clicked.connect(self.refresh);self.export_button.clicked.connect(self.export_report)
        self.export_button.setEnabled(False);bar.addWidget(self.refresh_button);bar.addWidget(self.export_button);bar.addStretch();layout.addLayout(bar)
        self.tabs=QTabWidget();layout.addWidget(self.tabs)
        hardware=QWidget();body=QVBoxLayout(hardware);filters=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar modelo, fabricante, driver ou ID')
        self.category=QComboBox();self.category.addItem('Todas as categorias')
        filters.addWidget(self.search,1);filters.addWidget(self.category);body.addLayout(filters)
        self.table=self.make_table(['Dispositivo','Categoria','Barramento','Driver','Estado'])
        self.details=QPlainTextEdit();self.details.setReadOnly(True)
        splitter=QSplitter();splitter.addWidget(self.table);splitter.addWidget(self.details)
        splitter.setStretchFactor(0,3);splitter.setStretchFactor(1,2);body.addWidget(splitter)
        self.table.itemSelectionChanged.connect(self.select_device)
        self.search.textChanged.connect(self.filter_devices);self.category.currentTextChanged.connect(self.filter_devices)
        self.device_options_button=self.tool_button('Drivers e firmware do dispositivo','preferences-devices')
        self.device_options_button.clicked.connect(self.show_device_options);body.addWidget(self.device_options_button,0,Qt.AlignmentFlag.AlignLeft)
        self.tabs.addTab(hardware,'Hardware e drivers')
        firmware=QWidget();body=QVBoxLayout(firmware)
        explanation=QLabel('Opções relacionadas ao hardware detectado nos repositórios configurados. Firmware complementa o driver; os drivers integrados são atualizados com o kernel. A versão exibida é a do pacote. A relação com um dispositivo não significa que a instalação seja necessária.')
        explanation.setWordWrap(True);body.addWidget(explanation)
        options=QHBoxLayout()
        self.check_updates_button=self.tool_button('Buscar atualizações','view-refresh')
        self.check_updates_button.clicked.connect(self.check_updates);options.addWidget(self.check_updates_button)
        self.show_all=QCheckBox('Mostrar também firmwares de outras famílias')
        self.show_all.toggled.connect(self.render_software)
        self.all_devices_button=self.tool_button('Todos os dispositivos','computer')
        self.all_devices_button.clicked.connect(self.clear_device_filter);options.addWidget(self.all_devices_button)
        help_button=self.tool_button('Ajuda NVIDIA','help-contents')
        help_button.clicked.connect(self.nvidia_help);options.addWidget(help_button)
        options.addStretch();body.addLayout(options);body.addWidget(self.show_all)
        self.software_summary=QLabel();self.software_summary.setWordWrap(True);body.addWidget(self.software_summary)
        self.firmware_table=self.make_table(['Dispositivo / componente','Tipo','Pacote','Instalada','Disponível','Situação'])
        body.addWidget(self.firmware_table)
        self.install_button=QPushButton('Selecione uma opção');self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install_selected);self.firmware_table.itemSelectionChanged.connect(self.update_install_button)
        body.addWidget(self.install_button,0,Qt.AlignmentFlag.AlignLeft)
        self.install_log=QPlainTextEdit();self.install_log.setReadOnly(True);self.install_log.setMaximumHeight(160);body.addWidget(self.install_log);self.install_log.hide()
        self.tabs.addTab(firmware,'Drivers e atualizações')
        self.tabs.setCurrentIndex(1)
        self.diagnostics=QPlainTextEdit();self.diagnostics.setReadOnly(True);self.tabs.addTab(self.diagnostics,'Diagnósticos')
        self.status=QLabel('Consultando hardware…');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(30000)
        self.refresh()

    @staticmethod
    def tool_button(text,icon):
        button=QToolButton();button.setText(text);button.setIcon(QIcon.fromTheme(icon))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);button.setAutoRaise(True)
        return button

    @staticmethod
    def make_table(headers):
        table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide();table.setAlternatingRowColors(True)
        table.setShowGrid(False);table.setFrameShape(QFrame.Shape.NoFrame)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def refresh(self):
        if self.process is not None:return
        self.status.setText('Consultando hardware…')
        self.run(sys.executable,[str(Path(__file__).with_name('hardware.py'))],False)

    def run(self,program,args,installing):
        if self.process is not None:return
        process=QProcess(self);self.process=process;self.installing=installing
        updating=installing and args[-1]=='--refresh'
        self.refresh_button.setEnabled(False);self.update_install_button()
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels if installing else QProcess.ProcessChannelMode.SeparateChannels)
        if installing:
            self.status.setText('Atualizando índices dos repositórios…' if updating else 'Aguardando autorização / instalação do pacote…')
            self.install_log.show();self.install_log.clear()
            process.readyReadStandardOutput.connect(lambda:self.install_log.appendPlainText(bytes(process.readAllStandardOutput()).decode(errors='replace')))
        def done(code,status):
            output=bytes(process.readAllStandardOutput()).decode(errors='replace')
            error=bytes(process.readAllStandardError()).decode(errors='replace') if not installing else ''
            self.process=None;self.installing=False;self.refresh_button.setEnabled(True);self.update_install_button()
            process.deleteLater()
            if installing:
                if output:self.install_log.appendPlainText(output)
                message=(('Índices atualizados. Consultando as versões disponíveis.' if updating else 'Pacote instalado. Reinicie o sistema para usar o kernel ou firmware atualizado.') if code==0 else 'Operação não concluída ou autorização cancelada. Consulte a saída acima; as versões listadas podem vir de índices anteriores.')
                self.install_log.appendPlainText(message)
                self.status.setText(message);QMessageBox.information(self,'Drivers e atualizações',message)
                self.refresh()
            else:
                try:
                    data=json.loads(output)
                    if code or 'error' in data:raise ValueError(data.get('error',error or 'Falha na consulta.'))
                    self.populate(data)
                except (ValueError,KeyError) as exc:self.status.setText('Não foi possível atualizar: '+str(exc))
        process.finished.connect(done)
        def failed(error):
            if error==QProcess.ProcessError.FailedToStart:
                self.process=None;self.installing=False;self.refresh_button.setEnabled(True);self.update_install_button()
                self.status.setText('Não foi possível iniciar '+program);process.deleteLater()
        process.errorOccurred.connect(failed)
        process.start(program,args)

    def populate(self,data):
        self.data=data
        previous=self.category.currentText();self.category.blockSignals(True)
        self.category.clear();self.category.addItem('Todas as categorias')
        self.category.addItems(sorted({r['category'] for r in data['devices']}))
        self.category.setCurrentIndex(max(0,self.category.findText(previous)));self.category.blockSignals(False)
        self.filter_devices()
        self.render_software()
        self.diagnostics.setPlainText('Kernel: '+data['kernel']+'\nArquitetura: '+data['architecture']+'\n\n'+
            '\n'.join(data['warnings'])+'\n\nMensagens recentes do kernel acessíveis ao usuário (até 600 linhas consultadas):\n'+
            ('\n'.join(data['diagnostics']) or 'Nenhuma mensagem correspondente acessível. Isso não confirma ausência de falhas.'))
        self.status.setText(f"{len(data['devices'])} dispositivos · atualização a cada 30 s. "+' '.join(data['warnings']))
        self.export_button.setEnabled(True);self.update_install_button()

    def filter_devices(self):
        previous=self.visible[self.table.currentRow()]['id'] if 0<=self.table.currentRow()<len(self.visible) else None
        text=self.search.text().casefold();category=self.category.currentText()
        self.visible=[r for r in self.data.get('devices',[]) if (category=='Todas as categorias' or category==r['category']) and
                      text in ' '.join([r['name'],r['vendor'],r['driver'],r['hardware_id'],r['id']]).casefold()]
        self.table.setRowCount(len(self.visible));self.details.clear()
        for i,row in enumerate(self.visible):
            for j,key in enumerate(('name','category','bus','driver','status')):self.table.setItem(i,j,QTableWidgetItem(row[key] or '—'))
        selected=next((i for i,r in enumerate(self.visible) if r['id']==previous),0)
        if self.visible:self.table.selectRow(selected);self.select_device()

    def select_device(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.visible):return
        row=self.visible[index]
        lines=[row['name'],'Fabricante: '+row['vendor'],'ID: '+row['hardware_id'],'Barramento: '+row['id'],
               'Driver: '+(row['driver'] or 'Não associado'), 'Módulos: '+(', '.join(row['modules']) or 'Não identificado / integrado ao kernel'),
               'Modalias: '+(row['modalias'] or 'Não informado')]
        if not row['driver']:lines+=['','Sem vínculo não significa necessariamente falta de suporte: interfaces auxiliares podem não precisar de driver. Investigue o ID e os diagnósticos.']
        if not row['driver'] or row.get('unbound_aliases'):
            lines+=['Candidatos locais: '+(', '.join(row.get('candidates',[])) or 'Nenhum identificado'),row.get('support_note','')]
        lines+=['','Firmware declarado pelos módulos (inclui outros modelos da mesma família):']
        for module in row['modules']:
            details=self.data['modules'].get(module,{})
            lines.append(module+': '+details.get('error',''))
            if not details.get('error') and not details.get('firmware'):lines.append('Nenhum arquivo declarado nos metadados.')
            for entry in details.get('firmware',[]):lines.append(('Presente: ' if entry['present'] else 'Não encontrado: ')+entry['name'])
        lines+=['','Um arquivo não encontrado pode ser opcional ou pertencer a outro modelo; consulte as mensagens do kernel antes de instalar firmware.']
        self.details.setPlainText('\n'.join(lines))

    def render_software(self):
        previous=self.selected_software()
        package=previous['package'] if previous else None
        self.firmware_table.blockSignals(True)
        self.software_rows=[r for r in self.data.get('firmware',[]) if
                            (self.show_all.isChecked() or r['related']) and
                            (self.device_filter is None or any(d['id']==self.device_filter for d in r.get('devices',[])))]
        # Actionable options first, then up-to-date/unavailable entries for context.
        self.software_rows.sort(key=lambda r:(not bool(r.get('action')),r['package']))
        self.firmware_table.setRowCount(len(self.software_rows))
        for i,row in enumerate(self.software_rows):
            names=', '.join(dict.fromkeys(d['name'] for d in row.get('devices',[])))
            values=[names or row['description'],row['type'],row['package'],row['installed_version'] or 'Não instalado',
                    row['candidate'] or 'Indisponível',row['status']]
            for j,value in enumerate(values):
                item=QTableWidgetItem(value)
                item.setToolTip(row.get('notes','') or '\n'.join(d['name']+': '+d['reason'] for d in row.get('devices',[])) or row['description'])
                self.firmware_table.setItem(i,j,item)
        if self.software_rows:
            index=next((i for i,r in enumerate(self.software_rows) if r['package']==package),0)
            self.firmware_table.selectRow(index)
        self.firmware_table.blockSignals(False)
        available=sum(bool(r.get('action')) for r in self.software_rows)
        scope=next((r['name'] for r in self.data.get('devices',[]) if r['id']==self.device_filter),'Todos os dispositivos')
        message=f'{scope} · {available} opção(ões) para instalar ou atualizar.'
        if not self.software_rows:message+=' Nenhum pacote correspondente encontrado no catálogo suportado. Isso não comprova ausência de suporte.'
        message+=' Use “Buscar atualizações” para atualizar os índices do APT. NVIDIA é verificado pelo detector Debian; outros fornecedores proprietários ainda não estão integrados.'
        self.software_summary.setText(message)
        self.update_install_button()

    def selected_software(self):
        index=self.firmware_table.currentRow()
        return self.software_rows[index] if 0<=index<len(self.software_rows) else None

    def show_device_options(self):
        index=self.table.currentRow()
        if 0<=index<len(self.visible):
            self.device_filter=self.visible[index]['id'];self.render_software();self.tabs.setCurrentIndex(1)

    def clear_device_filter(self):
        self.device_filter=None;self.render_software()

    def update_install_button(self):
        row=self.selected_software()
        action=row.get('action','') if row else ''
        self.install_button.setText({'install':'Instalar selecionado…','upgrade':'Atualizar selecionado…'}.get(action,'Selecione uma opção disponível'))
        self.install_button.setEnabled(self.process is None and bool(action))
        self.check_updates_button.setEnabled(self.process is None)

    def check_updates(self):
        if self.process is None:
            self.run('/usr/bin/pkexec',['/usr/lib/linuxbr-device-manager/install-firmware','--refresh'],True)

    def install_selected(self):
        row=self.selected_software()
        if self.process is not None or not row or not row.get('action'):return
        package=row['package']
        verb='Atualizar' if row['action']=='upgrade' else 'Instalar'
        message=f"{verb} {package}?\nVersão instalada: {row['installed_version'] or 'não instalado'}\nVersão disponível: {row['candidate']}\n\nO APT verificará a versão disponível novamente. Será solicitada autorização administrativa. Reinicie após concluir. No Live, essa alteração não é transferida automaticamente para futuras instalações."
        if row['type']=='Kernel':message+='\n\nEsta opção atualiza o kernel Debian e seus drivers integrados; não garante mudanças em cada driver individual.'
        if row['type']=='Proprietário':
            message+='\n\nInstalará o driver NVIDIA recomendado pelo Debian, DKMS e headers. Pode substituir Nouveau após reiniciar. Não desative o computador durante a compilação dos módulos.\nPacotes adicionais: '+', '.join(row.get('prerequisites',[]))
        if row.get('notes'):message+='\n\n'+row['notes']
        answer=QMessageBox.question(self,'Drivers e atualizações',message)
        if answer==QMessageBox.StandardButton.Yes:
            self.run('/usr/bin/pkexec',['/usr/lib/linuxbr-device-manager/install-firmware',package],True)

    def nvidia_help(self):
        QMessageBox.information(self,'NVIDIA e Secure Boot',
            'A lista usa os IDs PCI e o nvidia-detect do Debian. GPUs muito novas, legadas ou combinações de ramos diferentes exigem análise manual. Atualize os índices e o detector quando houver uma versão disponível.\n\n'
            'A instalação exige headers do kernel em execução. Execute no sistema instalado; não são usados instaladores .run nem repositórios externos. Reinicie após concluir.\n\n'
            'Com Secure Boot ativo, a chave DKMS precisa estar cadastrada. No terminal do Linux BR instalado:\n'
            'sudo apt install dkms mokutil\nsudo dkms generate_mok\nsudo mokutil --import /var/lib/dkms/mok.pub\n\n'
            'Defina uma senha temporária, reinicie e confirme Enroll MOK no gerenciador do firmware. Depois verifique:\n'
            'mokutil --test-key /var/lib/dkms/mok.pub\n\n'
            'Configurações que usam outra chave DKMS precisam de ajuste administrativo. A aplicação não desativa Secure Boot nem cadastra chaves automaticamente.')

    def export_report(self):
        if not self.data:return
        path,_=QFileDialog.getSaveFileName(self,'Exportar inventário sem logs','linuxbr-hardware.json','JSON (*.json)')
        if path:
            try:Path(path).write_text(json.dumps({k:v for k,v in self.data.items() if k!='diagnostics'},ensure_ascii=False,indent=2)+'\n')
            except OSError as error:QMessageBox.warning(self,'Falha ao exportar',str(error))

    def shutdown(self):
        if self.installing:return False
        self.timer.stop()
        if self.process is not None:
            self.process.kill();self.process.waitForFinished(1000)
        return True

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Dispositivos — Linux BR');self.setWindowIcon(QIcon.fromTheme('computer'))
        self.resize(1180,740);self.devices=Devices();self.setCentralWidget(self.devices)
    def closeEvent(self,event):
        if not self.devices.shutdown():
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de pacotes terminar.');event.ignore()
        else:event.accept()

if __name__=='__main__':
    application=QApplication(sys.argv);window=Window();window.show();sys.exit(application.exec())
