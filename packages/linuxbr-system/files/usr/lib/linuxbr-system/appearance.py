"""Limited appearance preferences: color and brightness, not global layout packs."""
import json
from pathlib import Path
import sqlite3
import subprocess
import dbus
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel,QComboBox,QPushButton,QFormLayout,QFileDialog,QHBoxLayout,QMessageBox

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
        transfer = QHBoxLayout()
        for label, handler in [('Exportar cores…', self.export_colors), ('Importar cores…', self.import_colors),
                               ('Exportar favoritos…', self.export_favorites), ('Importar favoritos…', self.import_favorites)]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            transfer.addWidget(button)
        body.addLayout(transfer)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status);body.addStretch()

    def export_favorites(self):
        from start_favorites import export_favorites

        filename, _ = QFileDialog.getSaveFileName(self, 'Exportar favoritos do Iniciar',
                                                 'linuxbr-favoritos.json', 'JSON (*.json)')
        if filename:
            try:
                export_favorites(filename)
                self.status.setText('Favoritos de aplicativos exportados.')
            except (OSError, sqlite3.Error, dbus.DBusException):
                QMessageBox.warning(self, 'Exportar favoritos', 'Não foi possível ler os favoritos do menu Iniciar.')

    def import_favorites(self):
        from start_favorites import import_favorites, installed_apps, load_favorites

        title = 'Importar favoritos do Iniciar'
        filename, _ = QFileDialog.getOpenFileName(self, title, '', 'JSON (*.json)')
        if not filename:
            return
        try:
            ids = load_favorites(filename)
            apps = installed_apps(ids)
            if not apps:
                QMessageBox.information(self, title, 'Nenhum aplicativo desta lista está instalado e visível.')
                return
            dialog = QMessageBox(QMessageBox.Icon.Question, title,
                                 f'Adicionar {len(apps)} aplicativos aos favoritos? '
                                 f'Itens indisponíveis nesta conta: {len(ids) - len(apps)}.',
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, self)
            dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
            dialog.setDetailedText('\n'.join(apps.values()))
            if dialog.exec() == QMessageBox.StandardButton.Yes:
                import_favorites(apps)
                self.status.setText('Aplicativos adicionados aos favoritos do menu Iniciar.')
        except (OSError, ValueError, dbus.DBusException):
            QMessageBox.warning(self, title, 'A importação não foi concluída. Confira os favoritos e o arquivo selecionado.')

    def export_colors(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Exportar cores', 'linuxbr-cores.json', 'JSON (*.json)')
        if not filename:
            return
        from store_sources import atomic_write
        record = dict(schema='linuxbr-colors-1', mode=self.mode.currentData(), accent=self.accent.currentData())
        try:
            atomic_write(Path(filename), (json.dumps(record) + '\n').encode(), 0o600)
        except OSError as error:
            QMessageBox.warning(self, 'Exportar cores', str(error))

    def import_colors(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Importar cores', '', 'JSON (*.json)')
        if not filename:
            return
        try:
            with Path(filename).open('rb') as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise ValueError
            record = json.loads(raw)
            if not isinstance(record, dict) or record.get('schema') != 'linuxbr-colors-1':
                raise ValueError
            mode = self.mode.findData(record.get('mode'))
            accent = self.accent.findData(record.get('accent'))
            if mode < 0 or accent < 0:
                raise ValueError
        except (OSError, ValueError):
            QMessageBox.warning(self, 'Importar cores', 'Escolha um arquivo de cores exportado pelo Linux BR.')
            return
        self.mode.setCurrentIndex(mode)
        self.accent.setCurrentIndex(accent)
        self.status.setText('Confira a prévia e clique em Aplicar para usar as cores importadas.')
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
