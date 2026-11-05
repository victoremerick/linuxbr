#!/usr/bin/python3
"""System hub: existing KDE tools and the shared Linux BR storage interface."""
import shutil
import sys
sys.path.insert(0, '/usr/lib/linuxbr-drive-manager')
sys.path.insert(0, '/usr/lib/linuxbr-device-manager')
from PyQt6.QtCore import QProcess, QSize, Qt
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                            QListWidget, QListWidgetItem, QStackedWidget, QLabel, QPushButton, QMessageBox, QToolButton, QScrollArea, QFrame, QLineEdit, QSizePolicy)
from app import Window as Drives
from devices import Devices
from about import About
from accounts import AccountsPage
from appearance import Appearance
from proxy import Proxy
from firewall import Firewall
from network_page import IPPage
from audio import Audio
from display_page import Displays
from remote_page import RemoteAccess
from power_page import Power
from visual_style import BUTTONS
from welcome import HelpPage
from recovery import RecoveryPage
from daily_use import DailyUse
from desktopflows08 import DesktopFlowsPage, PathButton
from maintenance import MaintenancePage
from function_icons import FUNCTION_ICONS

PAGES = [
 ('Sistema', '', []),
 ('Dispositivos', 'Hardware, periféricos e conexões locais.', [
     ('Informações e dispositivos', ['kinfocenter']),
     ('Bluetooth', ['kcmshell6', 'kcm_bluetooth']),
     ('Áudio e headsets', ['kcmshell6', 'kcm_pulseaudio']),
     ('Celulares', ['kdeconnect-settings']),
     ('Impressoras', ['kcmshell6', 'kcm_printer_manager']),
     ('Digitalizar documentos', ['skanpage'])]),
 ('Armazenamento', '', []),
 ('Rede', 'Conexões, Wi-Fi, VPN e unidades de rede.', [
     ('Wi-Fi e Ethernet', ['kcmshell6', 'kcm_networkmanagement']),
     ('VPN', ['kcmshell6', 'kcm_networkmanagement']),
     ('Mapear unidade de rede', ['linuxbr-file-tools', '--map-network']),
     
     ('Bluetooth', ['kcmshell6', 'kcm_bluetooth'])]),
 ('Usuários', 'Contas locais e configurações de acesso.', [
     ('Gerenciar usuários', ['kcmshell6', 'kcm_users'])]),
 ('Organização', '', []),
 ('Administração', 'Ferramentas de manutenção do sistema.', [
     ('Aplicativos e atualizações', ['linuxbr-store']),
     ('Firmware de dispositivos', ['linuxbr-store','--firmware']),
     ('Analisar espaço ocupado', ['filelight']),
     ('Executar um programa', ['linuxbr-run']),
     ('Aplicativos na inicialização', ['linuxbr-desktop-flows', '--page', 'startup']),
     ('Logs desta inicialização', ['konsole', '-e', 'journalctl', '-b', '--pager-end']),
     ('Estado dos serviços', ['konsole', '-e', 'systemctl', 'status']),
     ('Configurações do terminal', ['linuxbr-terminal-settings']),
     ('Configurações avançadas', ['systemsettings'])]),
 ('Programas', 'Instale, remova e atualize aplicativos.', [
     ('Loja de aplicativos', ['linuxbr-store']),
     ('Instalar a partir de arquivo', ['linuxbr-install-package']),
     ('Programas Windows e jogos', ['linuxbr-windows']),
     ('Aplicativos web', ['linuxbr-webapps']),
     ('Programas instalados', ['linuxbr-store', '--installed']),
     ('Encontrar programas', ['linuxbr-store']),
     ('Atualizações', ['linuxbr-store','--updates'])]),
 ('Telas', 'Monitores, resolução, escala, orientação e disposição das telas.', []),
 ('Personalização', '', []),
 ('Acesso remoto', 'Permita conexões RDP ou VNC à sessão deste computador.', []),
 ('Energia e bateria', 'Tempo de tela, suspensão, tampa e botão de energia.', []),
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
 ('Uso diário', 'Pendrives, NTFS, pastas Windows, impressoras, Bluetooth e aplicativos padrão.', []),
 ('Arquivos e atalhos', 'Crie atalhos, mapeie unidades de rede e organize documentos.', [
     ('Trazer meus arquivos do Windows', ['linuxbr-migration']),
     ('Ferramentas de arquivos', ['linuxbr-file-tools']),
     ('Mapear unidade de rede', ['linuxbr-file-tools', '--map-network']),
     ('Este computador', ['dolphin', 'linuxbr:/']),
     ('Lixeira', ['dolphin', 'trash:/']),
     ('Arquivos compactados', ['ark']),
     ('Analisar espaço ocupado', ['filelight']),
     ('Cópias e conflitos de arquivos', ['linuxbr-desktop-flows', '--page', 'transfers'])]),
 ('Cuidados com o computador', 'Proteção, backup, condições para atualizar, diagnóstico e limpeza revisada.', []),
 ('Aplicativos web', 'Sites instalados como aplicativos, com janela própria no Chromium.', [
     ('Gerenciar aplicativos web', ['linuxbr-webapps']),
     ('Abrir Chromium', ['chromium'])]),
 ('Firewall', 'Proteção de rede, portas liberadas e aplicativos com portas abertas.', []),
 ('Áudio', 'Alto-falantes, microfones, perfis e mixer por aplicativo.', []),
 ('Endereços IP e DNS', 'Propriedades IPv4 e IPv6 das conexões de rede.', []),
 ('Proxy', 'Proxy manual ou PAC para aplicativos KDE.', []),
 ('Primeiros passos', 'Ajuda, guia para quem vem do Windows, menu Iniciar e uso diário.', []),
 ('Recuperação e ajuda', 'Suporte, cópia de segurança, backup, falhas e reparação da inicialização.', []),
 ('Backup e recuperação', 'Cópias de segurança, restauração de arquivos e suporte.', []),
 ('Atualizações', 'Atualizações do sistema, aplicativos e firmware.', []),
 ('Programas Windows e jogos', 'Compatibilidade com EXE, MSI, Wine, Steam, Proton e Bottles.', [
     ('Abrir central de compatibilidade', ['linuxbr-windows']),
     ('Meus programas Windows', ['linuxbr-windows', '--page', 'library']),
     ('Instalar programa Windows', ['linuxbr-windows', '--page', 'install']),
     ('Jogos e controles', ['linuxbr-windows', '--page', 'games']),
     ('Abrir Steam', ['steam'])]),
]

