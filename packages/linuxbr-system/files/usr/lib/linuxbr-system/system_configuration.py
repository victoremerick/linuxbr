"""System configuration groups existing controls without maintaining parallel state."""
from pathlib import Path
import sys
from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QTabWidget,QPushButton


class SystemConfiguration(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Configuração do Sistema');self.resize(1120,760);self.pages=[]
        layout=QVBoxLayout(self);title=QLabel('Configuração do Sistema');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        general=QWidget();box=QVBoxLayout(general);note=QLabel('Inicialização normal usa a configuração habitual. Diagnóstico registra o boot sem bloquear serviços. Para uma inicialização seletiva, revise serviços e programas de início da sessão; as alterações são exibidas nos controles próprios.');note.setWordWrap(True);box.addWidget(note)
        for label,icon,index in [('Normal, diagnóstico e modos de segurança','system-reboot',1),('Selecionar serviços de sistema e usuário','preferences-system-services',2),('Selecionar programas de inicialização','system-run',3)]:
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(lambda _,i=index:self.tabs.setCurrentIndex(i));box.addWidget(button)
        box.addStretch();self.tabs.addTab(general,'Geral')
        if Path('/usr/lib/linuxbr-boot').is_dir():
            sys.path.insert(0,'/usr/lib/linuxbr-boot')
            from boot_page import BootOptions
            boot=BootOptions()
        else:boot=QLabel('Instale o componente de inicialização do Linux BR para configurar os modos de boot.')
        self.add(boot,'Inicialização do sistema')
        from administration import Administration
        from startup_page import Startup
        self.add(Administration(),'Serviços e tarefas');self.add(Startup(),'Programas de inicialização')
        tools=QWidget();box=QVBoxLayout(tools)
        for label,icon,argv in [('Gerenciador de Tarefas','utilities-system-monitor',['linuxbr-task-manager']),('Recursos opcionais','preferences-plugin',['linuxbr-system','--page','optional-features']),('Recuperação e backup','document-revert',['linuxbr-recovery']),('Variáveis de ambiente','preferences-system',['linuxbr-system','--page','environment']),('Detalhes da conexão','network-wired',['linuxbr-system','--page','network-details'])]:
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(lambda _,a=argv:QProcess.startDetached(a[0],a[1:]));box.addWidget(button)
        box.addStretch();self.tabs.addTab(tools,'Ferramentas')

    def add(self,page,title):self.pages.append(page);self.tabs.addTab(page,title)

    @property
    def jobs(self):return {job for page in self.pages for job in getattr(page,'jobs',set())}

    def closeEvent(self,event):
        if self.jobs:event.ignore()
        else:super().closeEvent(event)


if __name__=='__main__':
    app=QApplication(sys.argv);window=SystemConfiguration();window.show();sys.exit(app.exec())
