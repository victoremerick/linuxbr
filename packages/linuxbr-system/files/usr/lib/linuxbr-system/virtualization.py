#!/usr/bin/python3
"""Graphical administration of local and remote virtual machines."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QDialog,
    QDialogButtonBox,QFormLayout,QSpinBox,QCheckBox,QFileDialog,QMessageBox,QTabWidget,
    QPlainTextEdit,QInputDialog,QSplitter,QProgressDialog,QMenu)
import virtualization_backend as backend
import virtualization_disks as disk_tools
import virtualization_observability as observations
import virtualization_preferences as preferences


def button(text,icon,callback):
    value=QPushButton(QIcon.fromTheme(icon),text);value.clicked.connect(callback);return value


def spin(minimum,maximum,value,suffix=''):
    result=QSpinBox();result.setRange(minimum,maximum);result.setValue(value);result.setSuffix(suffix);return result


def table(headers):
    value=QTableWidget(0,len(headers));value.setHorizontalHeaderLabels(headers)
    value.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    value.setSelectionBehavior(value.SelectionBehavior.SelectRows);value.setSelectionMode(value.SelectionMode.SingleSelection)
    value.setEditTriggers(value.EditTrigger.NoEditTriggers);value.setAlternatingRowColors(True)
    value.verticalHeader().hide();return value


def populate(widget,rows,keys,select_first=True):
    previous=widget.currentRow();old=selected(widget);identity=(old.get('id') or old.get('name')) if old else None
    widget.clearSelection();widget.setCurrentItem(None);widget.setRowCount(len(rows))
    for i,row in enumerate(rows):
        widget.setRowHidden(i,False)
        for j,key in enumerate(keys):
            item=QTableWidgetItem(str(row.get(key,'')));item.setData(Qt.ItemDataRole.UserRole,row);widget.setItem(i,j,item)
    fallback = min(max(previous,0),len(rows)-1) if select_first else -1
    index = next((i for i,row in enumerate(rows) if identity is not None
                  and (row.get('id') or row.get('name'))==identity), fallback)
    if index >= 0:widget.selectRow(index)


def selected(widget):
    row = widget.currentRow()
    if row >= 0 and not widget.isRowHidden(row) and widget.selectedItems():
        return widget.item(row,0).data(Qt.ItemDataRole.UserRole)
    return None


class Task(QThread):
    result=pyqtSignal(object);failed=pyqtSignal(str);progress=pyqtSignal(int)
    def __init__(self,uri,operation,manager=None):super().__init__();self.uri=uri;self.operation=operation;self.manager=manager
    def run(self):
        try:
            if self.manager is None:self.manager=backend.Manager(self.uri)
            self.manager.progress=self.progress.emit;self.manager.cancelled=self.isInterruptionRequested;self.result.emit(self.operation(self.manager))
        except Exception as error:self.failed.emit(str(error))
        finally:
            if self.manager:self.manager.progress=lambda _:None;self.manager.cancelled=lambda:False


class Form(QDialog):
    def __init__(self,title,parent):
        super().__init__(parent);self.setWindowTitle(title);self.resize(620,480)
        self.body=QVBoxLayout(self);self.form=QFormLayout();self.form.setFieldGrowthPolicy(self.form.FieldGrowthPolicy.AllNonFixedFieldsGrow);self.body.addLayout(self.form)
        self.controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.controls.accepted.connect(self.accept);self.controls.rejected.connect(self.reject)
    def finish(self):self.body.addWidget(self.controls)


class Performance(QDialog):
    def __init__(self, owner, vm):
        super().__init__(owner)
        self.setWindowTitle('Desempenho · ' + vm['name'])
        self.resize(885, 475)
        self.uri, self.identifier = owner.uri, vm['id']
        self.samples, self.task = [], None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.interval = QComboBox()
        for seconds in (2, 5, 15, 60):
            self.interval.addItem(f'{seconds} s', seconds * 1000)
        self.interval.setCurrentIndex(1)
        form.addRow('Intervalo de coleta', self.interval)
        layout.addLayout(form)
        self.status = QLabel('Consultando a máquina virtual…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.results = table(['Horário local', 'CPU', 'RAM do convidado', 'Leitura', 'Gravação', 'Rede ↓', 'Rede ↑'])
        self.results.setAccessibleName('Histórico de desempenho da máquina virtual')
        layout.addWidget(self.results)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.interval.currentIndexChanged.connect(self.schedule)
        self.schedule()
        self.poll()

    def schedule(self):
        self.timer.start(self.interval.currentData())

    def poll(self):
        if self.task:
            return
        task = Task(self.uri, lambda manager: observations.sample(manager.domain(self.identifier)))
        self.task = task
        task.result.connect(self.show_sample)
        task.failed.connect(self.status.setText)
        task.finished.connect(self.finished_sample)
        task.finished.connect(task.deleteLater)
        task.start()

    def finished_sample(self):
        if self.task and self.task.manager:
            self.task.manager.close()
        self.task = None

    def show_sample(self, observed):
        previous = self.samples[-1][0] if self.samples else None
        self.samples = (self.samples + [(observed, observations.rates(previous, observed))])[-120:]
        self.status.setText('Últimas 120 amostras desta janela. A memória em uso depende do suporte do convidado.'
                            if observed['active'] else 'Máquina desligada. A coleta continua enquanto esta janela estiver aberta.')
        rows = []
        for item, rates in reversed(self.samples):
            capacity = item['memory'] // 1024
            memory = '—'
            if item['active']:
                memory = f'{item["actual"] // 1024} / {capacity} MiB' if item['actual'] is not None else f'{capacity} MiB alocados'
            row = dict(time=item['time'][11:], memory=memory,
                       cpu=f'{rates["cpu"]:.1f} %' if rates['cpu'] is not None else '—')
            row.update({key: f'{rates[key] / 1024:.1f} KiB/s' if rates[key] is not None else '—'
                        for key in ('read', 'write', 'rx', 'tx')})
            rows.append(row)
        populate(self.results, rows, ['time', 'cpu', 'memory', 'read', 'write', 'rx', 'tx'], select_first=False)

    def done(self, result):
        if self.task:
            self.status.setText('Aguarde o término da consulta em andamento para fechar.')
            return
        self.timer.stop()
        super().done(result)


class Editor(QDialog):
    def __init__(self,owner,row,data):
        super().__init__(owner);self.owner=owner;self.row=row;self.data=data
        self.setWindowTitle('Configurações de '+row['name']);self.resize(980,640)
        body=QVBoxLayout(self);note=QLabel('Configuração persistente do hospedeiro '+owner.uri+'. Desligue a VM para alterar hardware.');note.setWordWrap(True);body.addWidget(note)
        self.tabs=QTabWidget();body.addWidget(self.tabs,1)
        resources=QWidget();form=QFormLayout(resources);self.memory=spin(256,262144,row['memory'],' MiB');self.cpus=spin(1,256,row['cpus']);self.autostart=QCheckBox('Iniciar com o serviço de virtualização');self.autostart.setChecked(row['autostart'])
        form.addRow('Memória:',self.memory);form.addRow('Processadores virtuais:',self.cpus);form.addRow(self.autostart)
        form.addRow(button('Aplicar recursos','dialog-ok-apply',self.resources));self.tabs.addTab(resources,QIcon.fromTheme('computer'),'Recursos')
        network=QWidget();layout=QVBoxLayout(network);self.nics=table(['Modelo','Tipo','Rede / ponte','MAC'])
        populate(self.nics,[dict(n,source_label=', '.join(n['source'].values())) for n in data['interfaces']],['model','kind','source_label','mac']);layout.addWidget(self.nics)
        actions=QHBoxLayout();actions.addWidget(button('Adicionar adaptador','list-add',lambda:self.edit_nic(None)));actions.addWidget(button('Configurar adaptador','configure',lambda:self.edit_nic(selected(self.nics))));actions.addWidget(button('Remover adaptador','list-remove',self.remove_nic));layout.addLayout(actions)
        self.tabs.addTab(network,QIcon.fromTheme('network-wired'),'Adaptadores de rede')
        storage=QWidget();layout=QVBoxLayout(storage);self.disks=table(['Dispositivo','Destino','Origem','Formato'])
        populate(self.disks,[dict(d,target_label=d['target'].get('dev',''),source_label=', '.join(d['source'].values())) for d in data['storage']],['device','target_label','source_label','format']);layout.addWidget(self.disks)
        actions=QHBoxLayout();actions.addWidget(button('Conectar volume','drive-harddisk',self.attach));actions.addWidget(button('Imagem ISO','media-optical',self.iso));actions.addWidget(button('Desconectar','list-remove',self.detach));layout.addLayout(actions)
        text=QLabel('Desconectar mantém o arquivo. Crie ou expanda volumes na página Armazenamento do gerenciador.');text.setWordWrap(True);layout.addWidget(text);self.tabs.addTab(storage,QIcon.fromTheme('drive-harddisk'),'Discos e mídias')
        checkpoints=QWidget();layout=QVBoxLayout(checkpoints);self.snapshots=table(['Nome','Checkpoint anterior','Estado','Data']);snapshots=[]
        for item in data['snapshots']:
            try:date=time.strftime('%d/%m/%Y %H:%M',time.localtime(int(item['created'])))
            except (ValueError,TypeError,OverflowError):date='Não informada'
            snapshots.append(dict(item,date=date,state_label={'running':'Em execução','paused':'Pausada','shutoff':'Desligada'}.get(item['state'],item['state'])))
        populate(self.snapshots,snapshots,['name','parent','state_label','date']);layout.addWidget(self.snapshots)
        actions=QHBoxLayout()
        for title,action,icon in [('Criar checkpoint','create','list-add'),('Voltar ao checkpoint','restore','edit-undo'),('Excluir checkpoint','remove','edit-delete')]:actions.addWidget(button(title,icon,lambda _=False,a=action:self.checkpoint(a)))
        layout.addLayout(actions);label=QLabel('Com a VM desligada, o checkpoint inclui discos, firmware e TPM. Cópias com memória exigem BIOS sem TPM. Voltar substitui o estado salvo; checkpoint não substitui backup.');label.setWordWrap(True);layout.addWidget(label);self.tabs.addTab(checkpoints,QIcon.fromTheme('document-revert'),'Checkpoints')
        hardware=QWidget();form=QFormLayout(hardware);root=ET.fromstring(data['xml']);operating=root.find('os');devices=root.find('devices')
        self.uefi=QCheckBox('UEFI');self.uefi.setChecked(operating.get('firmware')=='efi' or operating.find('loader') is not None)
        self.secure=QCheckBox('Secure Boot');feature=operating.find("firmware/feature[@name='secure-boot']");loader=operating.find('loader');self.secure.setChecked((feature is not None and feature.get('enabled')=='yes') or (loader is not None and loader.get('secure')=='yes'))
        self.tpm=QCheckBox('TPM 2.0 virtual');self.tpm.setChecked(devices.find('tpm') is not None);self.audio=QCheckBox('Dispositivo de áudio');self.audio.setChecked(devices.find('sound') is not None);self.video=QComboBox();self.video.addItems(['vga','virtio','qxl']);model=devices.find('video/model');self.video.setCurrentText(model.get('type','vga') if model is not None else 'vga')
        for caption,widget in [('',self.uefi),('',self.secure),('',self.tpm),('Vídeo:',self.video),('',self.audio)]:form.addRow(caption,widget)
        form.addRow(button('Aplicar dispositivos e firmware','dialog-ok-apply',self.hardware));self.tabs.addTab(hardware,QIcon.fromTheme('preferences-devices-cpu'),'Firmware e dispositivos')
        certificates=button('Atualizar certificados Secure Boot…','security-high',self.update_certificates);nvram=operating.find('nvram');certificates.setEnabled(nvram is not None and nvram.get('format','raw')=='raw');certificates.setToolTip('Disponível para variáveis UEFI no formato raw.');form.addRow(certificates)
        bootpage=QWidget();form=QFormLayout(bootpage);self.boot_order=QComboBox()
        for title,order in [('Disco, mídia e rede',['hd','cdrom','network']),('Mídia, disco e rede',['cdrom','hd','network']),('Rede, disco e mídia',['network','hd','cdrom'])]:self.boot_order.addItem(title,order)
        first=operating.find('boot');self.boot_order.setCurrentIndex({'hd':0,'cdrom':1,'network':2}.get(first.get('dev') if first is not None else 'hd',0));self.boot_menu=QCheckBox('Exibir menu de inicialização');menu=operating.find('bootmenu');self.boot_menu.setChecked(menu is None or menu.get('enable')=='yes')
        self.cpu_mode=QComboBox()
        for title,value in [('Preservar modelo atual','preserve'),('Modelo compatível do hospedeiro','host-model'),('CPU do hospedeiro (migração restrita)','host-passthrough')]:self.cpu_mode.addItem(title,value)
        self.cpu_limit=spin(0,100,0,' %');self.cpu_limit.setSpecialValueText('Sem limite');period=int(root.findtext('cputune/global_period','100000'));quota=int(root.findtext('cputune/global_quota','0'));self.cpu_limit.setValue(min(100,max(0,int(quota*100/(period*max(1,row['cpus']))))))
        for title,widget in [('Prioridade de boot:',self.boot_order),('',self.boot_menu),('Processador exposto ao convidado:',self.cpu_mode),('Limite total de CPU:',self.cpu_limit)]:form.addRow(title,widget)
        note=QLabel('O limite se aplica ao conjunto de processadores virtuais. A topologia NUMA e ajustes específicos permanecem disponíveis em Avançado.');note.setWordWrap(True);form.addRow(note);form.addRow(button('Aplicar inicialização e CPU','dialog-ok-apply',self.guest_options));self.tabs.addTab(bootpage,QIcon.fromTheme('system-run'),'Inicialização e CPU')
        advanced=QWidget();layout=QVBoxLayout(advanced);label=QLabel('Configuração completa: topologia, dispositivos e integração. A edição preserva as extensões existentes e salva uma cópia anterior. Altere somente opções conhecidas; a aplicação valida o XML pelo libvirt.');label.setWordWrap(True);layout.addWidget(label)
        layout.addWidget(button('Abrir editor gráfico completo…','preferences-system',self.complete_editor))
        self.xml=QPlainTextEdit(data['xml']);self.xml.setAccessibleName('XML da configuração persistente da VM');layout.addWidget(self.xml,1);layout.addWidget(button('Aplicar configuração avançada…','dialog-ok-apply',self.apply_xml));self.tabs.addTab(advanced,QIcon.fromTheme('preferences-other'),'Avançado')
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(self.reject);body.addWidget(close)

    def execute(self,operation):
        if self.owner.tasks:
            QMessageBox.information(self,'Operação em andamento','Aguarde a conclusão da operação antes de aplicar outra alteração.');return
        self.setEnabled(False)
        self.owner.work(operation,lambda _:self.accept(),lambda _:self.setEnabled(True))

    def complete_editor(self):
        if self.owner.complete_tool(self.row['id']):self.accept()

    def resources(self):self.execute(lambda m:m.resources(self.row['id'],self.memory.value(),self.cpus.value(),self.autostart.isChecked()))

    def guest_options(self):
        spec=dict(boot=self.boot_order.currentData(),bootmenu=self.boot_menu.isChecked(),cpu=self.cpu_mode.currentData(),cpu_percent=self.cpu_limit.value())
        self.execute(lambda m:m.guest_options(self.row['id'],spec))

    def hardware(self):
        spec=dict(uefi=self.uefi.isChecked(),secure_boot=self.secure.isChecked(),tpm=self.tpm.isChecked(),video=self.video.currentText(),audio=self.audio.isChecked())
        self.execute(lambda m:m.hardware(self.row['id'],spec))

    def update_certificates(self):
        if self.owner.confirm('Adicionar as autoridades Microsoft de 2023 às variáveis UEFI? A VM deve estar desligada e um checkpoint completo será criado antes da alteração. Guarde as chaves de recuperação de volumes criptografados. PK, revogações e preferências de Secure Boot serão preservadas.'):self.execute(lambda m:m.update_certificates(self.row['id']))

    def edit_nic(self,item):
        dialog=Form('Adaptador de rede',self);kind=QComboBox()
        for label,value in [('Rede virtual','network'),('Ponte existente no hospedeiro','bridge'),('NAT do processo QEMU','user')]:kind.addItem(label,value)
        source=QComboBox();source.setEditable(True)
        for n in self.data['networks']:source.addItem(n['name'])
        model=QComboBox();model.addItems(['virtio','e1000e','rtl8139']);mac=QLineEdit();mac.setPlaceholderText('Automático, ou 52:54:00:12:34:56')
        connected=QCheckBox('Cabo conectado');connected.setChecked(True);vlan=spin(0,4094,0);vlan.setSpecialValueText('Sem marcação');bandwidth=spin(0,10000000,0,' KiB/s');bandwidth.setSpecialValueText('Sem limite')
        if item:
            kind.setCurrentIndex(max(0,kind.findData(item['kind'])));source.setCurrentText(next(iter(item['source'].values()),''));model.setCurrentText(item['model']);mac.setText(item['mac'])
            root=ET.fromstring(item['xml']);tag=root.find('vlan/tag');limit=root.find('bandwidth/inbound');link=root.find('link')
            vlan.setValue(int(tag.get('id','0')) if tag is not None else 0);bandwidth.setValue(int(limit.get('average','0')) if limit is not None else 0);connected.setChecked(link is None or link.get('state')!='down')
        for label,widget in [('Conexão:',kind),('Rede ou ponte:',source),('Modelo:',model),('Endereço MAC:',mac),('VLAN:',vlan),('Limite de entrada e saída:',bandwidth),('',connected)]:dialog.form.addRow(label,widget)
        dialog.finish()
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        spec=dict(kind=kind.currentData(),source=source.currentText(),model=model.currentText(),mac=mac.text(),vlan=vlan.value(),bandwidth=bandwidth.value(),connected=connected.isChecked())
        self.execute(lambda m:m.set_interface(self.row['id'],item['index'] if item else None,spec))

    def remove_nic(self):
        item=selected(self.nics)
        if item and self.owner.confirm('Remover este adaptador da configuração da VM?'):self.execute(lambda m:m.set_interface(self.row['id'],item['index'],{},True))

    def detach(self):
        item=selected(self.disks)
        if item and self.owner.confirm('Desconectar este dispositivo? O arquivo do disco será preservado.'):self.execute(lambda m:m.storage_action(self.row['id'],'detach',item))

    def iso(self):
        if self.owner.uri in ('qemu:///system','qemu:///session'):
            action,ok=QInputDialog.getItem(self,'Mídia de instalação','Ação:',['Selecionar arquivo ISO…','Ejetar mídia'],0,False)
            if not ok:return
            if action=='Ejetar mídia':path=''
            else:path,_=QFileDialog.getOpenFileName(self,'Selecionar mídia de instalação','','Imagens ISO (*.iso);;Todos os arquivos (*)');ok=bool(path)
        else:path,ok=QInputDialog.getText(self,'Mídia de instalação','Caminho absoluto da ISO no hospedeiro; vazio para ejetar:')
        if ok:self.execute(lambda m:m.storage_action(self.row['id'],'iso',{'path':path}))

    def attach(self):
        pool,ok=QInputDialog.getItem(self,'Local de armazenamento','Local:',[p['name'] for p in self.data['pools'] if p['active']],0,False)
        if not ok:return
        def choose(volumes):
            name,ok=QInputDialog.getItem(self,'Conectar volume','Volume existente:',[v['name'] for v in volumes],0,False)
            if ok:self.execute(lambda m:m.storage_action(self.row['id'],'attach',dict(pool=pool,volume=name)))
        self.owner.work(lambda m:m.volumes(pool),choose)

    def checkpoint(self,action):
        memory=False
        if action=='create':
            dialog=Form('Criar checkpoint',self);field=QLineEdit();include=QCheckBox('Incluir memória da VM em execução (BIOS, sem TPM)');root=ET.fromstring(self.data['xml']);supported=root.find('os/nvram') is None and root.find('os/loader') is None and root.find('os').get('firmware')!='efi' and root.find('devices/tpm') is None;include.setEnabled(supported);dialog.form.addRow('Nome:',field);dialog.form.addRow(include)
            note=QLabel('Com a VM desligada, a cópia combina discos, firmware e TPM. A memória só pode ser incluída em VMs BIOS sem TPM nesta edição.');note.setWordWrap(True);dialog.body.addWidget(note);dialog.finish();ok=dialog.exec()==QDialog.DialogCode.Accepted;name=field.text().strip();memory=include.isChecked()
        else:
            row=selected(self.snapshots);name=row['name'] if row else '';ok=bool(row)
        if ok and self.owner.confirm({'create':'Criar um checkpoint do estado selecionado?','restore':'Voltar ao checkpoint e substituir discos e estado salvo? Uma cópia com memória será retomada pausada.','remove':'Excluir este checkpoint? Esta ação pode consolidar dados dos discos.'}[action]):self.execute(lambda m:m.snapshot(self.row['id'],action,name,memory))

    def apply_xml(self):
        if self.owner.confirm('Aplicar a configuração avançada desta VM? Uma cópia do XML atual será salva.'):self.execute(lambda m:m.replace_xml(self.row['id'],self.xml.toPlainText()))


class Window(QMainWindow):
    def __init__(self,uri=None):
        from desktop_theme import initialize
        initialize()
        super().__init__();self.preferences=preferences.load()
        try:self.uri=backend.checked_uri(uri or self.preferences.get('last_uri','qemu:///system'))
        except ValueError:self.uri='qemu:///system'
        self.tasks=set();self.refreshing=False;self.data={};self.editors=[];self.manager=None;self.last_metrics={}
        self.setWindowTitle('Linux BR — Máquinas virtuais');self.setWindowIcon(QIcon.fromTheme('computer'));self.resize(1160,680)
        main=QWidget();self.setCentralWidget(main);body=QVBoxLayout(main);body.setContentsMargins(24,20,24,20)
        title=QLabel('Máquinas virtuais');title.setStyleSheet('font-size:28px;font-weight:600');body.addWidget(title)
        row=QHBoxLayout();self.host_profile=QComboBox();self.host_profile.addItem('Este computador — administração','qemu:///system');self.host_profile.addItem('Este computador — minha conta','qemu:///session');self.host_profile.addItem('Outro hospedeiro (SSH)…','');profile=self.host_profile.findData(self.uri);self.host_profile.setCurrentIndex(profile if profile>=0 else 2);row.addWidget(self.host_profile)
        self.address=QLineEdit(self.uri);self.address.setAccessibleName('Endereço avançado do hospedeiro');self.address.setVisible(self.uri not in ('qemu:///system','qemu:///session'));row.addWidget(self.address,1);row.addWidget(button('Conectar','network-connect',self.connect_host));body.addLayout(row)
        for uri in self.preferences.get('hosts',[]) if isinstance(self.preferences.get('hosts'),list) else []:
            try:backend.checked_uri(uri)
            except ValueError:continue
            if uri.startswith('qemu+ssh://') and self.host_profile.findData(uri)<0:self.host_profile.addItem(uri.split('@',1)[1].removesuffix('/system')+' (SSH)',uri)
        profile=self.host_profile.findData(self.uri)
        if profile>=0:self.host_profile.setCurrentIndex(profile)
        row.addWidget(button('Preferências','configure',self.configure))
        row.addWidget(button('Orçamento de recursos','view-statistics',self.resource_budget))
        def profile_changed():
            value=self.host_profile.currentData();self.address.setVisible(not bool(value));self.address.setText(value or 'qemu+ssh://usuario@servidor/system')
        self.host_profile.activated.connect(profile_changed)
        self.status=QLabel('Conectando ao serviço de virtualização…');self.status.setWordWrap(True);body.addWidget(self.status)
        self.pages=QTabWidget();body.addWidget(self.pages,1)
        self.pages.setEnabled(False)
        machines=QWidget();layout=QVBoxLayout(machines);self.vm_search=QLineEdit();self.vm_search.setPlaceholderText('Pesquisar máquinas virtuais pelo nome ou estado…');self.vm_search.setAccessibleName('Pesquisar máquinas virtuais');self.vm_search.textChanged.connect(self.filter_vms);layout.addWidget(self.vm_search);self.vms=table(['Nome','Estado','Memória (MiB)','Processadores','Uso de CPU']);layout.addWidget(self.vms,1)
        self.vm_search.setClearButtonEnabled(True)
        self.vms.setAccessibleName('Máquinas virtuais no hospedeiro')
        self.vm_results = QLabel();layout.addWidget(self.vm_results)
        row=QHBoxLayout()
        create=QPushButton(QIcon.fromTheme('list-add'),'Criar VM');menu=QMenu(create);menu.addAction(QIcon.fromTheme('tools-wizard'),'Assistente completo…',lambda:self.complete_tool());menu.addAction(QIcon.fromTheme('list-add'),'Criação rápida…',self.create);create.setMenu(menu);row.addWidget(create)
        self.vm_controls = {
            'settings': button('Configurações','configure',self.edit),
            'console': button('Abrir console','video-display',self.console),
            'start': button('Iniciar','media-playback-start',lambda:self.action('start')),
        }
        for control in self.vm_controls.values():
            row.addWidget(control)
        power_button = QPushButton(QIcon.fromTheme('system-shutdown'),'Energia')
        power = QMenu(power_button);power_button.setMenu(power);row.addWidget(power_button)
        for caption,icon,key in [('Desligar','system-shutdown','shutdown'),('Reiniciar','system-reboot','reboot'),
                 ('Pausar','media-playback-pause','pause'),('Continuar','media-playback-start','resume'),
                 ('Salvar estado','document-save','save'),('Desligar à força…','process-stop','poweroff')]:
            self.vm_controls[key] = power.addAction(QIcon.fromTheme(icon),caption,
                                                   lambda _checked=False,a=key:self.action(a))
        transfer_button = QPushButton(QIcon.fromTheme('document-import'),'Importar e exportar')
        transfer = QMenu(transfer_button);transfer_button.setMenu(transfer);row.addWidget(transfer_button)
        for caption,icon,callback in [('Importar VM completa…','document-import',self.import_bundle),
                                     ('Converter disco VHD ou VHDX…','drive-harddisk',self.import_hyperv),
                                     ('Recuperar arquivo de disco…','document-revert',self.recover_file),
                                     ('Importar definição XML…','text-xml',self.import_definition)]:
            transfer.addAction(QIcon.fromTheme(icon),caption,callback)
        transfer.addSeparator()
        self.vm_controls['export_vm'] = transfer.addAction(QIcon.fromTheme('document-export'),'Exportar VM completa…',self.export_bundle)
        self.vm_controls['export_xml'] = transfer.addAction(QIcon.fromTheme('text-xml'),'Exportar definição XML…',self.export_definition)
        more_button = QPushButton(QIcon.fromTheme('view-more'),'Mais ações')
        more = QMenu(more_button);more_button.setMenu(more);row.addWidget(more_button)
        for caption,icon,key,callback in [('Desempenho…','utilities-system-monitor','performance',self.performance),
                 ('Clonar…','edit-copy','clone',self.clone),
                 ('Criar acesso temporário…','dialog-password','lab_access',self.lab_access),
                 ('Delegar mídia ISO…','media-optical','delegate_media',self.delegate_media),
                 ('Checar destino da migração…','network-connect','migration_check',self.migration_check),
                 ('Migrar…','network-server','migrate',self.migrate),
                 ('Réplica offline…','document-save-as','replica',self.replicate_offline),
                 ('Remover definição…','edit-delete','remove',self.remove)]:
            self.vm_controls[key] = more.addAction(QIcon.fromTheme(icon),caption,callback)
        row.addStretch();layout.addLayout(row);self.pages.addTab(machines,QIcon.fromTheme('computer'),'Máquinas')
        self.vms.itemSelectionChanged.connect(self.update_vm_actions)
        self.update_vm_actions()
        networks=QWidget();layout=QVBoxLayout(networks);self.networks=table(['Nome','Tipo','Ativa','Início automático']);layout.addWidget(self.networks)
        row=QHBoxLayout();row.addWidget(button('Criar rede','list-add',self.create_network));row.addWidget(button('Editar rede','configure',self.edit_network))
        row.addWidget(button('DNS e DHCP','network-server',self.network_hosts))
        row.addWidget(button('Mapa da rede','network-wired',self.topology))
        for caption,action,icon in [('Ativar','start','network-connect'),('Desativar','stop','network-disconnect'),('Início automático','autostart','system-run'),('Remover','remove','edit-delete')]:row.addWidget(button(caption,icon,lambda _=False,a=action:self.network_action(a)))
        layout.addLayout(row);self.pages.addTab(networks,QIcon.fromTheme('network-wired'),'Redes e comutadores')
        storage=QWidget();layout=QVBoxLayout(storage);self.pools=table(['Local','Tipo','Ativo','Livre (GiB)','Diretório no hospedeiro']);layout.addWidget(self.pools)
        row=QHBoxLayout();row.addWidget(button('Novo local','folder-new',self.create_pool));row.addWidget(button('Volumes','drive-harddisk',self.volumes));row.addWidget(button('Criar disco','list-add',self.create_volume));row.addWidget(button('Expandir disco','zoom-in',self.resize_volume));layout.addLayout(row)
        row.addWidget(button('Cadeia de checkpoints…','view-list-tree',self.inspect_chain))
        row=QHBoxLayout()
        for title,icon,action in [('Ativar local','media-playback-start','start'),('Desativar local','media-playback-stop','stop'),('Início automático','system-run','autostart'),('Remover definição do local','edit-delete','remove')]:row.addWidget(button(title,icon,lambda _=False,a=action:self.pool_action(a)))
        layout.addLayout(row);self.pages.addTab(storage,QIcon.fromTheme('drive-harddisk'),'Armazenamento')
        self.events=QPlainTextEdit();self.events.setReadOnly(True);self.events.setMaximumBlockCount(1000);self.pages.addTab(self.events,QIcon.fromTheme('view-list-text'),'Eventos da sessão')
        self.address.textChanged.connect(lambda text:self.pages.setEnabled(bool(self.data) and not self.tasks and text.strip()==self.uri))
        self.timer=QTimer(self);self.timer.setInterval(5000);self.timer.timeout.connect(self.refresh);self.timer.start();self.refresh()
        self.vms.cellDoubleClicked.connect(lambda *_:self.edit())

    def confirm(self,text):return QMessageBox.question(self,'Confirmar operação',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes

    def complete_tool(self,identifier=None):
        if self.tasks:
            QMessageBox.information(self,'Operação em andamento','Aguarde a conclusão da operação antes de abrir outro editor.');return False
        if self.uri=='test:///default':QMessageBox.information(self,'Hospedeiro de demonstração','O editor completo exige um hospedeiro real.');return False
        argv=['/usr/bin/virt-manager','--connect',self.uri]
        argv+=['--show-domain-editor',identifier] if identifier else ['--show-domain-creator']
        try:subprocess.Popen(argv,start_new_session=True)
        except OSError as error:QMessageBox.warning(self,'Editor não disponível',str(error));return False
        return True

    def work(self,operation,done=None,failed=None,transfer=False,quiet=False):
        if self.tasks:return
        task=Task(self.uri,operation,self.manager);self.tasks.add(task);self.pages.setEnabled(False)
        progress=None
        if transfer:
            progress=QProgressDialog('Copiando e conferindo arquivos da VM…','Cancelar',0,100,self);progress.setWindowTitle('Transferência de máquina virtual');progress.setWindowModality(Qt.WindowModality.WindowModal);progress.setMinimumDuration(0);progress.setAutoClose(False);progress.setAutoReset(False);progress.canceled.connect(task.requestInterruption);task.progress.connect(progress.setValue);progress.show()
        results=[]
        def success(result):
            try:
                if done:done(result)
                if not quiet:self.events.appendPlainText('Operação concluída no hospedeiro '+task.uri)
            except Exception as exception:error(str(exception))
        def error(message):
            friendly=message
            if 'Timeout' in message or 'timed out' in message:friendly='O serviço ou a autorização não respondeu a tempo. Clique em Conectar para tentar novamente e confirme a solicitação de senha.'
            elif 'no polkit agent' in message:friendly='Nenhum agente de autorização está disponível nesta sessão. Abra o gerenciador pelo menu da área de trabalho para administrar este computador.'
            elif 'authentication failed' in message:friendly='A autorização não foi concluída. Confira a senha da conta administrativa e tente conectar novamente.'
            self.status.setText(friendly);self.events.appendPlainText(message)
            if failed:failed(message)
            QMessageBox.warning(self,'Operação não concluída',friendly)
        def finished():
            self.manager=task.manager
            self.tasks.discard(task);self.pages.setEnabled(bool(self.data) and self.address.text().strip()==self.uri)
            if progress:progress.close();progress.deleteLater()
            if results:success(results[0])
        task.result.connect(results.append);task.failed.connect(error);task.finished.connect(finished);task.finished.connect(task.deleteLater);task.start()

    def refresh(self):
        if self.tasks or self.editors:return
        def query(m):
            host = m.connection.getInfo()
            return dict(domains=m.domains(), networks=m.networks(), pools=m.pools(),
                        capabilities=m.capabilities(), host_memory=host[1], host_cpus=host[2])
        self.work(query,self.loaded,lambda _:self.timer.stop(),quiet=True)

    def loaded(self,data):
        self.pages.setEnabled(self.address.text().strip()==self.uri)
        now=time.monotonic();metrics={}
        for row in data['domains']:
            previous=self.last_metrics.get(row['id']);row['cpu_usage']='—'
            if previous and row['active'] and now>previous[0] and row['cpu_ns']>=previous[1]:row['cpu_usage']=str(round(min(100,(row['cpu_ns']-previous[1])/(now-previous[0])/max(1,row['cpus'])/1e7),1))+' %'
            metrics[row['id']]=(now,row['cpu_ns'])
        self.last_metrics=metrics
        self.data=data;populate(self.vms,data['domains'],['name','state','memory','cpus','cpu_usage'],select_first=False);self.filter_vms();populate(self.networks,[dict(n,active_label='Sim' if n['active'] else 'Não',auto_label='Sim' if n['autostart'] else 'Não') for n in data['networks']],['name','mode','active_label','auto_label']);populate(self.pools,[dict(p,active_label='Sim' if p['active'] else 'Não',free=round(p['available']/1024**3,1)) for p in data['pools']],['name','kind','active_label','free','path'])
        self.status.setText(self.uri+' · '+str(len(data['domains']))+' máquinas · '+('Aceleração KVM' if data['capabilities']['kind']=='kvm' else 'Emulação por software; desempenho reduzido'))
        if self.uri!='test:///default' and self.preferences.get('last_uri')!=self.uri:
            self.preferences['last_uri']=self.uri;hosts=self.preferences.get('hosts',[]);hosts=hosts if isinstance(hosts,list) else []
            if self.uri not in hosts:hosts=(hosts+[self.uri])[-40:]
            self.preferences['hosts']=hosts
            try:preferences.save(self.preferences)
            except (OSError,ValueError) as error:self.events.appendPlainText('Não foi possível lembrar o hospedeiro: '+str(error))

    def connect_host(self):
        if self.tasks:return
        if self.editors:QMessageBox.information(self,'Configuração aberta','Feche as configurações das VMs antes de trocar de hospedeiro.');return
        try:uri=backend.checked_uri(self.address.text().strip())
        except ValueError as error:QMessageBox.warning(self,'Conexão inválida',str(error));return
        if self.manager:self.manager.close();self.manager=None
        self.uri=uri
        self.data={};self.last_metrics={};self.vm_search.clear();self.vms.setRowCount(0);self.networks.setRowCount(0);self.pools.setRowCount(0);self.pages.setEnabled(False)
        self.timer.start();self.refresh()

    def filter_vms(self,*_):
        query=self.vm_search.text().casefold().strip();visible=[]
        for index in range(self.vms.rowCount()):
            match=query in ' '.join(self.vms.item(index,column).text() for column in (0,1)).casefold();self.vms.setRowHidden(index,not match)
            if match:visible.append(index)
        if self.vms.currentRow() not in visible:
            self.vms.clearSelection();self.vms.setCurrentItem(None)
        self.vm_results.setText(f'Máquinas exibidas: {len(visible)}' if visible else
                                'Nenhuma máquina corresponde à busca.' if query else
                                'Nenhuma máquina virtual neste hospedeiro.')
        self.update_vm_actions()

    def update_vm_actions(self):
        vm = selected(self.vms)
        enabled = set()
        if vm:
            enabled.update(('settings','export_xml','migrate','migration_check','performance'))
            if vm['active']:
                enabled.update(('console','shutdown','reboot','save','poweroff','lab_access'))
                if vm['state'] == backend.STATES[3]:
                    enabled.add('resume')
                elif vm['state'] in (backend.STATES[1], backend.STATES[2]):
                    enabled.add('pause')
            else:
                enabled.update(('start','clone','replica','remove','export_vm'))
                if self.uri == 'qemu:///system':
                    enabled.add('delegate_media')
        for key,control in self.vm_controls.items():
            control.setEnabled(key in enabled)

    def performance(self):
        vm = selected(self.vms)
        if vm:
            Performance(self, vm).exec()

    def topology(self):
        def display(rows):
            dialog = Form('Topologia virtual', self)
            dialog.resize(1000, 480)
            results = table(['Máquina virtual', 'Interface', 'Modo', 'Rede virtual', 'Ponte', 'VLAN', 'Saída'])
            results.setAccessibleName('Caminho de rede das interfaces virtuais')
            populate(results, rows, ['vm', 'interface', 'kind', 'network', 'bridge', 'vlan', 'upstream'])
            if not rows:
                dialog.body.addWidget(QLabel('Nenhuma interface virtual encontrada neste hospedeiro.'))
            dialog.body.addWidget(results)
            close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close.rejected.connect(dialog.reject)
            dialog.body.addWidget(close)
            dialog.exec()
        self.work(observations.topology, display, quiet=True)

    def resource_budget(self):
        if not self.data:
            QMessageBox.information(self, 'Orçamento de recursos', 'Conecte a um hospedeiro para consultar a capacidade.')
            return
        groups = ('Laboratório', 'Trabalho', 'Produção')
        host_record = self.preferences.get('resource_budgets', {}).get(self.uri, {})
        limits, assignments = host_record.get('limits', {}), host_record.get('assignments', {})
        dialog = Form('Orçamento de recursos', self)
        dialog.resize(730, 540)
        dialog.form.addRow('Capacidade física', QLabel(
            f'{self.data["host_cpus"]} processadores · {self.data["host_memory"]} MiB'))
        controls = {}
        for group in groups:
            configured = limits.get(group, {})
            memory = spin(0, 16777216, configured.get('memory', 0), ' MiB')
            cpus = spin(0, 8192, configured.get('cpus', 0), ' vCPU')
            memory.setSpecialValueText('RAM sem limite')
            cpus.setSpecialValueText('CPU sem limite')
            memory.setAccessibleName(f'Limite de RAM · {group}')
            cpus.setAccessibleName(f'Limite de CPU · {group}')
            row = QHBoxLayout()
            row.addWidget(memory); row.addWidget(cpus)
            dialog.form.addRow(group, row)
            controls[group] = memory, cpus
        listing = table(['Máquina virtual', 'RAM configurada (MiB)', 'vCPU', 'Grupo'])
        listing.setAccessibleName('Distribuição de máquinas pelos grupos')
        domains = self.data['domains']
        populate(listing, domains, ['name', 'memory', 'cpus'], select_first=False)
        choices = {}
        for index, domain in enumerate(domains):
            choice = QComboBox()
            choice.setAccessibleName('Grupo · ' + domain['name'])
            choice.addItems(('Sem grupo', *groups))
            choice.setCurrentText(assignments.get(domain['id'], 'Sem grupo'))
            listing.setCellWidget(index, 3, choice)
            choices[domain['id']] = choice
        dialog.body.addWidget(listing, 1)
        result = QLabel()
        result.setWordWrap(True)
        dialog.body.addWidget(result)

        def update():
            totals = {name: dict(memory=0, cpus=0) for name in ('Sem grupo', *groups)}
            for domain in domains:
                row = totals[choices[domain['id']].currentText()]
                for metric in ('memory', 'cpus'):
                    row[metric] += domain[metric]
            notices = []
            for name, row in totals.items():
                memory, cpus = controls[name] if name in controls else (None, None)
                excess = ((memory and memory.value() and row['memory'] > memory.value())
                          or (cpus and cpus.value() and row['cpus'] > cpus.value()))
                notices.append(f'{name} · {row["memory"]} MiB · {row["cpus"]} vCPU'
                               + (' · limite excedido' if excess else ''))
            if any(sum(row[key] for row in totals.values()) > self.data['host_' + key]
                   for key in ('memory', 'cpus')):
                notices.append('A soma dos recursos configurados ultrapassa a capacidade do hospedeiro.')
            result.setText('\n'.join(notices))

        for memory, cpus in controls.values():
            memory.valueChanged.connect(update)
            cpus.valueChanged.connect(update)
        for choice in choices.values():
            choice.currentIndexChanged.connect(update)
        update()
        dialog.controls.button(QDialogButtonBox.StandardButton.Ok).setText('Salvar orçamento')
        dialog.finish()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        record = dict(limits={name: dict(memory=memory.value(), cpus=cpus.value())
                              for name, (memory, cpus) in controls.items()},
                      assignments={identifier: control.currentText() for identifier, control in choices.items()})
        updated = dict(self.preferences, resource_budgets={
            **self.preferences.get('resource_budgets', {}), self.uri: record})
        try:
            preferences.save(updated)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Orçamento não salvo', str(error))
        else:
            self.preferences = updated

    def action(self,action):
        row=selected(self.vms)
        if not row:return
        if action in ('poweroff','reboot','save') and not self.confirm({'poweroff':'Desligar à força? Dados não salvos no convidado podem ser perdidos.','reboot':'Reiniciar esta VM?','save':'Salvar o estado desta VM em disco e interromper sua execução?'}[action]):return
        self.work(lambda m:m.action(row['id'],action),lambda _:QTimer.singleShot(200,self.refresh))

    def create(self):
        from virtualization_catalog import catalog

        dialog=Form('Criar máquina virtual',self);name=QLineEdit();memory=spin(256,262144,2048,' MiB');cpus=spin(1,256,2);size=spin(4,2048,40,' GiB');pool=QComboBox();pool.addItems([p['name'] for p in self.data.get('pools',[]) if p['active']]);network=QComboBox();network.addItem('NAT do processo QEMU','')
        for n in self.data.get('networks',[]):network.addItem(n['name'],n['name'])
        iso=QLineEdit();iso.setPlaceholderText('Caminho no hospedeiro; pode ficar vazio');iso_row=QWidget();iso_layout=QHBoxLayout(iso_row);iso_layout.setContentsMargins(0,0,0,0);iso_layout.addWidget(iso,1)
        def choose_iso():
            path,_=QFileDialog.getOpenFileName(dialog,'Selecionar mídia de instalação','','Imagens ISO (*.iso);;Todos os arquivos (*)')
            if path:iso.setText(path)
        browse=button('Selecionar…','document-open',choose_iso);browse.setEnabled(self.uri in ('qemu:///system','qemu:///session'));browse.setToolTip('Seleção de arquivo deste computador. Para armazenamento remoto e ajustes de acesso, use o assistente completo.');iso_layout.addWidget(browse)
        uefi=QCheckBox('Usar UEFI');uefi.setChecked(True);secure=QCheckBox('Secure Boot');tpm=QCheckBox('TPM 2.0 virtual');windows=QCheckBox('Convidado Windows (relógio e dispositivos compatíveis)')
        def windows_defaults(checked):
            if checked:uefi.setChecked(True);secure.setChecked(True);tpm.setChecked(True);memory.setValue(max(4096,memory.value()));cpus.setValue(max(2,cpus.value()));size.setValue(max(64,size.value()))
        windows.toggled.connect(windows_defaults)
        for caption,widget in [('Nome:',name),('Memória:',memory),('Processadores:',cpus),('Disco dinâmico:',size),('Local do disco:',pool),('Rede:',network),('ISO de instalação:',iso_row),('',uefi),('',secure),('',tpm),('',windows)]:dialog.form.addRow(caption,widget)
        directory=QLineEdit(str(Path.home()/'Máquinas virtuais') if self.uri=='qemu:///session' else '/var/lib/libvirt/images/linuxbr')
        saved=preferences.defaults(self.preferences,self.uri);memory.setValue(saved.get('memory',memory.value()));cpus.setValue(saved.get('cpus',cpus.value()));size.setValue(saved.get('disk_gib',size.value()));directory.setText(saved.get('directory',directory.text()))
        if pool.findText(saved.get('pool',''))>=0:pool.setCurrentText(saved['pool'])
        if network.findData(saved.get('network',''))>=0:network.setCurrentIndex(network.findData(saved.get('network','')))
        if pool.count()==0:
            pool.addItem('Criar local padrão ao confirmar','new');dialog.form.addRow('Diretório do novo local:',directory)
        models, model_errors = catalog()
        model = QComboBox()
        model.addItem('Configuração personalizada', None)
        for profile in models:
            model.addItem(f"{profile['name']} · revisão {profile['revision']}", profile)
        model_status = QLabel()
        model_status.setTextFormat(Qt.TextFormat.PlainText)
        model_status.setWordWrap(True)
        warning = QLabel('\n'.join(model_errors))
        warning.setTextFormat(Qt.TextFormat.PlainText)
        warning.setWordWrap(True)
        warning.setVisible(bool(model_errors))
        dialog.form.insertRow(0, 'Modelo administrado:', model)
        dialog.form.insertRow(1, '', model_status)
        dialog.body.addWidget(warning)

        def apply_model():
            profile = model.currentData()
            for widget in (memory, cpus, size, network, windows, uefi, secure, tpm):
                widget.setEnabled(profile is None)
            model_status.clear()
            if profile is None:
                return
            windows.setChecked(profile['windows'])
            uefi.setChecked(profile['firmware'] != 'bios')
            secure.setChecked(profile['firmware'] == 'uefi-secure')
            tpm.setChecked(profile['tpm'])
            memory.setValue(profile['memory'])
            cpus.setValue(profile['cpus'])
            size.setValue(profile['disk_gib'])
            index = network.findData(profile['network'])
            network.setCurrentIndex(index)
            model_status.setText(f"{profile['id']} · revisão {profile['revision']}"
                                 + (' · rede indisponível neste hospedeiro' if index < 0 else ''))

        model.currentIndexChanged.connect(apply_model)
        label=QLabel('O assistente cria a definição e um novo disco. Nenhum disco físico será usado. A VM será criada desligada.');label.setWordWrap(True);dialog.body.addWidget(label);dialog.finish()
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        new_pool=pool.currentData()=='new';spec=dict(name=name.text().strip(),memory=memory.value(),cpus=cpus.value(),disk_gib=size.value(),pool='linuxbr' if new_pool else pool.currentText(),network=network.currentData(),iso=iso.text().strip(),uefi=uefi.isChecked(),secure_boot=secure.isChecked(),tpm=tpm.isChecked(),windows=windows.isChecked());location=directory.text().strip()
        profile = model.currentData()
        if profile:
            if network.currentIndex() < 0:
                QMessageBox.warning(self, 'Rede indisponível', 'Crie a rede indicada no modelo ou escolha outro modelo.')
                return
            spec['managed_template'] = (profile['id'], profile['revision'])
        def create(manager):
            if new_pool:manager.create_pool('linuxbr',location)
            return manager.create(spec)
        self.work(create,lambda _:QTimer.singleShot(200,self.refresh))

    def configure(self):
        if self.tasks:return
        saved=preferences.defaults(self.preferences,self.uri);dialog=Form('Preferências de máquinas virtuais',self);memory=spin(256,262144,saved.get('memory',2048),' MiB');cpus=spin(1,256,saved.get('cpus',2));size=spin(4,2048,saved.get('disk_gib',40),' GiB');directory=QLineEdit(saved.get('directory',str(Path.home()/'Máquinas virtuais') if self.uri=='qemu:///session' else '/var/lib/libvirt/images/linuxbr'));pool=QComboBox();pool.addItem('Primeiro local disponível','')
        for item in self.data.get('pools',[]):pool.addItem(item['name'],item['name'])
        pool.setCurrentIndex(max(0,pool.findData(saved.get('pool',''))));network=QComboBox();network.addItem('NAT do processo QEMU','')
        for item in self.data.get('networks',[]):network.addItem(item['name'],item['name'])
        network.setCurrentIndex(max(0,network.findData(saved.get('network',''))))
        for label,widget in [('Memória padrão:',memory),('Processadores:',cpus),('Disco dinâmico:',size),('Local preferido:',pool),('Rede preferida:',network),('Diretório para criar o local padrão:',directory)]:dialog.form.addRow(label,widget)
        note=QLabel('Preferências da sua conta para este hospedeiro. Elas não alteram VMs existentes nem criam diretórios até você confirmar uma nova VM.');note.setWordWrap(True);dialog.body.addWidget(note);dialog.finish()
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if not Path(directory.text()).is_absolute():QMessageBox.warning(self,'Diretório inválido','Informe um caminho absoluto no hospedeiro.');return
        values=self.preferences.get('defaults',{});values=values if isinstance(values,dict) else {};values[self.uri]=dict(memory=memory.value(),cpus=cpus.value(),disk_gib=size.value(),directory=directory.text(),pool=pool.currentData(),network=network.currentData());self.preferences['defaults']=values
        try:preferences.save(self.preferences)
        except (OSError,ValueError) as error:QMessageBox.warning(self,'Preferências não salvas',str(error))

    def edit(self):
        row=selected(self.vms)
        if not row:return
        def loaded(data):
            dialog=Editor(self,row,data);self.editors.append(dialog);dialog.finished.connect(lambda _:self.editors.remove(dialog));dialog.show()
        self.work(lambda m:dict(xml=m.xml(row['id']),interfaces=m.interfaces(row['id']),storage=m.storage(row['id']),snapshots=m.snapshots(row['id']),networks=m.networks(),pools=m.pools()),loaded)

    def console(self):
        row=selected(self.vms)
        if row:
            try:subprocess.Popen(['/usr/bin/virt-viewer','--connect',self.uri,row['id']],start_new_session=True)
            except OSError as error:QMessageBox.warning(self,'Console indisponível',str(error))

    def remove(self):
        row=selected(self.vms)
        if row and self.confirm('Remover somente a definição de '+row['name']+'? Discos e arquivos serão preservados.'):self.work(lambda m:m.undefine(row['id']),lambda _:QTimer.singleShot(200,self.refresh))

    def create_network(self):
        dialog=Form('Criar rede virtual',self);name=QLineEdit();mode=QComboBox()
        for label,key in [('NAT — acesso externo pelo hospedeiro','nat'),('Interna — VMs e hospedeiro','internal'),('Privada — somente VMs','private'),('Externa — ponte existente','bridge')]:mode.addItem(label,key)
        subnet=QLineEdit('192.168.150.0/24');bridge=QLineEdit();bridge.setPlaceholderText('Exemplo: br0; não altera a rede física automaticamente')
        for caption,widget in [('Nome:',name),('Tipo:',mode),('Sub-rede IPv4:',subnet),('Ponte do hospedeiro:',bridge)]:dialog.form.addRow(caption,widget)
        dialog.finish()
        if dialog.exec()==QDialog.DialogCode.Accepted:self.work(lambda m:m.define_network(dict(name=name.text().strip(),mode=mode.currentData(),subnet=subnet.text().strip(),bridge=bridge.text().strip())),lambda _:QTimer.singleShot(200,self.refresh))

    def edit_network(self):
        row=selected(self.networks)
        if not row:return
        dialog=Form('Configurar rede '+row['name'],self);mode=QComboBox()
        for label,key in [('NAT','nat'),('Interna — VMs e hospedeiro','internal'),('Privada — somente VMs','private'),('Ponte externa existente','bridge')]:mode.addItem(label,key)
        if mode.findData(row['mode'])<0:QMessageBox.information(self,'Rede personalizada','Esta rede usa um encaminhamento personalizado. Sua configuração será preservada.');return
        mode.setCurrentIndex(mode.findData(row['mode']));root=ET.fromstring(row['xml']);address=root.find('ip');b=root.find('bridge');subnet=QLineEdit()
        if address is not None:
            import ipaddress
            subnet.setText(str(ipaddress.ip_network(address.get('address')+'/'+(address.get('netmask') or address.get('prefix','24')),strict=False)))
        else:subnet.setText('192.168.150.0/24')
        bridge=QLineEdit(b.get('name','') if b is not None else '')
        for caption,widget in [('Tipo:',mode),('Sub-rede IPv4 e DHCP:',subnet),('Ponte externa:',bridge)]:dialog.form.addRow(caption,widget)
        label=QLabel('Desative a rede antes de editar. Alterar tipo ou sub-rede muda a conectividade. Reservas DHCP existentes são preservadas quando compatíveis.');label.setWordWrap(True);dialog.body.addWidget(label);dialog.finish()
        if dialog.exec()==QDialog.DialogCode.Accepted:self.work(lambda m:m.edit_network(row['id'],dict(mode=mode.currentData(),subnet=subnet.text().strip(),bridge=bridge.text().strip())),lambda _:QTimer.singleShot(200,self.refresh))

    def network_hosts(self):
        row = selected(self.networks)
        if not row:
            return
        dialog = Form('DNS e DHCP — ' + row['name'], self)
        root = ET.fromstring(row['xml'])
        records = [f"{entry.text}  {host.get('ip', '')}" for host in root.findall('dns/host') for entry in host.findall('hostname')]
        records.extend(f"{host.get('mac', '')}  {host.get('ip', '')}" for host in root.findall('ip/dhcp/host'))
        listing = QPlainTextEdit('\n'.join(records))
        listing.setReadOnly(True)
        dialog.body.addWidget(listing)
        name, address, mac = QLineEdit(), QLineEdit(), QLineEdit()
        for label, field in [('Nome do computador', name), ('Endereço IPv4', address), ('MAC para reserva DHCP (opcional)', mac)]:
            dialog.form.addRow(label, field)
        note = QLabel('Desative a rede para adicionar um nome e, se informar o MAC, reservar um endereço IP.')
        note.setWordWrap(True)
        dialog.body.addWidget(note)
        dialog.finish()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.work(lambda manager: manager.add_network_host(row['id'], name.text().strip(), address.text().strip(), mac.text().strip()),
                      lambda _: QTimer.singleShot(200, self.refresh))

    def network_action(self,action):
        row=selected(self.networks)
        if row and (action not in ('stop','remove') or self.confirm('Alterar a rede '+row['name']+'? Desativar uma rede interrompe a conectividade das VMs conectadas.')):self.work(lambda m:m.network_action(row['id'],action),lambda _:QTimer.singleShot(200,self.refresh))

    def create_pool(self):
        dialog=Form('Local de armazenamento',self);name=QLineEdit();path=QLineEdit(str(Path.home()/'Máquinas virtuais') if self.uri=='qemu:///session' else '/var/lib/libvirt/images/linuxbr');dialog.form.addRow('Nome:',name);dialog.form.addRow('Diretório no hospedeiro:',path);dialog.finish()
        if dialog.exec()==QDialog.DialogCode.Accepted:self.work(lambda m:m.create_pool(name.text().strip(),path.text().strip()),lambda _:QTimer.singleShot(200,self.refresh))

    def pool_action(self,action):
        row=selected(self.pools)
        if row and (action not in ('stop','remove') or self.confirm('Alterar o local '+row['name']+'? Remover a definição mantém todos os arquivos.')):self.work(lambda m:m.pool_action(row['name'],action),lambda _:QTimer.singleShot(200,self.refresh))

    def volumes(self):
        row=selected(self.pools)
        if row:self.work(lambda m:m.volumes(row['name']),lambda rows:QMessageBox.information(self,'Volumes de '+row['name'],'\n'.join(v['name']+' · '+str(round(v['capacity']/1024**3,1))+' GiB · '+v['path'] for v in rows) or 'Nenhum volume neste local.'))

    def create_volume(self):
        row=selected(self.pools)
        if not row:return
        dialog=Form('Criar disco',self);name=QLineEdit();size=spin(1,2048,40,' GiB');dialog.form.addRow('Nome:',name);dialog.form.addRow('Capacidade dinâmica:',size);dialog.finish()
        if dialog.exec()==QDialog.DialogCode.Accepted:self.work(lambda m:m.create_volume(row['name'],name.text().strip(),size.value()),lambda _:QTimer.singleShot(200,self.refresh))

    def resize_volume(self):
        row=selected(self.pools)
        if not row:return
        def choose(volumes):
            name,ok=QInputDialog.getItem(self,'Expandir disco','Volume:',[v['name'] for v in volumes],0,False)
            if not ok:return
            size,ok=QInputDialog.getInt(self,'Expandir disco','Novo tamanho em GiB:',40,1,2048)
            if ok and self.confirm('Expandir '+name+'? A partição e o sistema de arquivos do convidado precisarão ser ampliados separadamente.'):self.work(lambda m:m.resize_volume(row['name'],name,size))
        self.work(lambda m:m.volumes(row['name']),choose)

    def export_definition(self):
        row=selected(self.vms)
        if not row:return
        path,_=QFileDialog.getSaveFileName(self,'Exportar somente a definição',row['name']+'.xml','Definição libvirt (*.xml)')
        if path:self.work(lambda m:m.xml(row['id']),lambda text:Path(path).write_text(text))

    def export_bundle(self):
        row=selected(self.vms)
        if not row:return
        parent=QFileDialog.getExistingDirectory(self,'Escolha onde guardar a cópia completa')
        if not parent:return
        name,ok=QInputDialog.getText(self,'Diretório da cópia','Nome do novo diretório:',text=row['name']+'-backup')
        if not ok:return
        try:backend.checked_name(name)
        except ValueError as error:QMessageBox.warning(self,'Nome inválido',str(error));return
        if not self.confirm('Exportar a VM desligada com discos, firmware e TPM? A cópia contém dados privados e deve ser guardada em local protegido.'):return
        self.work(lambda m:m.export_bundle(row['id'],str(Path(parent)/name)),lambda result:QMessageBox.information(self,'Cópia concluída',result['path']),transfer=True)

    def import_bundle(self):
        path=QFileDialog.getExistingDirectory(self,'Selecione a pasta que contém manifest.json e os discos')
        if not path:return
        dialog=Form('Importar máquina virtual completa',self);name=QLineEdit();pool=QComboBox();pool.addItems([p['name'] for p in self.data.get('pools',[]) if p['active']]);network=QComboBox();network.addItem('NAT do processo QEMU','')
        for item in self.data.get('networks',[]):network.addItem(item['name'],item['name'])
        identity=QCheckBox('Criar nova identidade e endereços MAC');identity.setChecked(True)
        for label,widget in [('Nome no destino:',name),('Local dos discos:',pool),('Rede no destino:',network),('',identity)]:dialog.form.addRow(label,widget)
        note=QLabel('A integridade será conferida antes da importação. VMs existentes são preservadas. A cópia pode conter credenciais do convidado; importe somente cópias de confiança.');note.setWordWrap(True);dialog.body.addWidget(note);dialog.finish()
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        specification=(path,pool.currentText(),name.text().strip(),identity.isChecked(),network.currentData())
        self.work(lambda m:m.import_bundle(*specification),lambda _:QTimer.singleShot(200,self.refresh),transfer=True)

    def complete_disk_copy(self, path):
        QMessageBox.information(self, 'Cópia concluída', path)

    def import_hyperv(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Selecionar disco Hyper-V independente', '',
                                              'Discos Hyper-V (*.vhd *.vhdx)')
        if not path:
            return
        def review(spec):
            dialog = Form('Revisar disco Hyper-V', self)
            dialog.form.addRow('Disco de origem', QLabel(path))
            dialog.form.addRow('Capacidade virtual', QLabel(f'{spec["capacity"] / disk_tools.GIB:.2f} GiB'))
            dialog.form.addRow('Tabela de partições', QLabel(spec['scheme']))
            dialog.form.addRow('Firmware sugerido', QLabel(spec['firmware']))
            note = QLabel('Para Windows, comece com SATA ou use o controlador do ambiente de origem '
                          'se o convidado já tiver o driver correspondente. Confirme o modo de boot antes de iniciar.')
            note.setWordWrap(True)
            dialog.body.addWidget(note)
            dialog.controls.button(QDialogButtonBox.StandardButton.Ok).setText('Salvar cópia…')
            dialog.finish()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            save, _ = QFileDialog.getSaveFileName(self, 'Salvar nova imagem QCOW2',
                                                 str(Path(path).with_suffix('.qcow2')), 'QCOW2 (*.qcow2)')
            if save:
                self.work(lambda m:disk_tools.convert(path, save, spec['capacity'], spec['format'], m.cancelled),
                          self.complete_disk_copy, transfer=True)
        self.work(lambda _:disk_tools.hyperv_preview(path), review, quiet=True)

    def inspect_chain(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Selecionar disco de uma VM desligada', '', 'QCOW2 (*.qcow2)')
        if not path:
            return
        def review(rows):
            dialog = Form('Cadeia de checkpoints', self)
            dialog.resize(960, 455)
            view = table(['Imagem', 'Formato', 'Capacidade (GiB)', 'Imagem de base'])
            populate(view, [dict(row, gib=round(row['capacity'] / disk_tools.GIB, 2)) for row in rows],
                     ['path', 'format', 'gib', 'parent'])
            dialog.body.addWidget(view)
            note = QLabel('Uma cópia independente consolida o estado atual num novo disco. '
                          'Confira a ordem dos arquivos acima e a recuperação antes de conectá-lo a uma VM.')
            note.setWordWrap(True)
            dialog.body.addWidget(note)
            save = dialog.controls.button(QDialogButtonBox.StandardButton.Ok)
            save.setText('Criar cópia independente…')
            save.setEnabled(len(rows) > 1)
            dialog.finish()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            destination, _ = QFileDialog.getSaveFileName(self, 'Salvar disco recuperado', '', 'QCOW2 (*.qcow2)')
            def consolidate(manager):
                if disk_tools.chain(path) != rows:
                    raise ValueError('A cadeia mudou. Inspecione os discos novamente.')
                return disk_tools.convert(path, destination, rows[0]['capacity'], 'qcow2', manager.cancelled)
            if destination:
                self.work(consolidate, self.complete_disk_copy, transfer=True)
        self.work(lambda _:disk_tools.chain(path), review, quiet=True)

    def recover_file(self):
        path, selected_filter = QFileDialog.getOpenFileName(self, 'Selecionar disco de uma VM desligada', '',
                                                'QCOW2 (*.qcow2);;Disco bruto (*.raw *.img)')
        if not path:
            return
        source, ok = QInputDialog.getText(self, 'Caminho no convidado',
                                         'Informe o caminho absoluto do arquivo, como /home/usuario/arquivo.txt.')
        if not ok:
            return
        destination, _ = QFileDialog.getSaveFileName(self, 'Salvar arquivo recuperado', Path(source).name)
        if destination:
            format_name = 'qcow2' if selected_filter.startswith('QCOW2') else 'raw'
            self.work(lambda m:disk_tools.restore_file(path, format_name, source, destination, m.cancelled),
                      self.complete_disk_copy, transfer=True)

    def import_definition(self):
        path,_=QFileDialog.getOpenFileName(self,'Importar definição existente','','Definição libvirt (*.xml)')
        if not path:return
        text=Path(path).read_text()
        if len(text)>1048576 or '<!DOCTYPE' in text.upper():QMessageBox.warning(self,'Definição inválida','Arquivo inválido ou muito grande.');return
        try:root=ET.fromstring(text)
        except ET.ParseError as error:QMessageBox.warning(self,'XML inválido',str(error));return
        if root.tag!='domain':return
        dialog=Form('Revisar definição importada',self);view=QPlainTextEdit(text);view.setReadOnly(True);dialog.body.addWidget(QLabel('Os discos não serão copiados. A definição pode referenciar dispositivos, caminhos e recursos privilegiados do hospedeiro. Confira o XML completo antes de autorizar.'));dialog.body.addWidget(view);dialog.finish()
        if dialog.exec()==QDialog.DialogCode.Accepted:self.work(lambda m:m.connection.defineXML(text).UUIDString(),lambda _:QTimer.singleShot(200,self.refresh))

    def clone(self):
        row=selected(self.vms)
        if not row:return
        if row['active']:QMessageBox.warning(self,'Desligue a VM','A clonagem exige a VM desligada.');return
        name,ok=QInputDialog.getText(self,'Clonar VM','Nome da nova VM (novos discos serão criados):')
        if not ok:return
        try:backend.checked_name(name)
        except ValueError as error:QMessageBox.warning(self,'Nome inválido',str(error));return
        pool,ok=QInputDialog.getItem(self,'Discos da cópia','Local de armazenamento:',[p['name'] for p in self.data.get('pools',[]) if p['active']],0,False)
        if not ok:return
        if not self.confirm('Clonar discos, firmware e TPM? A nova VM terá outra identidade no hospedeiro, mas manterá arquivos, contas e configurações do convidado. A cópia temporária exige espaço neste computador.'):return
        self.work(lambda m:m.clone(row['id'],pool,name),lambda _:QTimer.singleShot(200,self.refresh),transfer=True)

    def lab_access(self):
        from datetime import date, timedelta
        from virtualization_guest_access import create

        row = selected(self.vms)
        if not row or not row['active']:
            return
        expires, ok = QInputDialog.getText(
            self, 'Criar acesso temporário · ' + row['name'],
            'Data de expiração (AAAA-MM-DD, UTC). O convidado Linux receberá uma conta comum.',
            text=(date.today() + timedelta(days=1)).isoformat())
        if not ok:
            return

        def show(reply):
            dialog = Form('Credencial temporária · ' + row['name'], self)
            for label, key in (('Usuário', 'username'), ('Senha', 'password'), ('Expira em (UTC)', 'expires')):
                value = QLineEdit(reply[key])
                value.setReadOnly(True)
                dialog.form.addRow(label, value)
            text = QLabel('Entregue a credencial ao participante. A conta expira na data definida.')
            text.setWordWrap(True)
            dialog.body.addWidget(text)
            actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            actions.rejected.connect(dialog.reject)
            dialog.body.addWidget(actions)
            dialog.exec()

        self.work(lambda manager: create(manager, row['id'], expires.strip()), show, quiet=True)

    def delegate_media(self):
        row = selected(self.vms)
        if not row or row['active'] or self.uri != 'qemu:///system':
            return
        dialog = Form('Delegar mídia ISO · ' + row['name'], self)
        operator, image, sha256 = (QLineEdit() for _ in range(3))
        hours = spin(1, 168, 12, ' h')
        image.setPlaceholderText('Somente o nome do arquivo, com extensão .iso')
        sha256.setMaxLength(64)
        for label, widget in (('Conta do operador', operator), ('ISO aprovada', image),
                              ('SHA-256', sha256), ('Validade', hours)):
            dialog.form.addRow(label, widget)
        note = QLabel('O administrador guarda as ISOs aprovadas em /var/lib/linuxbr/vm-approved-media. '
                      'A VM deve ter um leitor de mídia de arquivo. O código vale para esta conta, '
                      'esta VM e esta ISO, e pode ser usado uma vez.')
        note.setWordWrap(True)
        dialog.body.addWidget(note)
        dialog.finish()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = [operator.text().strip(), row['id'], image.text().strip(), sha256.text().strip(), str(hours.value())]

        def issue(_):
            result = subprocess.run(['/usr/bin/pkexec', '/usr/bin/linuxbr-vm-media-admin', 'issue', *values],
                                    timeout=600, capture_output=True, text=True, check=False)
            if result.returncode:
                raise ValueError(result.stderr.strip()[:600] or 'A autorização administrativa não foi concluída.')
            return json.loads(result.stdout)

        def present(result):
            answer = Form('Autorização de mídia emitida', self)
            code = QLineEdit(result['code'])
            code.setReadOnly(True)
            answer.form.addRow('Código', code)
            answer.form.addRow('Expira em (UTC)', QLabel(result['expires']))
            answer.body.addWidget(QLabel('Entregue o código ao operador para usar em Anexar mídia autorizada.'))
            close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close.rejected.connect(answer.reject)
            answer.body.addWidget(close)
            answer.exec()

        self.work(issue, present, quiet=True)

    def migration_review(self, row, destination, mode, continuation=None, pool=None, network=None, name=None):
        from virtualization_migration_check import check

        status = {'ok': 'Conferido', 'review': 'Requer revisão', 'blocked': 'Impede migração'}

        def present(results):
            dialog = Form('Compatibilidade de migração · ' + row['name'], self)
            dialog.resize(780, 480)
            grid = table(['Área', 'Resultado', 'Observação'])
            grid.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            populate(grid, [{**item, 'result': status[item['status']]} for item in results],
                     ['area', 'result', 'detail'], select_first=False)
            grid.resizeRowsToContents()
            dialog.body.addWidget(grid)
            blocked = any(item['status'] == 'blocked' for item in results)
            label = QLabel('Revise os avisos antes de confirmar. O resultado reflete as condições atuais dos dois servidores.')
            label.setWordWrap(True)
            dialog.body.addWidget(label)
            options = QDialogButtonBox.StandardButton.Close
            if continuation and not blocked:
                options |= QDialogButtonBox.StandardButton.Ok
            actions = QDialogButtonBox(options)
            actions.accepted.connect(dialog.accept)
            actions.rejected.connect(dialog.reject)
            if actions.button(QDialogButtonBox.StandardButton.Ok):
                actions.button(QDialogButtonBox.StandardButton.Ok).setText('Migrar…')
            dialog.body.addWidget(actions)
            if dialog.exec() == QDialog.DialogCode.Accepted and continuation:
                continuation()

        self.work(lambda m: check(m, row['id'], destination, mode, pool, network, name), present, quiet=True)

    def migration_check(self):
        row = selected(self.vms)
        if row:
            destination, ok = QInputDialog.getText(self, 'Checar destino da migração', 'URI libvirt do destino')
            if ok:
                self.migration_review(row, destination.strip(), 'shared')

    def migrate(self):
        row=selected(self.vms)
        if not row:return
        copy_disks = False
        if not row['active']:
            options = ['Copiar os discos para o destino', 'Usar armazenamento compartilhado']
            operation, accepted = QInputDialog.getItem(self, 'Migrar VM desligada', 'Tipo de armazenamento',
                                                      options, editable=False)
            if not accepted:
                return
            if operation == options[0]:
                self.offline_transfer(row, replica=False)
                return
        else:
            modes = ['Armazenamento compartilhado', 'Copiar discos ao vivo com TLS']
            selected_mode, accepted = QInputDialog.getItem(self, 'Migrar VM em execução', 'Tipo de armazenamento',
                                                          modes, editable=False)
            if not accepted:
                return
            copy_disks = selected_mode == modes[1]
        context = ('Prepare TLS de migração nos dois hospedeiros e os caminhos de disco no destino. '
                   'Confira também a compatibilidade de CPU e rede.' if copy_disks else
                   'Confira o armazenamento compartilhado e a compatibilidade de CPU e rede.')
        destination,ok=QInputDialog.getText(self,'Migrar VM',context + '\nURI libvirt do destino')
        if ok:
            destination = destination.strip()

            def commit():
                if self.confirm('Migrar '+row['name']+' para '+destination+'?'):
                    self.work(lambda m:m.migrate(row['id'],destination,row['active'],copy_disks),
                              lambda _:QTimer.singleShot(200,self.refresh))

            self.migration_review(row, destination, 'live-copy' if copy_disks else 'shared', commit)

    def replicate_offline(self):
        row = selected(self.vms)
        if not row:
            return
        if row['active']:
            QMessageBox.information(self, 'Réplica offline', 'Desligue a VM de origem para copiar seus discos.')
            return
        self.offline_transfer(row, replica=True)

    def offline_transfer(self, row, replica):
        title = 'Réplica offline' if replica else 'Migrar VM com discos'
        hosts = [self.host_profile.itemData(index) for index in range(self.host_profile.count())]
        hosts = [host for host in hosts if host and host.startswith('qemu+ssh://') and host != self.uri]
        if not hosts:
            QMessageBox.information(self, title, 'Conecte-se ao hospedeiro de destino por SSH para cadastrá-lo.')
            return
        dialog = Form(title + ' — ' + row['name'], self)
        destination = QComboBox()
        destination.addItems(hosts)
        pool = QLineEdit()
        name = QLineEdit(row['name'] + ('-replica' if replica else ''))
        network = QLineEdit()
        for label, widget in [('Hospedeiro', destination), ('Local dos discos no destino', pool),
                              ('Nome no destino', name),
                              ('Rede isolada ativa no destino' if replica else 'Rede ativa no destino (VM com adaptadores)', network)]:
            dialog.form.addRow(label, widget)
        description = 'A transferência usa espaço temporário neste computador. A VM fica desligada no destino.'
        schedule = QCheckBox('Criar novas gerações em horários programados') if replica else None
        calendar = QLineEdit('daily') if replica else None
        if replica:
            dialog.form.addRow(schedule)
            dialog.form.addRow('Agenda systemd', calendar)
            calendar.setEnabled(False)
            schedule.toggled.connect(calendar.setEnabled)
            description += (' O agendamento usa as permissões da sua conta, exige SSH por chave sem '
                            'interação e só copia a VM se ela estiver desligada. '
                            'Cada execução bem-sucedida guarda uma geração separada e ocupa espaço adicional.')
        if not replica:
            description += (' A definição da origem é removida após a cópia. Os discos originais ficam '
                            'guardados. Mídias ISO precisam ser reconectadas no destino.')
        note = QLabel(description)
        note.setWordWrap(True)
        dialog.body.addWidget(note)
        dialog.finish()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = (destination.currentText(), pool.text().strip(), name.text().strip(), network.text().strip())
        if replica:
            if schedule.isChecked():
                from virtualization_replica_job import schedule as schedule_replica

                expression = calendar.text().strip()
                self.work(lambda manager: schedule_replica(manager.uri, row['id'], *values, expression),
                          lambda _: QMessageBox.information(self, title,
                              'Agendamento ativado. Consulte a tarefa em Agendador de Tarefas → Minha conta.'))
                return
            self.work(lambda manager: manager.replicate_offline(row['id'], *values),
                      lambda result: self.replica_created(values[0], result), transfer=True)
            return
        def completed(result):
            if result['source_removed']:
                QMessageBox.information(self, title, 'VM transferida e desligada no destino. Os discos originais foram preservados.')
            else:
                self.events.appendPlainText(result['source_error'])
                QMessageBox.warning(self, title, 'A cópia está desligada no destino. A remoção da definição de origem não foi confirmada. Confira a origem antes de ligar a cópia.')
            QTimer.singleShot(200, self.refresh)

        def commit():
            if self.confirm('Mover a VM para o hospedeiro selecionado? Mantenha a VM de origem desligada durante a transferência.'):
                self.work(lambda manager: manager.move_offline(row['id'], *values), completed, transfer=True)

        self.migration_review(row, values[0], 'offline-copy', commit, pool=values[1], network=values[3],
                              name=values[2])

    def replica_created(self, destination, result):
        if not self.confirm('Réplica criada e desligada no destino. Deseja iniciar um teste de ativação na rede isolada agora?'):
            return

        def activate(_):
            target = backend.Manager(destination)
            try:
                target.start_isolated_replica(result['id'])
            finally:
                target.close()

        def started(_):
            QMessageBox.information(self, 'Teste de ativação',
                'Réplica iniciada no destino. Conecte-se ao hospedeiro para abrir o console, testar o convidado e desligá-lo.')

        self.work(activate, started)

    def closeEvent(self,event):
        if self.tasks:
            event.ignore();QMessageBox.information(self,'Operação em andamento','Aguarde a conclusão da operação antes de fechar.');return
        self.timer.stop()
        if self.manager:self.manager.close();self.manager=None
        super().closeEvent(event)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--connect');args=parser.parse_args()
    if Path('/usr/bin/ksshaskpass').is_file():os.environ.setdefault('SSH_ASKPASS','/usr/bin/ksshaskpass');os.environ.setdefault('SSH_ASKPASS_REQUIRE','prefer')
    app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-virtual-machines');window=Window(args.connect);window.show();sys.exit(app.exec())