SEARCH_ALIASES = {
 'Cuidados com o computador': 'limpar cache lixeira espaço backup proteção certificado atualização resolver problema som impressão rede reparação diagnóstico',
 'Backup e recuperação': 'backup cópia segurança restaurar histórico arquivos recuperar pendrive disco externo kup ponto restauração sistema timeshift voltar',
 'Atualizações': 'windows update atualizar segurança firmware driver versão discover',
 'Administração': 'gerenciador de tarefas taskmgr processos cpu memória desempenho ctrl shift esc',
 'Arquivos e atalhos': 'explorer explorador atalho desktop área trabalho lixeira rede compartilhamento unc smb zip copiar caminho',
 'Aplicativos web': 'chromium navegador site pwa webapp whatsapp teams canva instalar internet',
 'Sistema': 'painel de controle configurações computador versão memória processador',
 'Programas Windows e jogos': 'exe msi wine steam proton bottles directx vulkan jogos games aplicativos windows',
 'Rede': 'wifi wi-fi internet conexão cabo ethernet vpn',
 'Programas': 'loja instalar desinstalar remover aplicativos microsoft store windows update atualizar',
 'Armazenamento': 'disco pendrive usb unidade partição formatar letras c: d: compartilhamento',
 'Áudio': 'som volume microfone fone alto-falante headset',
 'Telas': 'monitor resolução escala brilho imagem texto tamanho',
 'Dispositivos': 'driver impressora scanner bluetooth hardware',
 'Pesquisa e padrões': 'abrir com navegador padrão pdf pastas procurar arquivos',
 'Recuperação e ajuda': 'não inicia erro falha backup restaurar reparo suporte ajuda',
}

