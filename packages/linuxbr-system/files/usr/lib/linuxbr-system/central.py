#!/usr/bin/python3
"""System hub: existing KDE tools and the shared Linux BR storage interface."""
import shutil
import sys
sys.path.insert(0, '/usr/lib/linuxbr-drive-manager')
sys.path.insert(0, '/usr/lib/linuxbr-device-manager')
from PyQt6.QtCore import QProcess, QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                            QListWidget, QListWidgetItem, QStackedWidget, QLabel, QPushButton, QMessageBox, QToolButton, QScrollArea, QFrame, QLineEdit)
from app import Window as Drives
from devices import Devices
from about import About
from accounts import AccountsPage
from appearance import Appearance
from proxy import Proxy
from firewall import Firewall
from tasks import Tasks
from network_page import IPPage
from audio import Audio
from visual_style import BUTTONS

PAGES = [
 ('Sistema', '', []),
 ('Dispositivos', 'Hardware, periféricos e conexões locais.', [
     ('Informações e dispositivos', ['kinfocenter']),
     ('Bluetooth', ['kcmshell6', 'kcm_bluetooth']),
     ('Áudio e headsets', ['kcmshell6', 'kcm_pulseaudio']),
     ('Celulares', ['kdeconnect-settings']),
     ('Impressoras', ['kcmshell6', 'kcm_printer_manager'])]),
 ('Armazenamento', '', []),
 ('Rede', 'Conexões, Wi-Fi, VPN e unidades de rede.', [
     ('Wi-Fi e Ethernet', ['kcmshell6', 'kcm_networkmanagement']),
     ('VPN', ['kcmshell6', 'kcm_networkmanagement']),
     
     ('Bluetooth', ['kcmshell6', 'kcm_bluetooth'])]),
 ('Usuários', 'Contas locais e configurações de acesso.', [
     ('Gerenciar usuários', ['kcmshell6', 'kcm_users'])]),
 ('Organização', '', []),
 ('Administração', 'Ferramentas de manutenção do sistema.', [
     ('Aplicativos e atualizações', ['plasma-discover']),
     ('Aplicativos na inicialização', ['kcmshell6', 'kcm_autostart']),
     ('Logs desta inicialização', ['konsole', '-e', 'journalctl', '-b', '--pager-end']),
     ('Estado dos serviços', ['konsole', '-e', 'systemctl', 'status']),
     ('Configurações do terminal', ['linuxbr-terminal-settings']),
     ('Configurações avançadas', ['systemsettings'])]),
 ('Programas', 'Instale, remova e atualize aplicativos.', [
     ('Instalar a partir de arquivo', ['linuxbr-install-package']),
     ('Programas instalados', ['plasma-discover', '--mode', 'Installed']),
     ('Encontrar programas', ['plasma-discover']),
     ('Atualizações', ['plasma-discover', '--mode', 'Update'])]),
 ('Telas', 'Monitores, resolução, escala, orientação e disposição das telas.', [
     ('Configurar telas e resoluções', ['kcmshell6', 'kcm_kscreen']),
     ('Luz noturna', ['kcmshell6', 'kcm_nightlight'])]),
 ('Personalização', '', []),
 ('Acesso remoto', 'Conecte a outro computador ou compartilhe sua sessão com autorização.', [
     ('Conectar por RDP ou VNC', ['krdc']),
     ('Compartilhar esta sessão (VNC)', ['krfb'])]),
 ('Energia e bateria', 'Configure separadamente o uso na tomada e na bateria. As ações disponíveis dependem do hardware.', [
     ('Tela ligada, suspensão, tampa e botão de energia', ['kcmshell6', 'kcm_powerdevilprofilesconfig']),
     ('Bloqueio automático da sessão', ['kcmshell6', 'kcm_screenlocker'])]),
 ('Notificações', 'Alertas temporários, histórico, sons e Não perturbe.', [
     ('Preferências e permissões por aplicativo', ['kcmshell6', 'kcm_notifications'])]),
 ('Acessibilidade', 'Recursos de visão, teclado e interação.', [
     ('Recursos de acessibilidade', ['kcmshell6', 'kcm_access'])]),
 ('Hora e idioma', 'Data, fuso horário, idioma e formatos brasileiros.', [
     ('Data e hora', ['kcmshell6', 'kcm_clock']),
     ('Idioma e formatos regionais', ['kcmshell6', 'kcm_regionandlang']),
     ('Teclado e layouts', ['kcmshell6', 'kcm_keyboard'])]),
 ('Entrada e atalhos', 'Mouse, touchpad, teclado, gestos disponíveis e controles.', [
     ('Mouse', ['kcmshell6', 'kcm_mouse']),
     ('Touchpad', ['kcmshell6', 'kcm_touchpad']),
     ('Atalhos do teclado', ['kcmshell6', 'kcm_keys']),
     ('Controle de jogos', ['kcmshell6', 'kcm_gamecontroller']),
     ('Mesa digitalizadora', ['kcmshell6', 'kcm_tablet']),
     ('Tela sensível ao toque', ['kcmshell6', 'kcm_touchscreen'])]),
 ('Pesquisa e padrões', 'Pesquisa de arquivos, aplicativos padrão e pastas pessoais.', [
     ('Indexação de arquivos', ['kcmshell6', 'kcm_baloofile']),
     ('Pesquisa do sistema', ['kcmshell6', 'kcm_plasmasearch']),
     ('Aplicativos padrão', ['kcmshell6', 'kcm_componentchooser']),
     ('Pastas pessoais', ['kcmshell6', 'kcm_desktoppaths'])]),
 ('Privacidade e sessão', 'Bloqueio, dados de uso e comportamento ao entrar ou sair.', [
     ('Bloqueio e senha da sessão', ['kcmshell6', 'kcm_screenlocker']),
     ('Dados de uso e feedback', ['kcmshell6', 'kcm_feedback']),
     ('Restaurar sessão e encerramento', ['kcmshell6', 'kcm_smserver'])]),
]
PAGES += [
 ('Firewall', 'Proteção de rede, portas liberadas e aplicativos com portas abertas.', []),
 ('Gerenciador de tarefas', 'Processos, uso de CPU e memória.', []),
 ('Áudio', 'Alto-falantes, microfones, perfis e mixer por aplicativo.', []),
 ('Endereços IP e DNS', 'Propriedades IPv4 e IPv6 das conexões de rede.', []),
]

