"""Explicit local package review; installation stays with Discover/PackageKit."""
from pathlib import Path
import subprocess
import sys
from PyQt6.QtCore import QProcess,Qt
from PyQt6.QtGui import QKeySequence,QShortcut
from PyQt6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox,QPlainTextEdit

from visual_style import BUTTONS

SUPPORTED={'.deb':'Pacote Debian', '.flatpak':'Pacote Flatpak', '.flatpakref':'Referência Flatpak', '.exe':'Programa Windows', '.msi':'Instalador Windows'}

def inspect_package(filename):
    try:path=Path(filename).expanduser().resolve(strict=True)
    except FileNotFoundError:raise ValueError('Arquivo não encontrado. Selecione-o novamente.') from None
    if not path.is_file():raise ValueError('Selecione um arquivo de programa.')
    suffix=path.suffix.lower()
    if suffix not in SUPPORTED:
        reason={'rpm':'RPM é um pacote de outra família de distribuições. Procure a versão DEB ou Flatpak.', 'msi':'Este instalador é para Windows. Procure uma versão para Linux ou uma solução de compatibilidade validada pelo fornecedor.', 'exe':'Este programa é para Windows. Procure uma versão para Linux.', 'appimage':'AppImage é um aplicativo portátil, não um pacote instalável pelo APT. Use a versão DEB ou Flatpak para gerenciamento pela Central.'}
        return path,False,reason.get(suffix.lstrip('.'),'Formato não suportado pelo instalador do Linux BR. Use DEB ou Flatpak.')
    detail=SUPPORTED[suffix]
    if suffix in ('.exe','.msi'):
        from windows_runner import inspect_windows_file
        path,kind=inspect_windows_file(path)
        return path,True,detail+' ('+kind+'). Continuar abre Programas Windows e jogos para escolher um ambiente Wine. A compatibilidade varia por programa.'
    if suffix=='.deb':
        result=subprocess.run(['dpkg-deb','--show','--showformat=${Package}\n${Version}\n${Architecture}\n',str(path)],capture_output=True,text=True,timeout=10)
        if result.returncode:raise ValueError('O arquivo não é um pacote Debian válido.')
        values=result.stdout.splitlines()
        if len(values)!=3:raise ValueError('Metadados do pacote inválidos.')
        native=subprocess.check_output(['dpkg','--print-architecture'],text=True,timeout=3).strip()
        if values[2] not in ('all',native):raise ValueError('Arquitetura incompatível: '+values[2]+'. Este sistema usa '+native+'.')
        detail+='\nPrograma: '+values[0]+'\nVersão: '+values[1]+'\nArquitetura: '+values[2]
    return path,True,detail

class Installer(QWidget):
    def __init__(self,filename=None):
        super().__init__();self.path=None;self.setStyleSheet(BUTTONS);self.setWindowTitle('Linux BR — Instalar programa');self.resize(600,480)
        self.setAcceptDrops(True)
        body=QVBoxLayout(self);body.setContentsMargins(24,24,24,24);body.setSpacing(16)
        title=QLabel('Instalar programa');title.setStyleSheet('font-size:24px;font-weight:600');body.addWidget(title)
        self.details=QPlainTextEdit('Arraste um arquivo para esta janela ou use Selecionar arquivo.\n\nAceita DEB, Flatpak, Flatpakref e programas Windows EXE/MSI.\n\nAtalho: Ctrl+O para escolher um arquivo.');self.details.setReadOnly(True);self.details.setAcceptDrops(False);self.details.setMinimumHeight(130);body.addWidget(self.details,1)
        choose=QPushButton('Selecionar arquivo…');choose.clicked.connect(self.choose);body.addWidget(choose)
        self.note=QLabel('Continue apenas se você confia na origem do arquivo. A próxima janela mostra a instalação e pode solicitar autenticação administrativa.');self.note.setWordWrap(True);body.addWidget(self.note)
        self.install=QPushButton('Continuar instalação');self.install.setProperty('primary',True);self.install.setEnabled(False);self.install.clicked.connect(self.start);body.addWidget(self.install)
        cancel=QPushButton('Fechar');cancel.clicked.connect(self.close);body.addWidget(cancel)
        QShortcut(QKeySequence('Ctrl+O'),self,activated=self.choose)
        if filename:self.load(filename)
    def choose(self):
        name,_=QFileDialog.getOpenFileName(self,'Selecionar programa','','Programas compatíveis (*.deb *.flatpak *.flatpakref *.msi *.MSI *.exe *.EXE);;Todos os arquivos (*)')
        if name:self.load(name)
    def dragEnterEvent(self,event):
        urls=event.mimeData().urls()
        if len(urls)==1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED:
            event.acceptProposedAction()
    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if len(urls)==1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED:
            self.load(urls[0].toLocalFile());event.acceptProposedAction()
    def load(self,name):
        self.install.setEnabled(False);self.path=None
        self.install.setText('Continuar instalação')
        self.note.setText('Continue apenas se você confia na origem do arquivo. O Discover verifica o pacote, mostra a instalação e pode solicitar autenticação administrativa.')
        try:
            path,allowed,detail=inspect_package(name)
            self.details.setPlainText(path.name+'\nPasta: '+str(path.parent)+'\n\n'+detail)
            if allowed:
                self.path=path;self.install.setEnabled(True)
                if path.suffix.lower() in ('.exe','.msi'):
                    self.install.setText('Escolher ambiente Wine…')
                    self.note.setText('A próxima janela permite escolher o ambiente e confirmar a execução. Wine usa os acessos da sua conta e não precisa de sudo. A compatibilidade depende do programa.')
            else:self.note.setText('Escolha uma versão DEB ou Flatpak para Linux, ou um EXE/MSI compatível com Wine. O arquivo selecionado não será executado.')
        except (OSError,ValueError,subprocess.SubprocessError) as error:self.details.setPlainText('Não foi possível abrir o pacote: '+str(error))
    def start(self):
        if self.path is None:return
        # Revalidate after the user reviewed it. Discover performs its own checks.
        try:
            path,allowed,_=inspect_package(str(self.path))
            if not allowed:raise ValueError('Formato incompatível.')
            command,args=('linuxbr-windows',[str(path)]) if path.suffix.lower() in ('.exe','.msi') else ('plasma-discover',['--local-filename',str(path)])
            if not QProcess.startDetached(command,args)[0]:raise OSError('Ferramenta indisponível: '+command)
            self.close()
        except (OSError,ValueError,subprocess.SubprocessError) as error:QMessageBox.warning(self,'Não foi possível continuar',str(error))
if __name__=='__main__':
    app=QApplication(sys.argv);app.setDesktopFileName("linuxbr-install-package");window=Installer(sys.argv[1] if len(sys.argv)>1 else None);window.show();sys.exit(app.exec())
