#!/usr/bin/python3
"""Application storefront with library, source management and native operations."""
import argparse
import json
import os
from pathlib import Path
import sys
from PyQt6.QtCore import Qt,QSize,QTimer
from PyQt6.QtGui import QIcon,QFont,QFontMetrics
from PyQt6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,
    QListWidgetItem,QStackedWidget,QSplitter,QPushButton,QCheckBox,QFormLayout,QMessageBox,QStyledItemDelegate,QStyleOptionViewItem,QStyle,QSizePolicy)
from store import Window as OperationsWindow
import store_backend as backend
import catalog_sources
import store_repository
from store_source_page import Sources
from desktop_jobs import Query,Command
from firmware_page import Firmware


def category_icon(name):
    return {'Imagem e criação':'applications-graphics','Internet e comunicação':'applications-internet','Jogos':'applications-games','Música e vídeo':'applications-multimedia','Trabalho e estudo':'applications-office','Escritório':'applications-office','Produtividade':'applications-office','Utilitários':'applications-utilities','Desenvolvimento':'applications-development','Educação':'applications-education','Sistema':'applications-system'}.get(name,'applications-other')


class CardDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        style=QStyleOptionViewItem(option);self.initStyleOption(style,index);style.icon=QIcon();style.text=''
        (style.widget.style() if style.widget else QApplication.style()).drawControl(QStyle.ControlElement.CE_ItemViewItem,style,painter,style.widget)


