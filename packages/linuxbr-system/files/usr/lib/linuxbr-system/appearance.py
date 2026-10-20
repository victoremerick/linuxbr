"""Limited appearance preferences: color and brightness, not global layout packs."""
import subprocess
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel,QComboBox,QPushButton,QFormLayout

class ThemePreview(QWidget):
    """Preview only: selecting colors does not modify the session."""
    def __init__(self):
        super().__init__();self.dark=False;self.accent='#6054a3'
        self.setMinimumHeight(190);self.setAccessibleName('Pré-visualização do tema')
    def paintEvent(self,event):
        p=QPainter(self); bg=QColor('#242b33' if self.dark else '#f3f4f6');fg=QColor('#edf0f4' if self.dark else '#1e252c')
        p.fillRect(self.rect(),QColor('#151b22' if self.dark else '#dce1e8'))
        p.fillRect(16,16,self.width()-32,self.height()-32,bg)
        p.setPen(fg);p.drawText(30,40,'Linux BR — Pré-visualização')
        p.drawText(self.width()-110,40,'−     □     ×')
        p.drawText(30,82,'Cores sólidas. Controles simples.')
        p.fillRect(30,110,120,36,QColor(self.accent));p.setPen(QColor('white'));p.drawText(30,110,120,36,Qt.AlignmentFlag.AlignCenter,'Primário')
        p.setPen(QPen(fg,1));p.drawRect(168,110,120,36);p.drawText(168,110,120,36,Qt.AlignmentFlag.AlignCenter,'Secundário')
        p.end()

class Appearance(QWidget):
    def __init__(self):
        super().__init__(); self.process=None
        body=QVBoxLayout(self);body.setContentsMargins(32,28,32,28);body.setSpacing(16)
        heading=QLabel('Personalização');heading.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(heading)
        note=QLabel('Escolha o modo e a cor de destaque. O formato das janelas, os botões e a organização do Linux BR são mantidos.');note.setWordWrap(True);body.addWidget(note)
        form=QFormLayout();self.mode=QComboBox();self.accent=QComboBox()
        for text,value in [('Claro','Light'),('Escuro','Dark')]:self.mode.addItem(text,value)
        for text,value in [('Violeta','Violet'),('Azul','Blue'),('Verde','Green'),('Grafite','Graphite')]:self.accent.addItem(text,value)
        try:
            scheme=subprocess.check_output(['kreadconfig6','--file','kdeglobals','--group','General','--key','ColorScheme'],text=True,timeout=2).strip()
            for i in range(self.mode.count()):
                for j in range(self.accent.count()):
                    if scheme=='LinuxBR'+self.mode.itemData(i)+self.accent.itemData(j):self.mode.setCurrentIndex(i);self.accent.setCurrentIndex(j)
        except (OSError,subprocess.SubprocessError):pass
        form.addRow('Modo',self.mode);form.addRow('Cor de destaque',self.accent);body.addLayout(form)
        self.preview=ThemePreview();body.addWidget(self.preview)
        self.mode.currentIndexChanged.connect(self.update_preview);self.accent.currentIndexChanged.connect(self.update_preview);self.update_preview()
        self.apply=QPushButton('Aplicar');self.apply.setProperty('primary',True);self.apply.clicked.connect(self.save);body.addWidget(self.apply)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status);body.addStretch()
    def update_preview(self):
        self.preview.dark=self.mode.currentData()=='Dark'
        self.preview.accent={'Violet':'#6054a3','Blue':'#005fb8','Green':'#147050','Graphite':'#4f5b66'}[self.accent.currentData()]
        self.preview.update()
    def save(self):
        self.apply.setEnabled(False); self.mode.setEnabled(False);self.accent.setEnabled(False)
        self.process=QProcess(self);self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        self.process.start('plasma-apply-colorscheme',['LinuxBR'+self.mode.currentData()+self.accent.currentData()])
    def failed(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            self.apply.setEnabled(True);self.mode.setEnabled(True);self.accent.setEnabled(True)
            self.status.setText('Não foi possível iniciar a aplicação das cores.')

    def finished(self,code,status):
        self.apply.setEnabled(True); self.mode.setEnabled(True);self.accent.setEnabled(True)
        if code:
            self.status.setText('Não foi possível aplicar as cores. Confira se linuxbr-desktop está instalado.');return
        dark=self.mode.currentData()=='Dark'
        try:
            for version in ('3.0','4.0'):
                for key,value in [('gtk-theme-name','LinuxBR'+self.mode.currentData()+self.accent.currentData()),('gtk-application-prefer-dark-theme','true' if dark else 'false')]:
                    subprocess.run(['kwriteconfig6','--file','gtk-'+version+'/settings.ini','--group','Settings','--key',key,value],check=True,timeout=3)
            subprocess.run(['kwriteconfig6','--file','kwinrc','--group','org.kde.kdecoration2','--key','theme','__aurorae__svg__LinuxBRClean-'+self.mode.currentData()],check=True,timeout=3)
            subprocess.run(['dbus-send','--session','--type=signal','/KWin','org.kde.KWin.reloadConfig'],check=True,timeout=3)
            self.status.setText('Cores aplicadas. Reabra aplicativos GTK para atualizar sua aparência.')
        except (OSError,subprocess.SubprocessError):self.status.setText('Cores aplicadas; não foi possível atualizar todos os aplicativos. Encerre e inicie a sessão.')