class Central(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(BUTTONS)
        self.setWindowTitle('Linux BR — Central do Sistema')
        self.setWindowIcon(QIcon.fromTheme('linuxbr'))
        self.resize(1260, 720)
        self.setMinimumSize(900, 560)
        root=QWidget(); self.setCentralWidget(root)
        layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar=QWidget(); sidebar.setFixedWidth(224)
        side=QVBoxLayout(sidebar); side.setContentsMargins(12,20,12,16); side.setSpacing(16)
        brand=QLabel('Linux BR'); brand.setStyleSheet('font-size:18px; font-weight:600; padding-left:12px')
        side.addWidget(brand)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar configuração…');self.search.setClearButtonEnabled(True);side.addWidget(self.search)
        self.nav=QListWidget(); self.nav.setSpacing(2); self.nav.setIconSize(QSize(18,18))
        self.nav.setObjectName('linuxbrNavigation')
        self.nav.setStyleSheet("""
            QListWidget#linuxbrNavigation { border: none; background: palette(window); }
            QListWidget#linuxbrNavigation::item { padding: 4px 8px; border-radius: 0; border-left: 3px solid transparent; }
            QListWidget#linuxbrNavigation::item:hover { background: palette(alternate-base); }
            QListWidget#linuxbrNavigation::item:selected { background: palette(highlight); color: palette(highlighted-text); border-left: 3px solid palette(highlight); }
            QListWidget#linuxbrNavigation::item:focus { border-left: 3px solid palette(highlight); }
        """)
        self.nav.setAccessibleName('Categorias da Central do Sistema'); side.addWidget(self.nav,1)
        footer=QLabel('Central do Sistema'); footer.setStyleSheet('padding-left:12px'); side.addWidget(footer)
        self.stack=QStackedWidget()
        layout.addWidget(sidebar); layout.addWidget(self.stack,1)
        self.drives=Drives(); self.devices=Devices()
        self.firewall=Firewall();self.tasks=Tasks();self.audio=Audio();self.ip=IPPage()
        self.users=AccountsPage(False,self.launch); self.organization=AccountsPage(True,self.launch)
        icons=['computer','preferences-devices','drive-harddisk','network-workgroup','system-users','preferences-system','preferences-other','applications-other','video-display','preferences-desktop-theme','krdc']
        for index,(title,description,actions) in enumerate(PAGES):
            item=QListWidgetItem(QIcon.fromTheme(icons[index] if index<len(icons) else 'preferences-system'),title); item.setSizeHint(QSize(190,38)); self.nav.addItem(item)
            if title=='Sistema':
                page=About(self.launch,self.navigate)
            elif title=='Personalização':
                page=Appearance()
            elif title=='Usuários':
                page=self.users
            elif title=='Organização':
                page=self.organization
            elif title in ('Firewall','Gerenciador de tarefas','Áudio','Endereços IP e DNS'):
                page={'Firewall':self.firewall,'Gerenciador de tarefas':self.tasks,
                      'Áudio':self.audio,'Endereços IP e DNS':self.ip}[title]
            elif title=='Dispositivos':
                page=QWidget(); body=QVBoxLayout(page); body.setContentsMargins(0,0,0,16)
                body.addWidget(self.devices)
                links=QVBoxLayout(); links.setContentsMargins(24,0,24,0)
                for caption,command in actions:
                    links.addWidget(self.action_link(caption,lambda checked=False,cmd=command:self.launch(cmd)))
                links.addStretch(); body.addLayout(links)
            elif title=='Armazenamento':
                page=QWidget(); body=QVBoxLayout(page); body.setContentsMargins(0,0,0,16)
                body.addWidget(self.drives)
            else:
                page=QScrollArea(); page.setWidgetResizable(True); page.setFrameShape(QFrame.Shape.NoFrame)
                content=QWidget(); page.setWidget(content); body=QVBoxLayout(content)
                body.setContentsMargins(32,28,32,28); body.setSpacing(16)
                heading=QLabel(title); heading.setStyleSheet('font-size:26px; font-weight:600'); body.addWidget(heading)
                text=QLabel(description); text.setWordWrap(True); body.addWidget(text)
                for caption,command in actions:
                    body.addWidget(self.action_link(caption,lambda checked=False,cmd=command:self.launch(cmd)),0,Qt.AlignmentFlag.AlignLeft)
                if title=='Acesso remoto':
                    note=QLabel('O compartilhamento só é iniciado por você. Configure senha e permissão de controle no compartilhador. Para acesso fora da rede local, use a VPN da empresa.'); note.setWordWrap(True); body.addWidget(note)
                if title=='Rede':
                    body.addWidget(self.action_link('Endereços IP e DNS',lambda:self.navigate('Endereços IP e DNS')),0,Qt.AlignmentFlag.AlignLeft)
                    body.addWidget(self.action_link('Configurar proxy',self.open_proxy),0,Qt.AlignmentFlag.AlignLeft)
                    body.addWidget(self.action_link('Compartilhamentos e letras de rede',lambda:self.navigate('Armazenamento')),0,Qt.AlignmentFlag.AlignLeft)
                if title=='Administração':
                    body.addWidget(self.action_link('Firewall',lambda:self.navigate('Firewall')),0,Qt.AlignmentFlag.AlignLeft)
                    body.addWidget(self.action_link('Gerenciador de tarefas',lambda:self.navigate('Gerenciador de tarefas')),0,Qt.AlignmentFlag.AlignLeft)
                body.addStretch()
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.search.textChanged.connect(self.filter_pages)
        self.navigate('Sistema')

    def filter_pages(self,text):
        import unicodedata
        def normalized(value):
            return ''.join(c for c in unicodedata.normalize('NFD',value.casefold()) if not unicodedata.combining(c))
        query=normalized(text.strip());first=None
        for i,(title,description,actions) in enumerate(PAGES):
            visible=query in normalized(' '.join([title,description]+[a[0] for a in actions]))
            self.nav.item(i).setHidden(not visible)
            if visible and first is None:first=i
        if first is not None and (self.nav.currentItem() is None or self.nav.currentItem().isHidden()):self.nav.setCurrentRow(first)

    @staticmethod
    def action_link(caption,callback):
        button=QToolButton(); button.setText(caption); button.setIcon(QIcon.fromTheme('go-next'))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); button.setAutoRaise(True)
        button.clicked.connect(callback)
        return button

    def open_proxy(self):
        self.proxy_window=Proxy(); self.proxy_window.setWindowTitle("Linux BR — Proxy"); self.proxy_window.resize(650,480); self.proxy_window.show()

    def navigate(self, title):
        self.nav.setCurrentRow(next(i for i, page in enumerate(PAGES) if page[0] == title))

    def launch(self, command):
        if not shutil.which(command[0]) or not QProcess.startDetached(command[0], command[1:])[0]:
            QMessageBox.warning(self, 'Ferramenta indisponível', 'Não foi possível iniciar '+command[0]+'. Verifique a instalação do pacote correspondente.')

    def closeEvent(self, event):
        if self.users.process is not None or self.organization.process is not None or self.users.groups.process is not None:
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de contas ou domínio terminar.')
            event.ignore()
        elif self.firewall.process is not None or self.audio.process is not None or self.ip.process is not None:
            QMessageBox.information(self,'Operação em andamento','Aguarde a alteração de sistema terminar.')
            event.ignore()
        elif self.drives.process is not None:
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de armazenamento terminar.')
            event.ignore()
        elif not self.devices.shutdown():
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de pacotes terminar.')
            event.ignore()
        else: event.accept()

if __name__=='__main__':
    application=QApplication(sys.argv)
    application.setDesktopFileName("linuxbr-system")
    window=Central(); window.show()
    if len(sys.argv)==3 and sys.argv[1]=='--page' and sys.argv[2] in (page[0] for page in PAGES):
        window.navigate(sys.argv[2])
    sys.exit(application.exec())
