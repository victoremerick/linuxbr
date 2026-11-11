"""Authenticated maintenance and minimal server configuration console."""
import getpass
import os
from pathlib import Path
import shutil
import socket
import sys
from PyQt6.QtCore import Qt,QProcess
from PyQt6.QtGui import QIcon,QKeySequence,QShortcut
from PyQt6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QGridLayout,QLabel,QPushButton,QMessageBox
from boot_policy import mode
from grub_modes import MODES


class Console(QMainWindow):
    def __init__(self):
        super().__init__();self.children_windows=[];self.selected=mode();self.setWindowTitle('Linux BR — Manutenção' if self.selected else 'Linux BR — Console do servidor');self.resize(980,640)
        self.setStyleSheet('QWidget {background:#101820;color:#edf4fa;font-size:15px;} QPushButton {background:#183047;border:1px solid #34536e;padding:14px;text-align:left;} QPushButton:hover,QPushButton:focus {background:#234a6a;border:2px solid #7fc3ff;}')
        body=QWidget();self.setCentralWidget(body);layout=QVBoxLayout(body);title=QLabel(self.windowTitle());title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        subtitle=QLabel(socket.gethostname()+' · '+getpass.getuser()+' · '+(MODES[self.selected][0] if self.selected else 'Sessão mínima sem o desktop completo'));layout.addWidget(subtitle)
        note=QLabel('Alterações administrativas exigem autorização. '+('A rede está disponível para diagnóstico; compartilhamento e acesso remoto permanecem bloqueados.' if self.selected=='safe-network' else 'Rede e serviços opcionais estão bloqueados nesta inicialização.' if self.selected else 'Configure o host, serviços e máquinas virtuais.'))
        note.setWordWrap(True);layout.addWidget(note)
        if Path('/run/live/medium').exists():
            live=QLabel('Modo live: as alterações da sessão são temporárias. Confira os discos antes de instalar ou restaurar dados.');live.setWordWrap(True);layout.addWidget(live)
        grid=QGridLayout();layout.addLayout(grid,1)
        actions=[('Terminal de manutenção','utilities-terminal',self.terminal),
                 ('Configurar rede e DNS','network-wired',lambda:self.embedded('network_details_page','NetworkDetails')),
                 ('Serviços e tarefas','preferences-system-services',lambda:self.embedded('administration','Administration')),
                 ('Máquinas virtuais','computer',self.virtualization),
                 ('Nome do computador','network-server',lambda:self.host(0)),
                 ('Usuários e permissões','system-users',lambda:self.host(1)),
                 ('Armazenamento','drive-harddisk',lambda:self.launch(['partitionmanager'])),
                 ('Firewall','security-high',lambda:self.embedded('firewall','Firewall')),
                 ('Restaurar ponto de sistema','document-revert',lambda:self.launch(['pkexec','timeshift-gtk'])),
                 ('Recursos opcionais','system-software-install',lambda:self.embedded('features_page','Features')),
                 ('Eventos de inicialização','view-list-text',lambda:self.launch(['xterm','-e','journalctl','-b','--no-pager'])),
                 ('Data e hora','preferences-system-time',lambda:self.host(2)),
                 ('Acesso remoto','network-connect',lambda:self.host(3)),
                 ('Atualizações','system-software-update',lambda:self.launch(['linuxbr-store','--updates']) if shutil.which('linuxbr-store') else self.launch(['pkexec','synaptic'])),
                 ('Recuperação e opções avançadas','tools-wizard',lambda:self.launch(['linuxbr-recovery-options'])),
                 ('Reiniciar','system-reboot',lambda:self.power('reboot')),
                 ('Desligar','system-shutdown',lambda:self.power('poweroff')),
                 ('Recuperar atualização','edit-undo',lambda:self.launch(['linuxbr-recover-update']))]
        if Path('/run/live/medium').exists():actions.insert(1,('Instalar Linux BR','system-software-install',lambda:self.launch(['calamares-install-linuxbr'])))
        for index,(label,icon,action) in enumerate(actions):
            button=QPushButton(QIcon.fromTheme(icon),f'{index+1}. '+label);button.setAutoDefault(True);button.clicked.connect(action);grid.addWidget(button,index//3,index%3)
            if self.selected and (label in {'Máquinas virtuais','Acesso remoto','Atualizações'} or label=='Configurar rede e DNS' and self.selected!='safe-network'):
                button.setEnabled(False);button.setToolTip('Serviço bloqueado neste modo de inicialização.')
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        QShortcut(QKeySequence('Ctrl+Alt+T'),self,activated=actions[0][2])

    def terminal(self):
        profile=Path('/usr/share/linuxbr/bashrc')
        arguments=['--rcfile',str(profile),'-i'] if profile.is_file() else ['-l']
        self.launch(['xterm','-T','Linux BR — Terminal de manutenção','-fa','monospace','-fs','12','-e','/bin/bash',*arguments])

    def launch(self,argv):
        if not shutil.which(argv[0]):self.status.setText('Ferramenta não instalada: '+argv[0]+'. Use os recursos opcionais para adicioná-la.');return
        if not QProcess.startDetached(argv[0],argv[1:])[0]:self.status.setText('Não foi possível iniciar a ferramenta.')

    def embedded(self,module,name):
        for directory in ['/usr/lib/linuxbr-system','/usr/lib/linuxbr-server']:
            if Path(directory).is_dir() and directory not in sys.path:sys.path.insert(0,directory)
        try:
            import importlib
            window=getattr(importlib.import_module(module),name)();window.resize(1080,700);window.setWindowFlag(Qt.WindowType.Window,True);window.show();self.children_windows.append(window)
        except Exception as error:self.status.setText('Não foi possível abrir a ferramenta: '+str(error))

    def host(self,section):
        if Path('/usr/lib/linuxbr-server/host_page.py').is_file():
            if '/usr/lib/linuxbr-server' not in sys.path:sys.path.insert(0,'/usr/lib/linuxbr-server')
            from host_page import Host
            window=Host(section);window.setWindowFlag(Qt.WindowType.Window,True);window.resize(980,700);window.show();self.children_windows.append(window)
        else:
            self.launch(['linuxbr-system','--page',{0:'about',1:'users',2:'datetime',3:'remote-desktop'}[section]])

    def virtualization(self):
        if shutil.which('linuxbr-virtual-machines'):self.launch(['linuxbr-virtual-machines']);return
        target=Path('/usr/lib/linuxbr-server/virtualization.py')
        self.launch(['python3',str(target)]) if target.is_file() else self.launch(['virt-manager'])

    def normal(self):
        self.launch(['linuxbr-boot-options'])

    def power(self,action):
        if QMessageBox.question(self,'Confirmar','Salve seu trabalho. '+('Reiniciar' if action=='reboot' else 'Desligar')+' o computador?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.launch(['systemctl',action])

    def closeEvent(self,event):
        if any(getattr(w,'jobs',set()) or getattr(w,'running',False) or any(c.process.state()!=QProcess.ProcessState.NotRunning for c in getattr(w,'commands',[]) if hasattr(c,'process')) for w in self.children_windows):event.ignore();return
        if QMessageBox.question(self,'Sair da sessão','Encerrar esta sessão de configuração?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:event.ignore();return
        super().closeEvent(event)


if __name__=='__main__':
    app=QApplication(sys.argv)
    sys.path.insert(0,'/usr/lib/linuxbr-server')
    from desktop_theme import initialize
    initialize();QIcon.setThemeName('breeze-dark');window=Console();window.show();sys.exit(app.exec())