class Central(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(BUTTONS)
        self.setWindowTitle('Linux BR — Central do Sistema')
        self.setWindowIcon(QIcon.fromTheme('preferences-system'))
        self.resize(1260, 720)
        self.setMinimumSize(900, 560)
        root=QWidget(); self.setCentralWidget(root)
        layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar=QWidget(); sidebar.setFixedWidth(224)
        side=QVBoxLayout(sidebar); side.setContentsMargins(12,20,12,16); side.setSpacing(16)
        brand=QLabel('Linux BR'); brand.setStyleSheet('font-size:18px; font-weight:600; padding-left:12px')
        side.addWidget(brand)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar configuração…');self.search.setClearButtonEnabled(True);side.addWidget(self.search)
        self.search.setAccessibleName('Buscar configurações e ferramentas')
        self.search_status=QLabel();self.search_status.setWordWrap(True);self.search_status.hide();side.addWidget(self.search_status)
        self.find_shortcut=QShortcut(QKeySequence.StandardKey.Find,self)
        self.find_shortcut.activated.connect(self.search.setFocus)
        self.clear_shortcut=QShortcut(QKeySequence('Esc'),self)
        self.clear_shortcut.activated.connect(self.search.clear)
        self.nav=QListWidget(); self.nav.setSpacing(2); self.nav.setIconSize(QSize(18,18))
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        content=QWidget(); column=QVBoxLayout(content); column.setContentsMargins(0,0,0,0)
        trail=QHBoxLayout(); trail.setContentsMargins(24,14,24,4)
        self.back=PathButton(); self.back.setIcon(QIcon.fromTheme('go-previous'))
        self.back.setToolTip('Voltar (Alt+Esquerda)'); self.back.setAccessibleName('Voltar à configuração anterior')
        self.back.setEnabled(False); self.back.clicked.connect(self.go_back); trail.addWidget(self.back)
        self.home=PathButton(); self.home.setText('Configurações'); self.home.setAutoRaise(True)
        self.home.clicked.connect(lambda:self.navigate('Sistema')); trail.addWidget(self.home)
        trail.addWidget(QLabel('›')); self.breadcrumb=QLabel(); self.breadcrumb.setTextFormat(Qt.TextFormat.PlainText)
        self.breadcrumb.setAccessibleName('Página atual'); trail.addWidget(self.breadcrumb,1)
        column.addLayout(trail); column.addWidget(self.stack,1)
        self.navigation_history=[]; self.returning=False
        self.back_shortcut=QShortcut(QKeySequence('Alt+Left'),self); self.back_shortcut.activated.connect(self.go_back)
        layout.addWidget(sidebar); layout.addWidget(content,1)
        self.drives=Drives(); self.devices=Devices()
        self.firewall=Firewall();self.audio=Audio();self.ip=IPPage()
        self.displays=Displays();self.remote=RemoteAccess();self.proxy=Proxy();self.power=Power()
        self.users=AccountsPage(False,self.launch); self.organization=AccountsPage(True,self.launch)
        for index,(title,description,actions) in enumerate(PAGES):
            item=QListWidgetItem(QIcon.fromTheme(FUNCTION_ICONS[title]),title); item.setToolTip(title); item.setSizeHint(QSize(170,38)); self.nav.addItem(item)
            if title=='Sistema':
                page=About(self.launch,self.navigate)
            elif title=='Personalização':
                page=Appearance()
            elif title=='Usuários':
                page=self.users
            elif title=='Organização':
                page=self.organization
            elif title=='Telas':
                page=self.displays
            elif title=='Acesso remoto':
                page=self.remote
            elif title=='Energia e bateria':
                page=self.power
            elif title in ('Primeiros passos','Recuperação e ajuda'):
                page=HelpPage(self.launch,title)
            elif title in ('Backup e recuperação','Atualizações'):
                page=RecoveryPage('updates' if title=='Atualizações' else 'backup')
            elif title in ('Firewall','Áudio','Endereços IP e DNS','Proxy'):
                page={'Firewall':self.firewall,
                      'Áudio':self.audio,'Endereços IP e DNS':self.ip,'Proxy':self.proxy}[title]
            elif title=='Uso diário':
                page=DailyUse()
            elif title=='Pesquisa e padrões':
                page=DesktopFlowsPage('search')
                page.back_shortcut.setEnabled(False)
            elif title=='Cuidados com o computador':
                self.maintenance=MaintenancePage()
                page=self.maintenance
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
                    body.addWidget(self.action_link(caption,lambda checked=False,cmd=command:self.launch(cmd)))
                if title=='Rede':
                    body.addWidget(self.action_link('Endereços IP e DNS',lambda:self.navigate('Endereços IP e DNS')),0,Qt.AlignmentFlag.AlignLeft)
                    body.addWidget(self.action_link('Configurar proxy',self.open_proxy),0,Qt.AlignmentFlag.AlignLeft)
                    body.addWidget(self.action_link('Compartilhamentos e letras de rede',lambda:self.navigate('Armazenamento')),0,Qt.AlignmentFlag.AlignLeft)
                if title=='Administração':
                    body.addWidget(self.action_link('Firewall',lambda:self.navigate('Firewall')),0,Qt.AlignmentFlag.AlignLeft)
                    body.addWidget(self.action_link('Gerenciador de Tarefas',lambda:self.launch(['linuxbr-task-manager'])),0,Qt.AlignmentFlag.AlignLeft)
                body.addStretch()
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.select_page)
        self.search.textChanged.connect(self.filter_pages)
        self.navigate('Sistema')

    def filter_pages(self,text):
        import unicodedata
        def normalized(value):
            return ''.join(c for c in unicodedata.normalize('NFD',value.casefold()) if not unicodedata.combining(c))
        query=normalized(text.strip());first=None
        for i,(title,description,actions) in enumerate(PAGES):
            haystack=normalized(' '.join([title,description,SEARCH_ALIASES.get(title,'')]+[a[0] for a in actions]))
            visible=all(word in haystack for word in query.split())
            self.nav.item(i).setHidden(not visible)
            if visible and first is None:first=i
        if first is not None and (self.nav.currentItem() is None or self.nav.currentItem().isHidden()):self.nav.setCurrentRow(first)
        self.stack.setVisible(first is not None)
        self.search_status.setText('Nenhuma configuração encontrada. Tente palavras como rede, som, tela ou programas.' if first is None else '')
        self.search_status.setVisible(first is None)

    @staticmethod
    def action_link(caption,callback):
        button=PathButton(); button.setText(caption); button.setIcon(QIcon.fromTheme(FUNCTION_ICONS[caption]))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); button.setAutoRaise(False)
        button.setMinimumHeight(44); button.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        button.setStyleSheet('QToolButton { text-align:left; padding:10px 12px; border:1px solid palette(mid); border-radius:5px; } QToolButton:focus { border:2px solid palette(highlight); }')
        button.clicked.connect(callback)
        return button

    def select_page(self,index):
        if index < 0: return
        previous=self.stack.currentIndex()
        if previous != index and not self.returning:
            self.navigation_history.append(previous)
        self.stack.setCurrentIndex(index); self.breadcrumb.setText(PAGES[index][0])
        self.back.setEnabled(bool(self.navigation_history))

    def go_back(self):
        page=self.stack.currentWidget()
        if isinstance(page,DesktopFlowsPage) and page.history:
            page.go_back(); return
        if not self.navigation_history: return
        index=self.navigation_history.pop(); self.returning=True
        try:
            if self.nav.item(index).isHidden(): self.search.clear()
            self.nav.setCurrentRow(index)
        finally:
            self.returning=False; self.back.setEnabled(bool(self.navigation_history))

    def open_proxy(self):
        self.navigate('Proxy')

    def navigate(self, title):
        self.nav.setCurrentRow(next(i for i, page in enumerate(PAGES) if page[0] == title))

    def launch(self, command):
        if not shutil.which(command[0]) or not QProcess.startDetached(command[0], command[1:])[0]:
            QMessageBox.warning(self, 'Ferramenta indisponível', 'Não foi possível iniciar '+command[0]+'. Verifique a instalação do pacote correspondente.')

    def closeEvent(self, event):
        if getattr(self, 'maintenance', None) is not None and self.maintenance.jobs:
            for job in self.maintenance.jobs:
                job.cancel.set()
            QMessageBox.information(self,'Operação em andamento','Aguarde a consulta ou limpeza terminar. O cancelamento foi solicitado.')
            event.ignore()
        elif self.users.process is not None or self.organization.process is not None or self.users.groups.process is not None:
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de contas ou domínio terminar.')
            event.ignore()
        elif self.firewall.process is not None or self.audio.process is not None or self.ip.process is not None or self.remote.process is not None:
            QMessageBox.information(self,'Operação em andamento','Aguarde a alteração de sistema terminar.')
            event.ignore()
        elif self.drives.process is not None:
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de armazenamento terminar.')
            event.ignore()
        elif not self.devices.shutdown():
            QMessageBox.information(self,'Operação em andamento','Aguarde a operação de pacotes terminar.')
            event.ignore()
        else:
            for page in self.findChildren(RecoveryPage):
                page.stop_update_query()
            event.accept()

if __name__=='__main__':
    application=QApplication(sys.argv)
    if sys.argv[1:]==['--page','Gerenciador de tarefas']:
        sys.exit(0 if QProcess.startDetached('linuxbr-task-manager',[])[0] else 1)
    application.setDesktopFileName("linuxbr-system")
    window=Central(); window.show()
    if len(sys.argv)==3 and sys.argv[1]=='--page' and sys.argv[2] in (page[0] for page in PAGES):
        window.navigate(sys.argv[2])
    sys.exit(application.exec())
