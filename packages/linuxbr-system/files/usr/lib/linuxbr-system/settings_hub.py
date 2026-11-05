#!/usr/bin/python3
"""Category navigation, configuration search and integrated system pages."""
import argparse
import getpass
import importlib
import os
from pathlib import Path
import subprocess
import sys
from PyQt6.QtCore import Qt,QSize,QProcess
from PyQt6.QtGui import QIcon,QKeySequence,QShortcut
from PyQt6.QtWidgets import QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QStackedWidget,QScrollArea,QPushButton,QMessageBox,QGridLayout
from desktop_jobs import Query,Command
import settings_catalog as catalog


class Window(QMainWindow):
    def __init__(self,page=None):
        from desktop_theme import initialize
        initialize()
        super().__init__();self.setWindowTitle('Linux BR — Configurações');self.setWindowIcon(QIcon.fromTheme('preferences-system'));self.resize(1160,680)
        self.jobs=set();self.cache={};self.history=[];self.current='home';self.capabilities=None;self.pending_page=page;self.dialogs=[]
        main=QWidget();self.setCentralWidget(main);layout=QHBoxLayout(main);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        sidebar=QWidget();sidebar.setFixedWidth(245);side=QVBoxLayout(sidebar);side.setContentsMargins(16,20,16,16)
        brand=QLabel('Configurações');brand.setStyleSheet('font-size:22px;font-weight:600');side.addWidget(brand);user=QLabel(getpass.getuser());user.setTextFormat(Qt.TextFormat.PlainText);side.addWidget(user)
        self.search=QLineEdit();self.search.setPlaceholderText('Localizar uma configuração');self.search.setAccessibleName('Pesquisar configurações');self.search.setClearButtonEnabled(True);side.addWidget(self.search)
        self.navigation=QListWidget();self.navigation.setFrameShape(self.navigation.Shape.NoFrame);self.navigation.setSpacing(2);self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for identifier,title,icon in catalog.CATEGORIES:
            item=QListWidgetItem(QIcon.fromTheme(icon),title);item.setToolTip(title);item.setData(Qt.ItemDataRole.UserRole,identifier);item.setSizeHint(QSize(180,42));self.navigation.addItem(item)
        side.addWidget(self.navigation,1);layout.addWidget(sidebar)
        right=QWidget();body=QVBoxLayout(right);body.setContentsMargins(24,18,24,18);layout.addWidget(right,1)
        trail=QHBoxLayout();self.back=QPushButton(QIcon.fromTheme('go-previous'),'Voltar');self.back.clicked.connect(self.go_back);self.back.setEnabled(False);trail.addWidget(self.back);home=QPushButton('Início');home.clicked.connect(lambda:self.navigate('home'));trail.addWidget(home);self.breadcrumb=QLabel();self.breadcrumb.setTextFormat(Qt.TextFormat.PlainText);trail.addWidget(self.breadcrumb,1);body.addLayout(trail)
        self.summary=QLabel();self.summary.setWordWrap(True);self.summary.setTextFormat(Qt.TextFormat.PlainText);body.addWidget(self.summary)
        self.stack=QStackedWidget();body.addWidget(self.stack,1);self.overview=QScrollArea();self.overview.setWidgetResizable(True);self.overview.setFrameShape(self.overview.Shape.NoFrame);self.stack.addWidget(self.overview)
        self.status=QLabel('Consultando os recursos disponíveis nesta instalação…');self.status.setWordWrap(True);body.addWidget(self.status)
        self.navigation.currentItemChanged.connect(self.category_changed);self.search.textChanged.connect(self.filter);QShortcut(QKeySequence('Alt+Left'),self,activated=self.go_back);QShortcut(QKeySequence('Ctrl+F'),self,activated=self.search.setFocus)
        self.navigation.setCurrentRow(0);self.query(catalog.inventory,self.inventory_loaded)

    def query(self,operation,done):
        task=Query(operation,self);self.jobs.add(task);task.result.connect(done);task.failed.connect(self.status.setText);task.finished.connect(lambda:self.jobs.discard(task));task.finished.connect(task.deleteLater);task.start()

    def inventory_loaded(self,capabilities):
        self.capabilities=capabilities;self.status.setText('Configurações da sua conta e do computador. Alterações administrativas solicitam autorização.')
        self.summary.setText(capabilities.get('summary',''))
        if self.pending_page:
            page=self.pending_page;self.pending_page=None;self.navigate(page)
        else:self.render_category(self.current)

    def category_changed(self,item,*_):
        if item:self.navigate(item.data(Qt.ItemDataRole.UserRole))

    def title(self,identifier):return next((p['title'] for p in catalog.PAGES if p['id']==identifier),next((title for key,title,_ in catalog.CATEGORIES if key==identifier),identifier))

    def navigate(self,identifier,remember=True):
        identifier=catalog.ALIASES.get(identifier,identifier)
        if identifier==self.current and self.stack.currentWidget()!=self.overview:return
        if remember and identifier!=self.current:self.history.append(self.current)
        self.current=identifier;self.back.setEnabled(bool(self.history));self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False)
        category=next((p['category'] for p in catalog.PAGES if p['id']==identifier),identifier)
        self.navigation.blockSignals(True)
        for i in range(self.navigation.count()):
            if self.navigation.item(i).data(Qt.ItemDataRole.UserRole)==category:self.navigation.setCurrentRow(i);break
        self.navigation.blockSignals(False)
        page=next((p for p in catalog.PAGES if p['id']==identifier),None)
        if page:self.open_page(page)
        else:self.render_category(identifier)

    def go_back(self):
        if self.history:self.navigate(self.history.pop(),False)

    def filter(self,query):
        if not query.strip():self.render_category(next((p['category'] for p in catalog.PAGES if p['id']==self.current),self.current));return
        self.render('Resultados da pesquisa',catalog.search(query));self.breadcrumb.setText('Pesquisa › '+query)

    def card(self,page):
        button=QPushButton();button.setAccessibleName(page['title']);button.setAccessibleDescription(page['description']);button.setMinimumHeight(76);button.setStyleSheet('QPushButton { text-align:left;border:1px solid palette(mid);border-radius:8px;background:palette(base); } QPushButton:hover { border-color:palette(highlight); } QPushButton:focus { border:2px solid palette(highlight); }')
        body=QHBoxLayout(button);body.setContentsMargins(16,10,16,10);icon=QLabel();icon.setPixmap(QIcon.fromTheme(page['icon'],QIcon.fromTheme('preferences-system')).pixmap(28,28));body.addWidget(icon)
        column=QVBoxLayout();name=QLabel(page['title']);name.setTextFormat(Qt.TextFormat.PlainText);name.setStyleSheet('font-weight:600;font-size:15px');description=QLabel(page['description']);description.setWordWrap(True);description.setTextFormat(Qt.TextFormat.PlainText);column.addWidget(name);column.addWidget(description);body.addLayout(column,1);arrow=QLabel('›');arrow.setStyleSheet('font-size:24px');body.addWidget(arrow)
        for child in button.findChildren(QWidget):child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if self.capabilities is not None:
            enabled,reason=catalog.available(page,self.capabilities);button.setEnabled(enabled)
            if not enabled:description.setText(page['description']+' · '+reason);button.setToolTip(reason)
        button.clicked.connect(lambda:self.navigate(page['id']));return button

    def render(self,title,pages):
        widget=QWidget();body=QVBoxLayout(widget);body.setContentsMargins(4,14,4,14);body.setSpacing(10);heading=QLabel(title);heading.setStyleSheet('font-size:28px;font-weight:600');body.addWidget(heading)
        for page in pages:body.addWidget(self.card(page))
        if not pages:
            label=QLabel('Nenhuma configuração encontrada. Tente tela, som, senha, impressora, IP, programas ou restauração.');label.setWordWrap(True);body.addWidget(label)
        body.addStretch();old=self.overview.takeWidget();self.overview.setWidget(widget)
        if old:old.deleteLater()
        self.stack.setCurrentWidget(self.overview)

    def render_category(self,identifier):
        if identifier=='home':
            promoted=['display','sound','connections','installed','virtualization','updates','recovery']
            self.render('Bem-vindo às Configurações',[p for p in catalog.PAGES if p['id'] in promoted]);self.breadcrumb.setText('Início');return
        self.render(self.title(identifier),catalog.search(category=identifier));self.breadcrumb.setText(self.title(identifier))

    def launch(self,argv):
        if argv and argv[0]=='linuxbr-system' and len(argv)>=3 and argv[1]=='--page':self.navigate(argv[2]);return
        if not QProcess.startDetached(argv[0],argv[1:])[0]:QMessageBox.warning(self,'Não foi possível abrir','A ferramenta não está disponível nesta instalação. Confira a Loja Linux BR.')

    def open_page(self,page):
        category=self.title(page['category']);self.breadcrumb.setText(category+' › '+page['title']);kind,target,*args=page['route']
        if self.capabilities is not None:
            enabled,reason=catalog.available(page,self.capabilities)
            if not enabled:QMessageBox.information(self,'Recurso indisponível',reason);self.render_category(page['category']);return
        if kind in ('kcm','app'):
            self.render(page['title'],[page]);self.launch(['/usr/bin/kcmshell6',target] if kind=='kcm' else [target,*args]);return
        if page['id'] not in self.cache:
            try:widget=self.make_page(kind,target,args)
            except Exception as error:QMessageBox.warning(self,'Página não disponível',str(error));self.render_category(page['category']);return
            self.stack.addWidget(widget);self.cache[page['id']]=widget
        self.stack.setCurrentWidget(self.cache[page['id']])

    def make_page(self,kind,target,args=None):
        if target=='Recursos opcionais':
            from features_page import Features
            return Features()
        if target=='Programas de inicialização':
            from startup_page import Startup
            return Startup()
        if target=='Detalhes da conexão':
            from network_details_page import NetworkDetails
            return NetworkDetails()
        if kind=='tool':
            if target=='administration':
                from administration import Administration
                page=Administration(self)
                if args:page.tabs.setCurrentIndex(int(args[0]))
                return page
            from settings_tools import Clipboard,Permissions
            return {'clipboard':Clipboard,'permissions':Permissions}[target](self)
        simple={'Telas':('display_page','Displays'),'Áudio':('audio','Audio'),'Energia e bateria':('power_page','Power'),'Acesso remoto':('remote_page','RemoteAccess'),'Proxy':('proxy','Proxy'),'Firewall':('firewall','Firewall'),'Endereços IP e DNS':('network_page','IPPage'),'Personalização':('appearance','Appearance'),'Cuidados com o computador':('maintenance','MaintenancePage')}
        if target in simple:
            module,cls=simple[target];return getattr(importlib.import_module(module),cls)()
        if target=='Sistema':
            from about import About
            return About(self.launch,self.navigate)
        if target in ('Usuários','Organização'):
            from accounts import AccountsPage
            return AccountsPage(target=='Organização',self.launch)
        if target in ('Backup e recuperação','Atualizações'):
            from recovery import RecoveryPage
            return RecoveryPage('updates' if target=='Atualizações' else 'backup')
        if target=='Armazenamento':
            sys.path.insert(0,'/usr/lib/linuxbr-drive-manager');from app import Window as Drives
            return Drives()
        if target=='Dispositivos':
            sys.path.insert(0,'/usr/lib/linuxbr-device-manager');from devices import Devices
            return Devices()
        if target=='Arquivos e atalhos':
            widget=QWidget();layout=QVBoxLayout(widget)
            for title,icon,command in [('Mapear unidade de rede','folder-network',['linuxbr-file-tools','--map-network']),('Trazer arquivos do Windows','folder-download',['linuxbr-migration']),('Este computador','computer',['dolphin','linuxbr:/']),('Ferramentas de arquivos','system-file-manager',['linuxbr-file-tools'])]:
                button=QPushButton(QIcon.fromTheme(icon),title);button.clicked.connect(lambda _=False,argv=command:self.launch(argv));layout.addWidget(button)
            layout.addStretch();return widget
        raise ValueError('Configuração não encontrada.')

    def closeEvent(self,event):
        from PyQt6 import sip
        widgets=list(self.cache.values());running=bool(self.jobs)
        for widget in widgets:
            running=running or bool(getattr(widget,'jobs',set()))
            for dialog in getattr(widget,'commands',[]):
                if not sip.isdeleted(dialog) and dialog.process.state()!=QProcess.ProcessState.NotRunning:running=True
            process=getattr(widget,'process',None)
            if process is not None:running=True
        if running:event.ignore();QMessageBox.information(self,'Operação em andamento','Aguarde a alteração ou consulta concluir antes de fechar.');return
        for widget in widgets:
            if hasattr(widget,'stop_update_query'):widget.stop_update_query()
            if hasattr(widget,'shutdown') and not widget.shutdown():event.ignore();return
        super().closeEvent(event)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--page');args=parser.parse_args();app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-system');window=Window(args.page);window.show();sys.exit(app.exec())