class Window(OperationsWindow):
    def __init__(self):
        from desktop_theme import initialize
        initialize()
        self.ready=False;self.queries=set();self.repository_cache={};self.repository_errors={};self.requested=set();self.only_favorites=False;self.dialogs=[];self.metadata_cache={};self.metadata_requested=set()
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
        side=QWidget();side.setFixedWidth(max(196,min(300,self.fontMetrics().horizontalAdvance('Configurações')+64)));self.navigation_side=side
        column=QVBoxLayout(side);column.setContentsMargins(12,22,12,16)
        title_font=QFont(self.font());title_font.setPointSizeF(max(12,self.font().pointSizeF()+2))
        brand=QLabel('Loja Linux BR');brand.setFont(title_font);brand.setStyleSheet('font-weight:700;padding:8px 6px');column.addWidget(brand)
        self.navigation=QListWidget();self.navigation.setFrameShape(self.navigation.Shape.NoFrame);self.navigation.setSpacing(4);self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.navigation.setWordWrap(True);self.navigation.setTextElideMode(Qt.TextElideMode.ElideNone);column.addWidget(self.navigation,1);layout.addWidget(side)
        right=QWidget();body=QVBoxLayout(right);body.setContentsMargins(24,20,24,16);body.setSpacing(12);layout.addWidget(right,1)
        self.hero=QLabel('Encontre seu próximo aplicativo\nProgramas Linux, sites com janela própria e opções para Windows.');self.hero.setFont(title_font);self.hero.setWordWrap(True);self.hero.setMinimumHeight(96);self.hero.setStyleSheet('font-weight:600;padding:20px;border-radius:12px;color:white;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #095ba7,stop:1 #267d94);');body.addWidget(self.hero)
        filters=QHBoxLayout();self.query.setPlaceholderText('Pesquisar aplicativos, sites e programas…');self.query.setMinimumHeight(38);filters.addWidget(self.query,1);filters.addWidget(self.kind);filters.addWidget(self.category);body.addLayout(filters)
        for control in (self.kind,self.category):
            control.setSizeAdjustPolicy(control.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);control.setMinimumContentsLength(10)
            for index in range(control.count()):control.setItemData(index,control.itemText(index),Qt.ItemDataRole.ToolTipRole)
            control.setToolTip(control.currentText());control.currentTextChanged.connect(control.setToolTip)
        self.repository_note=QLabel();self.repository_note.setWordWrap(True);self.repository_note.setTextFormat(Qt.TextFormat.PlainText)
        self.repository_note.setAccessibleName('Estado da consulta nas fontes');self.repository_note.hide();body.addWidget(self.repository_note)
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
        self.heading.setStyleSheet('font-weight:600;');self.heading.setFont(title_font)
        for label in (self.heading,self.description,self.note,self.source,self.metadata):
            label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);label.setMinimumWidth(0)
        self.installer.setText('Abrir EXE / MSI…');self.installer.setToolTip('Escolha o arquivo EXE ou MSI que você já baixou para abrir no Wine.')
        self.manage_native.setText('Gerenciar aplicativo…');self.manage_windows.setText('Ambiente Wine…')
        self.remove_button.setText('Remover atalho…')
        for button in detail_area.widget().findChildren(QPushButton):
            button.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);button.setMinimumWidth(0);button.setToolTip(button.text())
        self.sources=Sources(self);self.pages.addWidget(self.sources)
        preferences=QWidget();form=QFormLayout(preferences);self.compact=QCheckBox('Usar cartões compactos');self.compact.setChecked(bool(self.preferences.get('compact')));self.compact.toggled.connect(self.save_preferences);form.addRow(QLabel('Preferências da Loja'));form.addRow(self.compact)
        note=QLabel('Instalações e atualizações são confirmadas pelos gerenciadores nativos. Os programas Windows usam o site oficial e o ambiente escolhido. Sites mantêm contas em perfis separados do Chromium.');note.setWordWrap(True);form.addRow(note);self.pages.addWidget(preferences)
        self.firmware_page=Firmware(self);self.pages.addWidget(self.firmware_page)
        from webapp_updates import WebUpdates
        self.web_updates=WebUpdates(self);self.pages.addWidget(self.web_updates)
        footer=QHBoxLayout();footer.addWidget(self.count,1)
        self.retry_search=QPushButton(QIcon.fromTheme('view-refresh'),'Repetir consulta')
        self.retry_search.setAccessibleName('Repetir consulta nas fontes de aplicativos');self.retry_search.clicked.connect(self.repeat_repository_search);self.retry_search.hide();footer.addWidget(self.retry_search)
        refresh=QPushButton(QIcon.fromTheme('view-refresh'),'Atualizar catálogo');refresh.clicked.connect(self.reload_catalog);footer.addWidget(refresh);body.addLayout(footer)
        self.links={}
        for caption,icon,data in [('Início','go-home',('catalog','')),('Biblioteca','applications-all',('installed','')),('Favoritos','rating',('favorites','')),('Downloads e histórico','folder-download',('downloads','')),('Atualizações','system-software-update',('updates','')),('Revisões de webapps','internet-web-browser',('web-updates','')),('Firmware','preferences-devices-cpu',('firmware','')),('Fontes','network-server',('sources','')),('Configurações','configure',('preferences',''))]:self.nav_item(caption,icon,data)
        for category in sorted({item['category'] for item in self.base_entries}):self.nav_item(category,category_icon(category),('category',category))
        self.navigation.currentItemChanged.connect(self.navigate);old.deleteLater();self.ready=True;self.navigation.setCurrentRow(0);self.refresh()

    def nav_item(self,caption,icon,data):
        height=self.fontMetrics().boundingRect(0,0,max(100,self.navigation_side.width()-76),2000,int(Qt.TextFlag.TextWordWrap),caption).height()+20
        item=QListWidgetItem(QIcon.fromTheme(icon),caption);item.setToolTip(caption);item.setData(Qt.ItemDataRole.UserRole,data);item.setSizeHint(QSize(150,max(42,height)));self.navigation.addItem(item);self.links[data[0]+':'+data[1]]=item

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
        super().refresh();errors=self.repository_errors.get(query,[])
        self.count.setText(str(self.results.count())+' resultados'+(' · consultando fontes…' if query in self.requested else ' · consulta incompleta' if errors else ''))
        self.count.setToolTip('\n'.join(errors));self.retry_search.setVisible(bool(errors));self.retry_search.setEnabled(query not in self.requested)
        self.repository_note.setText(' '.join(errors));self.repository_note.setVisible(bool(errors))
        card_width=max(228,min(420,self.fontMetrics().horizontalAdvance('Aplicativos e programas')+48))
        card_height=132 if self.compact.isChecked() else 148
        for index in range(self.results.count()):
            item=self.results.item(index);entry=item.data(Qt.ItemDataRole.UserRole);item.setData(Qt.ItemDataRole.AccessibleTextRole,entry['name']);card=QWidget();card.setFixedWidth(card_width);card.setAccessibleName(entry['name']);card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);card.setStyleSheet('background:transparent;');body=QVBoxLayout(card);body.setContentsMargins(16,12,16,10);header=QHBoxLayout();icon=QLabel();icon.setPixmap(item.icon().pixmap(40,40));icon.setObjectName('appIcon');header.addWidget(icon);header.addStretch();badge=QLabel({'linux':'Linux','web':'Web','windows':'Windows'}[entry['kind']]);header.addWidget(badge);body.addLayout(header)
            name=QLabel(entry['name']);name.setTextFormat(Qt.TextFormat.PlainText);name.setWordWrap(True);name.setStyleSheet('font-weight:600;');body.addWidget(name);label=QLabel(entry['category']);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True);body.addWidget(label);body.addStretch();item.setToolTip(entry['name']+'\n'+entry['description']);self.results.setItemWidget(item,card)
            card_height=max(card_height,body.totalHeightForWidth(card_width))
        for index in range(self.results.count()):self.results.item(index).setSizeHint(QSize(card_width,card_height))
        self.results.setGridSize(QSize(card_width+10,card_height+10))
        if 2<=len(query)<=100 and self.view.currentData()!='installed' and not self.only_favorites and query not in self.repository_cache and query not in self.requested:self.search_timer.start()

    def start_repository_search(self):
        query=self.query.text().strip()
        if len(self.queries)>=2:self.search_timer.start();return
        if query in self.requested or query in self.repository_cache or len(query)<2:return
        self.requested.add(query);task=Query(lambda:store_repository.search(query,with_status=True),self);self.queries.add(task)
        def loaded(value):
            rows=value.get('rows',[]) if isinstance(value,dict) else value
            self.repository_errors[query]=value.get('errors',[]) if isinstance(value,dict) else []
            self.repository_cache[query]=rows;self.requested.discard(query)
            while len(self.repository_cache)>40:
                oldest=next(iter(self.repository_cache));self.repository_cache.pop(oldest);self.repository_errors.pop(oldest,None)
            if self.query.text().strip()==query:self.refresh()
        task.result.connect(loaded);task.failed.connect(lambda _:loaded(dict(rows=[],errors=['A consulta não terminou. Confira as fontes e tente novamente.'])));task.finished.connect(lambda:self.queries.discard(task));task.finished.connect(task.deleteLater);task.start()

    def repeat_repository_search(self):
        query=self.query.text().strip()
        if query in self.requested:return
        self.repository_cache.pop(query,None);self.repository_errors.pop(query,None)
        self.start_repository_search();self.refresh()

    def select(self,*args):
        super().select(*args)
        if not getattr(self,'ready',False):return
        item=self.selected();self.favorite.setVisible(bool(item));self.favorite.setText('Remover favorito' if item and item['id'] in self.favorites else 'Favoritar')
        self.note.setText(self.note.text().replace('O Discover oferece outras fontes e pacotes.','Consulte as fontes configuradas na Loja.'))
        self.metadata.setText(self.metadata.text().replace('ou o Discover','na origem da instalação'))
        if self.primary.text().startswith('Baixar instalador'):
            self.primary.setToolTip(self.primary.text());self.primary.setText('Baixar instalador…')
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
        fields=[('type','Tipo'),('origin','Origem'),('version','Versão'),('size','Tamanho'),('publisher','Fornecedor / mantenedor'),('license','Licença')]
        if details.get('compatibility'):fields.append(('compatibility','Compatibilidade'))
        self.metadata.setText('\n'.join(label+': '+details.get(key,'Não informado.') for key,label in fields))
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
        self.base_entries=backend.catalog()+catalog_sources.entries();self.repository_cache.clear();self.repository_errors.clear()
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


