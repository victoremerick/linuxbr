"""Display settings embedded in the Linux BR System Center."""
import subprocess
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QHBoxLayout,QLabel,QComboBox,
    QCheckBox,QSpinBox,QDoubleSpinBox,QPushButton,QMessageBox,QGroupBox)
from display_backend import outputs,settings,apply


class Displays(QWidget):
    def __init__(self):
        super().__init__()
        self.detected=[]
        body=QVBoxLayout(self);body.setContentsMargins(32,28,32,28);body.setSpacing(14)
        title=QLabel('Telas');title.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(title)
        note=QLabel('Configure resolução, escala, orientação e posição. Se a imagem não aparecer após uma mudança, a configuração anterior será restaurada em 15 segundos.')
        note.setWordWrap(True);body.addWidget(note)
        row=QHBoxLayout();self.output=QComboBox();self.output.currentIndexChanged.connect(self.load)
        row.addWidget(self.output,1);refresh=QPushButton('Detectar telas');refresh.clicked.connect(self.refresh);row.addWidget(refresh);body.addLayout(row)
        form=QFormLayout()
        self.enabled=QCheckBox('Usar esta tela');form.addRow('',self.enabled)
        self.mode=QComboBox();form.addRow('Resolução e frequência',self.mode)
        self.scale=QDoubleSpinBox();self.scale.setRange(0.5,4);self.scale.setSingleStep(0.25);self.scale.setSuffix(' ×');form.addRow('Escala',self.scale)
        self.rotation=QComboBox()
        for label,value in [('Horizontal','none'),('Vertical à esquerda','left'),('Invertida','inverted'),('Vertical à direita','right')]:self.rotation.addItem(label,value)
        form.addRow('Orientação',self.rotation)
        self.x=QSpinBox();self.y=QSpinBox()
        for control in (self.x,self.y):control.setRange(-10000,10000)
        position=QHBoxLayout();position.addWidget(QLabel('X'));position.addWidget(self.x);position.addWidget(QLabel('Y'));position.addWidget(self.y)
        form.addRow('Posição',position);body.addLayout(form)
        self.enabled.toggled.connect(self.toggle_fields)
        save=QPushButton('Aplicar alterações');save.setProperty('primary',True);save.clicked.connect(self.save);body.addWidget(save)
        night=QGroupBox('Luz noturna');night_form=QFormLayout(night)
        self.night_enabled=QCheckBox('Reduzir luz azul à noite');night_form.addRow('',self.night_enabled)
        self.night_temp=QSpinBox();self.night_temp.setRange(1000,6500);self.night_temp.setSingleStep(100);self.night_temp.setSuffix(' K')
        night_form.addRow('Temperatura noturna',self.night_temp)
        night_save=QPushButton('Aplicar luz noturna');night_save.clicked.connect(self.save_night)
        night_form.addRow('',night_save);body.addWidget(night)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status);body.addStretch()
        self.refresh();self.load_night()

    def load_night(self):
        try:
            def read(key):
                return subprocess.check_output(['kreadconfig6','--file','kwinrc','--group','NightColor','--key',key],text=True,timeout=3).strip()
            self.night_enabled.setChecked(read('Active').lower()=='true')
            self.night_temp.setValue(int(read('NightTemperature') or 4500))
        except (OSError,ValueError,subprocess.SubprocessError):self.night_temp.setValue(4500)

    def save_night(self):
        try:
            for key,value in [('Active','true' if self.night_enabled.isChecked() else 'false'),
                              ('NightTemperature',str(self.night_temp.value()))]:
                subprocess.run(['kwriteconfig6','--file','kwinrc','--group','NightColor','--key',key,value],check=True,timeout=3)
            subprocess.run(['dbus-send','--session','--type=signal','/KWin','org.kde.KWin.reloadConfig'],check=False,timeout=3)
            self.status.setText('Luz noturna atualizada.')
        except (OSError,subprocess.SubprocessError) as error:self.status.setText('Não foi possível alterar a luz noturna: '+str(error))

    def refresh(self):
        try:self.detected=outputs()
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
            self.status.setText('Não foi possível consultar as telas: '+str(error));return
        old=self.output.currentData();self.output.blockSignals(True);self.output.clear()
        for screen in self.detected:
            self.output.addItem(screen.get('name') or f'Tela {screen["id"]}',screen['id'])
        index=self.output.findData(old)
        if index>=0:self.output.setCurrentIndex(index)
        self.output.blockSignals(False);self.load()

    def selected(self):
        return next((screen for screen in self.detected if screen['id']==self.output.currentData()),None)

    def load(self):
        screen=self.selected()
        if not screen:
            self.status.setText('Nenhuma tela conectada.');return
        current=settings(screen)
        self.mode.clear()
        for mode in screen.get('modes',[]):
            self.mode.addItem(mode.get('name') or mode['id'],str(mode['id']))
        self.mode.setCurrentIndex(max(0,self.mode.findData(current['mode'])))
        self.scale.setValue(current['scale']);self.rotation.setCurrentIndex(max(0,self.rotation.findData(current['rotation'])))
        self.x.setValue(current['x']);self.y.setValue(current['y']);self.enabled.setChecked(current['enabled'])
        self.toggle_fields();self.status.setText('Configuração atual carregada.')

    def toggle_fields(self):
        for widget in (self.mode,self.scale,self.rotation,self.x,self.y):widget.setEnabled(self.enabled.isChecked())

    def save(self):
        screen=self.selected()
        if not screen:return
        if not self.enabled.isChecked() and sum(bool(item.get('enabled')) for item in self.detected)<=1:
            self.status.setText('Mantenha ao menos uma tela ligada.');return
        before=settings(screen);modes={str(item['id']) for item in screen.get('modes',[])}
        after={'id':before['id'],'enabled':self.enabled.isChecked(),'mode':self.mode.currentData(),
               'scale':self.scale.value(),'rotation':self.rotation.currentData(),'x':self.x.value(),'y':self.y.value()}
        if before==after:
            self.status.setText('Nenhuma alteração.');return
        try:apply(after,modes)
        except (OSError,ValueError,subprocess.SubprocessError) as error:
            self.status.setText('Falha ao aplicar: '+str(error));return
        box=QMessageBox(self);box.setWindowTitle('Confirmar tela');box.setText('A imagem está legível? Mantenha as alterações em até 15 segundos.')
        keep=box.addButton('Manter',QMessageBox.ButtonRole.AcceptRole)
        box.addButton('Reverter',QMessageBox.ButtonRole.RejectRole)
        timer=QTimer(box);timer.setSingleShot(True);timer.timeout.connect(box.reject);timer.start(15000)
        box.exec();timer.stop()
        if box.clickedButton() is keep:
            self.status.setText('Configuração de tela mantida.');self.refresh();return
        try:apply(before,modes);self.status.setText('Configuração anterior restaurada.')
        except (OSError,ValueError,subprocess.SubprocessError) as error:
            self.status.setText('Falha na reversão automática: '+str(error))
        self.refresh()
