#!/usr/bin/python3
"""Application storefront with library, source management and native operations."""
import argparse
import json
import os
from pathlib import Path
import sys
from PyQt6.QtCore import Qt,QSize,QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,
    QListWidgetItem,QStackedWidget,QSplitter,QPushButton,QCheckBox,QFormLayout,QMessageBox,QStyledItemDelegate,QStyleOptionViewItem,QStyle)
from store import Window as OperationsWindow
import store_backend as backend
import catalog_sources
import store_repository
from store_source_page import Sources
from desktop_jobs import Query,Command
from firmware_page import Firmware


def category_icon(name):
    return {'Imagem e criação':'applications-graphics','Internet e comunicação':'applications-internet','Jogos':'applications-games','Música e vídeo':'applications-multimedia','Escritório':'applications-office','Produtividade':'applications-office','Utilitários':'applications-utilities','Desenvolvimento':'applications-development','Educação':'applications-education','Sistema':'applications-system'}.get(name,'applications-other')


class CardDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        style=QStyleOptionViewItem(option);self.initStyleOption(style,index);style.icon=QIcon();style.text=''
        (style.widget.style() if style.widget else QApplication.style()).drawControl(QStyle.ControlElement.CE_ItemViewItem,style,painter,style.widget)


class Window(OperationsWindow):
    def __init__(self):
        from desktop_theme import initialize
        initialize()
        self.ready=False;self.queries=set();self.repository_cache={};self.requested=set();self.only_favorites=False;self.dialogs=[];self.metadata_cache={};self.metadata_requested=set()
        self.preferences_path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'linuxbr/store.json'
        try:self.preferences=json.loads(self.preferences_path.read_text())
        except (OSError,ValueError):self.preferences={}
        if not isinstance(self.preferences,dict):self.preferences={}
        self.favorites={v for v in self.preferences.get('favorites',[]) if isinstance(v,str)} if isinstance(self.preferences.get('favorites',[]),list) else set();super().__init__()
        self.base_entries=self.entries+catalog_sources.entries();self.entries=self.base_entries;self.resize(1180,680)
        for category in sorted({item['category'] for item in self.base_entries}):
            if self.category.findData(category)<0:self.category.addItem(category,category)
        self.search_timer=QTimer(self);self.search_timer.setSingleShot(True);self.search_timer.setInterval(450);self.search_timer.timeout.connect(self.start_repository_search)
        old=self.takeCentralWidget();splitter=old.findChild(QSplitter);main=QWidget();self.setCentralWidget(main);layout=QHBoxLayout(main);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        side=QWidget();side.setFixedWidth(196);column=QVBoxLayout(side);column.setContentsMargins(12,22,12,16)
        brand=QLabel('Loja Linux BR');brand.setStyleSheet('font-size:20px;font-weight:700;padding:8px 6px');column.addWidget(brand)
        self.navigation=QListWidget();self.navigation.setFrameShape(self.navigation.Shape.NoFrame);self.navigation.setSpacing(4);self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.navigation.setWordWrap(True);self.navigation.setTextElideMode(Qt.TextElideMode.ElideNone);column.addWidget(self.navigation,1);layout.addWidget(side)
        right=QWidget();body=QVBoxLayout(right);body.setContentsMargins(24,20,24,16);body.setSpacing(12);layout.addWidget(right,1)
        self.hero=QLabel('Encontre seu próximo aplicativo\nProgramas Linux, sites com janela própria e opções para Windows.');self.hero.setWordWrap(True);self.hero.setMinimumHeight(96);self.hero.setStyleSheet('font-size:19px;font-weight:600;padding:20px;border-radius:12px;color:white;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #095ba7,stop:1 #267d94);');body.addWidget(self.hero)
        filters=QHBoxLayout();self.query.setPlaceholderText('Pesquisar aplicativos, sites e programas…');self.query.setMinimumHeight(38);filters.addWidget(self.query,1);filters.addWidget(self.kind);filters.addWidget(self.category);body.addLayout(filters)
        self.view.setParent(main);self.view.hide();self.pages=QStackedWidget();body.addWidget(self.pages,1);self.pages.addWidget(splitter);splitter.setSizes([540,350])
        self.results.setViewMode(self.results.ViewMode.IconMode);self.results.setResizeMode(self.results.ResizeMode.Adjust);self.results.setMovement(self.results.Movement.Static);self.results.setWrapping(True);self.results.setSpacing(10);self.results.setGridSize(QSize(238,158));self.results.setMinimumWidth(270)
        self.results.setItemDelegate(CardDelegate(self.results))
        self.results.setStyleSheet('QListWidget { border:0;background:transparent; } QListWidget::item { border:1px solid palette(mid);border-radius:10px;background:palette(base); } QListWidget::item:selected { border:2px solid palette(highlight);background:palette(alternate-base); }')
        self.favorite=QPushButton(QIcon.fromTheme('rating'),'Adicionar aos favoritos');self.favorite.clicked.connect(self.toggle_favorite);self.detail_layout.insertWidget(0,self.favorite)
        self.license_button=QPushButton(QIcon.fromTheme('text-x-generic'),'Ler licenças do pacote');self.license_button.clicked.connect(self.show_license);self.detail_layout.insertWidget(self.detail_layout.count()-1,self.license_button)
        detail_area=splitter.widget(1);panel=QWidget();splitter.replaceWidget(1,panel);detail=QVBoxLayout(panel);detail.setContentsMargins(8,4,0,0);detail.setSpacing(10)
        for widget in (self.heading,self.primary,self.manage_native,self.manage_windows,self.new_session,self.installer):
            self.detail_layout.removeWidget(widget);detail.addWidget(widget)
        self.primary.setMinimumHeight(38);self.primary.setStyleSheet('QPushButton { background:palette(highlight);color:palette(highlighted-text);border:0;border-radius:6px;padding:8px; } QPushButton:disabled { background:palette(mid); }')
        detail.addWidget(detail_area,1)
        self.sources=Sources(self);self.pages.addWidget(self.sources)
        preferences=QWidget();form=QFormLayout(preferences);self.compact=QCheckBox('Usar cartões compactos');self.compact.setChecked(bool(self.preferences.get('compact')));self.compact.toggled.connect(self.save_preferences);form.addRow(QLabel('Preferências da Loja'));form.addRow(self.compact)
        note=QLabel('Instalações e atualizações são confirmadas pelos gerenciadores nativos. Os programas Windows usam o site oficial e o ambiente escolhido. Sites mantêm contas em perfis separados do Chromium.');note.setWordWrap(True);form.addRow(note);self.pages.addWidget(preferences)
        self.firmware_page=Firmware(self);self.pages.addWidget(self.firmware_page)
        from webapp_updates import WebUpdates
        self.web_updates=WebUpdates(self);self.pages.addWidget(self.web_updates)
        footer=QHBoxLayout();footer.addWidget(self.count,1);refresh=QPushButton(QIcon.fromTheme('view-refresh'),'Atualizar catálogo');refresh.clicked.connect(self.reload_catalog);footer.addWidget(refresh);body.addLayout(footer)
        self.links={}
        for caption,icon,data in [('Início','go-home',('catalog','')),('Biblioteca','applications-all',('installed','')),('Favoritos','rating',('favorites','')),('Downloads e histórico','folder-download',('downloads','')),('Atualizações','system-software-update',('updates','')),('Revisões de webapps','internet-web-browser',('web-updates','')),('Firmware','preferences-devices-cpu',('firmware','')),('Fontes','network-server',('sources','')),('Configurações','configure',('preferences',''))]:self.nav_item(caption,icon,data)
        for category in sorted({item['category'] for item in self.base_entries}):self.nav_item(category,category_icon(category),('category',category))
        self.navigation.currentItemChanged.connect(self.navigate);old.deleteLater();self.ready=True;self.navigation.setCurrentRow(0);self.refresh()

    def nav_item(self,caption,icon,data):
        item=QListWidgetItem(QIcon.fromTheme(icon),caption);item.setToolTip(caption);item.setData(Qt.ItemDataRole.UserRole,data);item.setSizeHint(QSize(150,50 if len(caption)>20 else 42));self.navigation.addItem(item);self.links[data[0]+':'+data[1]]=item

    def navigate(self,item,*_):
        if not item:return
        key,category=item.data(Qt.ItemDataRole.UserRole);self.only_favorites=key=='favorites'
        if key in ('sources','preferences','firmware','web-updates'):
            self.pages.setCurrentIndex({'sources':1,'preferences':2,'firmware':3,'web-updates':4}[key]);self.hero.setText(item.text());self.query.setEnabled(False);self.kind.setEnabled(False);self.category.setEnabled(False)
            if key=='sources':self.sources.refresh()
            if key=='web-updates':self.web_updates.refresh()
            return
        self.pages.setCurrentIndex(0);self.query.setEnabled(True);self.kind.setEnabled(True);self.category.setEnabled(True);self.view.setCurrentIndex(1 if key=='installed' else 0)
        self.category.setCurrentIndex(max(0,self.category.findData(category)));self.hero.setText({'installed':'Sua biblioteca\nAplicativos deste computador, programas Windows e perfis web.', 'favorites':'Seus favoritos\nAcesse os aplicativos que você marcou.'}.get(key,'Encontre seu próximo aplicativo\nEscolha uma categoria ou pesquise nas fontes configuradas.'))
        if key in ('updates','downloads'):
            self.open_updates() if key=='updates' else self.downloads()
        self.refresh()

    def refresh(self):
        if not getattr(self,'ready',False):return super().refresh()
        query=self.query.text().strip();extra=self.repository_cache.get(query,[])
        self.entries=self.base_entries+extra
        if self.only_favorites:self.entries=[entry for entry in self.entries if entry['id'] in self.favorites]
        super().refresh();self.count.setText(str(self.results.count())+' resultados'+(' · consultando fontes…' if query in self.requested else ''))
        for index in range(self.results.count()):
            item=self.results.item(index);entry=item.data(Qt.ItemDataRole.UserRole);item.setData(Qt.ItemDataRole.AccessibleTextRole,entry['name']);card=QWidget();card.setAccessibleName(entry['name']);card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);card.setStyleSheet('background:transparent;');body=QVBoxLayout(card);body.setContentsMargins(16,12,16,10);header=QHBoxLayout();icon=QLabel();icon.setPixmap(item.icon().pixmap(40,40));icon.setObjectName('appIcon');header.addWidget(icon);header.addStretch();badge=QLabel({'linux':'Linux','web':'Web','windows':'Windows'}[entry['kind']]);badge.setStyleSheet('font-size:11px;color:palette(mid);');header.addWidget(badge);body.addLayout(header)
            name=QLabel(entry['name']);name.setTextFormat(Qt.TextFormat.PlainText);name.setWordWrap(True);name.setStyleSheet('font-weight:600;font-size:14px;');body.addWidget(name);label=QLabel(entry['category']);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True);label.setStyleSheet('font-size:11px;');body.addWidget(label);body.addStretch();item.setSizeHint(QSize(228,132 if self.compact.isChecked() else 148));item.setToolTip(entry['name']+'\n'+entry['description']);self.results.setItemWidget(item,card)
        self.results.setGridSize(QSize(238,142 if self.compact.isChecked() else 158))
        if 2<=len(query)<=100 and self.view.currentData()!='installed' and not self.only_favorites and query not in self.repository_cache and query not in self.requested:self.search_timer.start()

    def start_repository_search(self):
        query=self.query.text().strip()
        if len(self.queries)>=2:self.search_timer.start();return
        if query in self.requested or query in self.repository_cache or len(query)<2:return
        self.requested.add(query);task=Query(lambda:store_repository.search(query),self);self.queries.add(task)
        def loaded(rows):
            self.repository_cache[query]=rows;self.requested.discard(query)
            if self.query.text().strip()==query:self.refresh()
        task.result.connect(loaded);task.failed.connect(lambda _:loaded([]));task.finished.connect(lambda:self.queries.discard(task));task.finished.connect(task.deleteLater);task.start()

    def select(self,*args):
        super().select(*args)
        if not getattr(self,'ready',False):return
        item=self.selected();self.favorite.setVisible(bool(item));self.favorite.setText('Remover dos favoritos' if item and item['id'] in self.favorites else 'Adicionar aos favoritos')
        self.note.setText(self.note.text().replace('O Discover oferece outras fontes e pacotes.','Consulte as fontes configuradas na Loja.'))
        self.metadata.setText(self.metadata.text().replace('ou o Discover','na origem da instalação'))
        details=self.metadata_cache.get(item['id'],{}) if item else {};self.license_button.setVisible(bool(details.get('copyright_file')))
        if details:self.show_metadata(details)
        if not item:self.description.setText('Tente outro nome, finalidade ou categoria. Para pesquisar nas fontes, digite pelo menos dois caracteres.')

    def metadata_for(self,item):
        identifier=item['id'];basic=dict(type=backend.KINDS[item['kind']],origin=item.get('source','Não informada'),version='Consultando metadados locais…',size='Consultando metadados locais…')
        if identifier in self.metadata_cache:return self.metadata_cache[identifier]
        if self.ready and identifier not in self.metadata_requested:
            self.metadata_requested.add(identifier);task=Query(lambda:backend.package_metadata(item),self);self.queries.add(task)
            def loaded(value):
                self.metadata_cache[identifier]=value;self.metadata_requested.discard(identifier)
                current=self.selected()
                if current and current['id']==identifier:self.show_metadata(value)
            task.result.connect(loaded);task.failed.connect(lambda _:loaded(dict(basic,version='Metadados não disponíveis.',size='Não informado.')));task.finished.connect(lambda:self.queries.discard(task));task.finished.connect(task.deleteLater);task.start()
        return basic

    def show_metadata(self,details):
        self.metadata.setText('\n'.join(label+': '+details.get(key,'Não informado.') for key,label in [('type','Tipo'),('origin','Origem'),('version','Versão'),('size','Tamanho'),('publisher','Fornecedor / mantenedor'),('license','Licença')]))
        self.license_button.setVisible(bool(details.get('copyright_file')))

    def show_license(self):
        from PyQt6.QtWidgets import QDialog,QPlainTextEdit,QDialogButtonBox
        item=self.selected();path=self.metadata_cache.get(item['id'],{}).get('copyright_file') if item else None
        if not path:return
        try:
            if not Path(path).is_relative_to('/usr/share/doc'):raise ValueError('Caminho de licença inválido.')
            with Path(path).open(encoding='utf-8',errors='replace') as stream:text=stream.read(1048576)
            dialog=QDialog(self);dialog.setWindowTitle('Licenças de '+item['name']);dialog.resize(800,600);body=QVBoxLayout(dialog);view=QPlainTextEdit(text);view.setReadOnly(True);body.addWidget(view);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);body.addWidget(buttons);dialog.exec()
        except (OSError,ValueError) as error:QMessageBox.warning(self,'Licença não disponível',str(error))

    def refresh_icons(self):
        super().refresh_icons()
        if not getattr(self,'ready',False):return
        for i in range(self.results.count()):
            item=self.results.item(i);card=self.results.itemWidget(item)
            if card:
                label=card.findChild(QLabel,'appIcon')
                if label:label.setPixmap(item.icon().pixmap(40,40))

    def save_preferences(self,*_):
        if not getattr(self,'ready',False):return
        from store_sources import atomic_write
        self.preferences.update(favorites=sorted(self.favorites),compact=self.compact.isChecked());self.preferences_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        atomic_write(self.preferences_path,json.dumps(self.preferences).encode(),0o600)
        self.refresh()

    def toggle_favorite(self):
        item=self.selected()
        if not item:return
        if item['id'] in self.favorites:self.favorites.remove(item['id'])
        else:self.favorites.add(item['id'])
        self.save_preferences();self.select()

    def reload_catalog(self):
        self.base_entries=backend.catalog()+catalog_sources.entries();self.repository_cache.clear()
        current=self.category.currentData();self.category.blockSignals(True)
        for index in range(self.navigation.count()-1,-1,-1):
            item=self.navigation.item(index);kind,value=item.data(Qt.ItemDataRole.UserRole)
            if kind=='category':self.links.pop(kind+':'+value,None);self.navigation.takeItem(index)
        for category in sorted({item['category'] for item in self.base_entries}):
            if self.category.findData(category)<0:self.category.addItem(category,category)
            self.nav_item(category,category_icon(category),('category',category))
        self.category.setCurrentIndex(max(0,self.category.findData(current)));self.category.blockSignals(False);self.refresh()

    def downloads(self):
        from store_operations import Operations
        if not hasattr(self,'operations'):self.operations=Operations(self)
        self.operations.show_history();self.operations.show();self.operations.raise_()

    def firmware(self,command):
        if command[-1]=='update' and QMessageBox.question(self,'Atualizar firmware','O fwupd apresentará as atualizações disponíveis. Mantenha o computador ligado e conectado à energia. Continuar?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        dialog=Command('Firmware dos dispositivos',command,self);self.dialogs.append(dialog)

    def closeEvent(self,event):
        if self.queries or self.sources.jobs or self.firmware_page.jobs or self.web_updates.jobs or any(d.process.state()!=d.process.ProcessState.NotRunning for d in self.dialogs+self.sources.commands+self.firmware_page.commands if not __import__('PyQt6.sip',fromlist=['isdeleted']).isdeleted(d)):
            event.ignore();QMessageBox.information(self,'Operação em andamento','Aguarde a consulta ou a operação concluir antes de fechar.');return
        super().closeEvent(event)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--installed',action='store_true');parser.add_argument('--updates',action='store_true');parser.add_argument('--sources',action='store_true');parser.add_argument('--firmware',action='store_true');parser.add_argument('--search',default='');args=parser.parse_args()
    app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-store')
    if not QIcon.themeName():QIcon.setThemeName('breeze')
    window=Window();window.show()
    if args.search:window.query.setText(args.search)
    for flag,key in [(args.installed,'installed'),(args.updates,'updates'),(args.sources,'sources'),(args.firmware,'firmware')]:
        if flag:window.navigation.setCurrentItem(window.links[key+':'])
    sys.exit(app.exec())