def open_store_link(window, value):
    from store_links import parse_link, find_entry
    try:
        source, identifier = parse_link(value)
        entry = find_entry(window.base_entries, source, identifier)
        if entry is None:
            window.navigation.setCurrentItem(window.links['sources:'])
            QMessageBox.information(window, 'Aplicativo não encontrado',
                'O aplicativo não está nos catálogos habilitados deste computador. Confira e atualize as fontes da Loja. Nenhuma fonte foi adicionada pelo link.')
            return
        window.navigation.setCurrentItem(window.links['catalog:'])
        window.query.setText(entry['name'])
        for index in range(window.results.count()):
            if window.results.item(index).data(Qt.ItemDataRole.UserRole)['id'] == entry['id']:
                window.results.setCurrentRow(index)
                break
    except ValueError as error:
        QMessageBox.warning(window, 'Link da Loja', str(error))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('uri',nargs='?');parser.add_argument('--installed',action='store_true');parser.add_argument('--updates',action='store_true');parser.add_argument('--sources',action='store_true');parser.add_argument('--firmware',action='store_true');parser.add_argument('--search',default='');args=parser.parse_args()
    app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-store')
    if not QIcon.themeName():QIcon.setThemeName('breeze')
    window=Window();window.show()
    if args.search:window.query.setText(args.search)
    for flag,key in [(args.installed,'installed'),(args.updates,'updates'),(args.sources,'sources'),(args.firmware,'firmware')]:
        if flag:window.navigation.setCurrentItem(window.links[key+':'])
    if args.uri:QTimer.singleShot(0,lambda:open_store_link(window,args.uri))
    sys.exit(app.exec())
