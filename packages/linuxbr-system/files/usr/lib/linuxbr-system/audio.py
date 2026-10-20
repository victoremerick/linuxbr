"""PipeWire/PulseAudio settings for defaults, active streams and device profiles."""
import json
import subprocess
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,
    QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QSlider,QMessageBox)


def pactl(*args):
    return subprocess.check_output(['pactl',*args],text=True,timeout=8)


def inspect():
    outputs={name:json.loads(pactl('-f','json','list',name)) for name in
             ('sinks','sources','sink-inputs','source-outputs','cards')}
    outputs['default_sink']=pactl('get-default-sink').strip()
    outputs['default_source']=pactl('get-default-source').strip()
    return outputs


def percent(volume):
    levels=[v.get('value',0) for v in (volume or {}).values() if isinstance(v,dict)]
    return max(0,min(150,round(max(levels,default=0)*100/65536)))


class Audio(QWidget):
    def __init__(self):
        super().__init__()
        self.process=None;self.data={}
        body=QVBoxLayout(self);body.setContentsMargins(32,28,32,28);body.setSpacing(14)
        heading=QLabel('Áudio');heading.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(heading)
        tabs=QTabWidget();body.addWidget(tabs,1)
        devices=QWidget(); dev=QVBoxLayout(devices)
        for title,name,command in [('Alto-falante principal','sinks','set-default-sink'),('Microfone principal','sources','set-default-source')]:
            row=QHBoxLayout();row.addWidget(QLabel(title));selector=QComboBox();selector.setObjectName(name);row.addWidget(selector,1)
            button=QPushButton('Definir como padrão');button.clicked.connect(lambda checked=False,s=selector,c=command:self.default(s,c));row.addWidget(button)
            dev.addLayout(row)
            if name=='sinks':self.sinks=selector
            else:self.sources=selector
        dev.addWidget(QLabel('Perfil de áudio e qualidade disponível pelo dispositivo:'))
        profile_row=QHBoxLayout();self.cards=QComboBox();self.cards.currentIndexChanged.connect(self.profiles)
        self.profile=QComboBox();profile_row.addWidget(self.cards);profile_row.addWidget(self.profile,1)
        select=QPushButton('Aplicar perfil');select.clicked.connect(self.set_profile);profile_row.addWidget(select);dev.addLayout(profile_row)
        self.format=QLabel();self.format.setWordWrap(True);dev.addWidget(self.format);dev.addStretch()
        tabs.addTab(devices,'Dispositivos')
        mixer=QWidget();mix=QVBoxLayout(mixer)
        info=QLabel('Volume e roteamento dos aplicativos em uso. O WirePlumber pode restaurar a escolha de dispositivo quando o aplicativo abrir novamente.')
        info.setWordWrap(True);mix.addWidget(info)
        self.streams=QTableWidget(0,4);self.streams.setHorizontalHeaderLabels(['Aplicativo','Tipo','Volume','Dispositivo'])
        self.streams.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.streams.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);mix.addWidget(self.streams)
        tabs.addTab(mixer,'Mixer por aplicativo')
        refresh=QPushButton('Atualizar dispositivos e aplicativos');refresh.clicked.connect(self.refresh);body.addWidget(refresh)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status)
        self.refresh()

    def refresh(self):
        try:self.data=inspect()
        except (OSError,ValueError,subprocess.SubprocessError) as error:
            self.status.setText('Serviço de áudio indisponível: '+str(error));return
        self.sinks.clear();self.sources.clear();self.cards.blockSignals(True);self.cards.clear()
        for key,selector,default in [('sinks',self.sinks,self.data['default_sink']),('sources',self.sources,self.data['default_source'])]:
            for item in self.data[key]:
                selector.addItem(item.get('description') or item.get('name'),item['name'])
                if item['name']==default:selector.setCurrentIndex(selector.count()-1)
        for card in self.data['cards']:self.cards.addItem(card.get('properties',{}).get('device.description',card['name']),card['name'])
        self.cards.blockSignals(False);self.profiles()
        self.streams.setRowCount(0)
        for direction,key,devices,targetkey,move,vol_command in [
            ('Reprodução','sink-inputs',self.data['sinks'],'sink','move-sink-input','set-sink-input-volume'),
            ('Microfone','source-outputs',self.data['sources'],'source','move-source-output',None)]:
            for item in self.data[key]:
                index=self.streams.rowCount();self.streams.insertRow(index)
                props=item.get('properties',{})
                label=props.get('application.name') or props.get('media.name') or f'Fluxo {item["index"]}'
                self.streams.setItem(index,0,QTableWidgetItem(label));self.streams.setItem(index,1,QTableWidgetItem(direction))
                if vol_command:
                    slider=QSlider(Qt.Orientation.Horizontal);slider.setRange(0,100);slider.setValue(min(100,percent(item.get('volume'))))
                    slider.sliderReleased.connect(lambda s=slider,n=item['index'],c=vol_command:self.change(c,str(n),str(s.value())+'%'))
                    self.streams.setCellWidget(index,2,slider)
                else:self.streams.setItem(index,2,QTableWidgetItem('—'))
                selector=QComboBox()
                for device in devices:
                    selector.addItem(device.get('description') or device['name'],device['name'])
                    if device['index']==item.get(targetkey):selector.setCurrentIndex(selector.count()-1)
                selector.currentIndexChanged.connect(lambda _,s=selector,n=item['index'],c=move:self.change(c,str(n),s.currentData()) if s.currentData() else None)
                self.streams.setCellWidget(index,3,selector)
        self.format.setText('Saída padrão: '+(self.data['default_sink'] or 'nenhuma')+' · Entrada padrão: '+(self.data['default_source'] or 'nenhuma'))
        self.status.setText('Áudio atualizado.')

    def profiles(self):
        self.profile.clear();name=self.cards.currentData()
        card=next((c for c in self.data.get('cards',[]) if c['name']==name),None)
        if not card:return
        available=card.get('profiles',{})
        entries=available.items() if isinstance(available,dict) else ((entry['name'],entry) for entry in available)
        for key,profile in entries:
            if profile.get('available')=='no':continue
            self.profile.addItem(profile.get('description') or key,key)
            active=card.get('active_profile',{})
            if key==(active.get('name') if isinstance(active,dict) else active):self.profile.setCurrentIndex(self.profile.count()-1)

    def set_profile(self):
        if not self.cards.currentData() or not self.profile.currentData():return
        if QMessageBox.question(self,'Alterar perfil de áudio','Alterar o perfil pode desconectar temporariamente saídas e entradas de áudio. Continuar?')!=QMessageBox.StandardButton.Yes:return
        self.change('set-card-profile',self.cards.currentData(),self.profile.currentData())

    def default(self,selector,command):
        if selector.currentData():self.change(command,selector.currentData())

    def change(self,*args):
        if self.process is not None or any(arg is None for arg in args):return
        process=self.process=QProcess(self);process.setProgram('/usr/bin/pactl');process.setArguments(list(args))
        process.finished.connect(lambda code,status:self.finished(process,code))
        process.errorOccurred.connect(lambda error:self.finished(process,1) if error==QProcess.ProcessError.FailedToStart else None)
        self.status.setText('Aplicando áudio…');process.start()

    def finished(self,process,code):
        if self.process is not process:return
        self.process=None;message=bytes(process.readAllStandardError()).decode(errors='replace').strip()
        process.deleteLater();self.refresh()
        if code:self.status.setText('Não foi possível alterar o áudio: '+(message or 'Fluxo ou dispositivo indisponível.'))
