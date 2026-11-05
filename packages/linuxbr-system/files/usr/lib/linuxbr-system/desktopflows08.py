"""Daily desktop flows using the native search, launchers and associations."""
import argparse
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication,QWidget,QMainWindow,QVBoxLayout,QHBoxLayout,
    QGridLayout,QLabel,QLineEdit,QPushButton,QTabWidget,QTreeWidget,QTreeWidgetItem,
    QScrollArea,QFileDialog,QComboBox,QMessageBox,QPlainTextEdit,QFrame,QToolButton,
    QSizePolicy)
import desktopflows08_backend as backend
from visual_style import BUTTONS
from keyboard_controls import EnterActivation,SettingsButton


def text_label(value):
    label=QLabel(value);label.setWordWrap(True);label.setTextFormat(Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse|Qt.TextInteractionFlag.TextSelectableByKeyboard)
    label.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    return label


class PathButton(EnterActivation,QToolButton):
    pass


class DesktopFlowsPage(QWidget):
    SECTIONS={
        'search':('Pesquisa','Arquivos e resultados','system-search','search-category'),
        'startup':('Aplicativos','Inicialização','system-run','apps'),
        'defaults':('Aplicativos','Aplicativos padrão','preferences-desktop-default-applications','apps'),
        'transfers':('Sistema','Cópias e conflitos','edit-copy','files'),
    }
    CATEGORIES={
        'overview':('Configurações','Escolha uma categoria para continuar.'),
        'apps':('Aplicativos','Escolha como os programas abrem e quais iniciam com sua conta.'),
        'search-category':('Pesquisa','Encontre arquivos e ajuste as fontes dos resultados.'),
        'files':('Sistema','Acompanhe as operações com seus arquivos.'),
    }

    def __init__(self, page='search', parent=None):
        super().__init__(parent);self.setStyleSheet(BUTTONS);self.change=None;self.association=None
        self.history=[];self.current_page=None;self.navigation={};self.breadcrumb_buttons=[]
        layout=QVBoxLayout(self);layout.setSpacing(12)
        self.breadcrumbs=QHBoxLayout();self.breadcrumbs.setSpacing(5);layout.addLayout(self.breadcrumbs)
        heading=QHBoxLayout();layout.addLayout(heading)
        self.page_icon=QLabel();self.page_icon.setFixedSize(32,32);heading.addWidget(self.page_icon)
        self.title=QLabel();self.title.setWordWrap(True)
        font=self.title.font();font.setPointSize(font.pointSize()+5);font.setBold(True);self.title.setFont(font)
        heading.addWidget(self.title,1)
        self.tabs=QTabWidget();self.tabs.tabBar().hide();layout.addWidget(self.tabs,1)
        self.pages={};self.focus_targets={}
        for key,title,builder in [('search','Pesquisa',self.build_search),('startup','Inicialização',self.build_startup),
                                  ('defaults','Aplicativos padrão',self.build_defaults),('transfers','Cópias e conflitos',self.build_transfers)]:
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
            content=QWidget();body=QVBoxLayout(content);body.setContentsMargins(2,2,8,12);body.setSpacing(12)
            builder(body);body.addStretch();scroll.setWidget(content);self.pages[key]=self.tabs.addTab(scroll,title)
        for key in self.CATEGORIES:
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
            content=QWidget();body=QVBoxLayout(content);body.setContentsMargins(2,2,8,12);body.setSpacing(12)
            self.build_category(body,key);body.addStretch();scroll.setWidget(content);self.pages[key]=self.tabs.addTab(scroll,key)
        self.status=text_label('');self.status.setAccessibleName('Resultado da ação');layout.addWidget(self.status)
        self.focus_targets.update(search=self.query,startup=self.startup,defaults=self.choose,transfers=self.transfer_open)
        self.back_shortcut=QShortcut(QKeySequence('Alt+Left'),self);self.back_shortcut.activated.connect(self.go_back)
        self.navigate(page if page in self.pages else 'overview',remember=False,focus=False)
        self.refresh_startup();self.filter_actions()

    def navigate(self,key,remember=True,focus=True):
        if key not in self.pages:return
        if remember and self.current_page and self.current_page!=key:self.history.append(self.current_page)
        self.current_page=key;self.tabs.setCurrentIndex(self.pages[key])
        while self.breadcrumbs.count():
            item=self.breadcrumbs.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.breadcrumb_buttons=[]
        back=PathButton();back.setIcon(QIcon.fromTheme('go-previous'));back.setText('Voltar');back.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        back.setAccessibleName('Voltar à página anterior (Alt+Seta para a esquerda)')
        back.setToolTip(back.accessibleName());back.setEnabled(bool(self.history));back.clicked.connect(self.go_back)
        self.breadcrumbs.addWidget(back);self.breadcrumb_buttons.append(back)
        chain=[('overview','Configurações')]
        if key in self.SECTIONS:
            category,title,icon,category_key=self.SECTIONS[key];chain.extend([(category_key,category),(key,title)])
        elif key!='overview':chain.append((key,self.CATEGORIES[key][0]))
        for index,(target,label) in enumerate(chain):
            if index:self.breadcrumbs.addWidget(QLabel('›'))
            if index==len(chain)-1:
                current=QLabel(label);current.setWordWrap(True);current.setAccessibleName('Página atual: '+label);self.breadcrumbs.addWidget(current)
            else:
                button=PathButton();button.setText(label);button.setAutoRaise(True);button.setAccessibleName('Ir para '+label)
                button.clicked.connect(lambda checked=False,target=target:self.navigate(target));self.breadcrumbs.addWidget(button);self.breadcrumb_buttons.append(button)
        self.breadcrumbs.addStretch()
        if key in self.SECTIONS:
            _category,title,icon,_category_key=self.SECTIONS[key]
        else:
            title=self.CATEGORIES[key][0];icon={'overview':'preferences-system','apps':'applications-other','files':'computer','search-category':'system-search'}[key]
        self.title.setText(title);self.page_icon.setPixmap(QIcon.fromTheme(icon).pixmap(QSize(28,28)))
        self.tabs.currentWidget().verticalScrollBar().setValue(0)
        if focus:
            target=self.focus_targets.get(key)
            if target:target.setFocus(Qt.FocusReason.OtherFocusReason)

    def go_back(self):
        if self.history:self.navigate(self.history.pop(),remember=False)

    def section(self,body,title,description=''):
        frame=QFrame();frame.setProperty('flowSection',True)
        frame.setStyleSheet('QFrame[flowSection="true"] { border:1px solid palette(mid); }')
        group=QVBoxLayout(frame);group.setContentsMargins(14,12,14,14);group.setSpacing(10)
        label=text_label(title);font=label.font();font.setBold(True);label.setFont(font);group.addWidget(label)
        if description:group.addWidget(text_label(description))
        body.addWidget(frame);return group

    def action_row(self,body,title,description,callback,icon='configure'):
        frame=QFrame();row=QHBoxLayout(frame);row.setContentsMargins(0,2,0,2);row.setSpacing(12)
        symbol=QLabel();symbol.setPixmap(QIcon.fromTheme(icon).pixmap(QSize(24,24)));symbol.setFixedSize(26,26);row.addWidget(symbol)
        labels=QVBoxLayout();labels.setSpacing(3);row.addLayout(labels,1)
        name=text_label(title);font=name.font();font.setBold(True);name.setFont(font);labels.addWidget(name)
        if description:labels.addWidget(text_label(description))
        button=SettingsButton('Abrir');button.setAccessibleName('Abrir '+title.replace('&',''));button.setToolTip(description)
        button.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed);button.clicked.connect(callback);row.addWidget(button)
        body.addWidget(frame);return button

    def build_category(self,body,key):
        body.addWidget(text_label(self.CATEGORIES[key][1]))
        descriptions={
            'defaults':'Escolha o navegador e o aplicativo usado para cada tipo de arquivo.',
            'startup':'Veja a origem e ative ou desative programas ao entrar na sessão.',
            'search':'Pesquise no sistema e ajuste o índice, as exclusões e os atalhos.',
            'transfers':'Abra o Explorador e veja onde acompanhar progresso e conflitos.',
        }
        groups=[('apps','Aplicativos',('defaults','startup')),('search-category','Pesquisa',('search',)),('files','Sistema',('transfers',))]
        for category,label,leaves in groups:
            if key!='overview' and key!=category:continue
            group=self.section(body,label)
            for leaf in leaves:
                _category,title,icon,_parent=self.SECTIONS[leaf]
                button=self.action_row(group,title,descriptions[leaf],lambda checked=False,leaf=leaf:self.navigate(leaf),icon)
                self.navigation[(key,leaf)]=button
                self.focus_targets.setdefault(key,button)

    def invoke(self, action, query=''):
        try:backend.launch_native(action,query);self.status.setText('Janela do sistema solicitada. Continue a ação nela.')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def button(self, body, label, action, icon='configure',description=''):
        return self.action_row(body,label.replace('&',''),description,lambda checked=False:self.invoke(action),icon)

    def build_search(self, body):
        body.addWidget(text_label('Encontre aplicativos, configurações e arquivos na sua conta.'))
        search_group=self.section(body,'Pesquisar no sistema','Os arquivos encontrados dependem das suas permissões e das pastas incluídas no índice.')
        self.query=QLineEdit();self.query.setPlaceholderText('Ex.: abrir com, inicialização, navegador padrão ou nome de arquivo')
        self.query.setAccessibleName('Termo de pesquisa');self.query.textChanged.connect(self.filter_actions)
        self.query.returnPressed.connect(self.search_system);search_group.addWidget(self.query)
        search=SettingsButton(QIcon.fromTheme('system-search'),'&Pesquisar no sistema');search.clicked.connect(self.search_system);search_group.addWidget(search)
        search_group.addWidget(text_label('Configurações relacionadas ao termo:'))
        self.actions=QTreeWidget();self.actions.setHeaderLabels(['Configuração','Tipo']);self.actions.setRootIsDecorated(False)
        self.actions.setAccessibleName('Configurações relacionadas à pesquisa');self.actions.setMinimumHeight(190)
        self.actions.itemActivated.connect(lambda item,column:self.invoke(item.data(0,Qt.ItemDataRole.UserRole)));search_group.addWidget(self.actions)
        search_group.addWidget(text_label('O KRunner abre os resultados completos, com os tipos e locais informados por cada serviço.'))
        preferences=self.section(body,'Preferências de pesquisa')
        self.button(preferences,'Pastas e exclusões','index','folder-open',description='Escolha os locais incluídos no índice de arquivos.')
        self.button(preferences,'Fontes dos resultados','search-settings','view-list-details',description='Configure os serviços usados pelo KRunner.')
        self.button(preferences,'Atalhos de teclado','shortcuts','preferences-desktop-keyboard',description='Consulte ou altere as combinações da pesquisa nesta sessão.')
        diagnosis=self.section(body,'Estado do índice','Consulte o diagnóstico fornecido pelo Baloo.')
        self.index_status=QPlainTextEdit();self.index_status.setReadOnly(True);self.index_status.setAccessibleName('Diagnóstico de indexação fornecido pelo Baloo');self.index_status.setMaximumHeight(130);diagnosis.addWidget(self.index_status)
        refresh=SettingsButton('Consultar &estado');refresh.clicked.connect(lambda:self.index_status.setPlainText(backend.indexing_status()));diagnosis.addWidget(refresh)

    def filter_actions(self):
        self.actions.clear()
        for label,action in backend.search_actions(self.query.text()):
            item=QTreeWidgetItem([label,'Configuração do sistema']);item.setData(0,Qt.ItemDataRole.UserRole,action);self.actions.addTopLevelItem(item)
        self.actions.resizeColumnToContents(0)

    def search_system(self):self.invoke('search',self.query.text().strip())

    def build_startup(self, body):
        body.addWidget(text_label('Escolha quais programas abrem quando você entra na sessão. As alterações valem para esta conta, na próxima entrada.'))
        programs=self.section(body,'Programas ao entrar','Selecione um programa para conferir a origem e alterar sua preferência.')
        self.startup=QTreeWidget();self.startup.setHeaderLabels(['Programa','Origem','Estado']);self.startup.setRootIsDecorated(False)
        self.startup.setAccessibleName('Aplicativos da inicialização, origem e estado');self.startup.setMinimumHeight(200);self.startup.currentItemChanged.connect(self.startup_selection);programs.addWidget(self.startup)
        self.startup_detail=text_label('Selecione um programa para conferir sua origem.');programs.addWidget(self.startup_detail)
        row=QGridLayout();programs.addLayout(row)
        self.enable=SettingsButton(QIcon.fromTheme('media-playback-start'),'&Ativar');self.enable.setAccessibleName('Ativar o programa selecionado ao entrar nesta conta');self.enable.clicked.connect(lambda:self.toggle_startup(True));row.addWidget(self.enable,0,0)
        self.disable=SettingsButton(QIcon.fromTheme('media-playback-pause'),'&Desativar');self.disable.setAccessibleName('Desativar o programa selecionado ao entrar nesta conta');self.disable.clicked.connect(lambda:self.toggle_startup(False));row.addWidget(self.disable,0,1)
        self.restore=SettingsButton(QIcon.fromTheme('edit-undo'),'&Restaurar estado anterior');self.restore.clicked.connect(self.restore_startup);row.addWidget(self.restore,1,0)
        refresh=SettingsButton(QIcon.fromTheme('view-refresh'),'&Atualizar lista');refresh.clicked.connect(self.refresh_startup);row.addWidget(refresh,1,1)
        preferences=self.section(body,'Configurações relacionadas')
        self.button(preferences,'Adicionar programas e ver registros','startup','list-add',description='Abra as preferências nativas de inicialização. Os registros dependem do ambiente.')
        self.button(preferences,'Restauração da sessão','session','system-log-out',description='Confira os aplicativos que podem reabrir da sessão anterior.')
        body.addWidget(text_label('A lista contém lançadores de sessão. Ela não desativa serviços do sistema nem encerra programas que já estão abertos. O impacto na inicialização não é estimado.'))

    def current_startup(self):
        selected=self.startup.currentItem()
        return selected.data(0,Qt.ItemDataRole.UserRole) if selected else None

    def refresh_startup(self):
        current=self.current_startup();identifier=current['id'] if current else None
        self.startup.clear()
        try:
            for entry in backend.autostart_entries():
                item=QTreeWidgetItem([entry['name'],entry['origin'],entry['status']]);item.setData(0,Qt.ItemDataRole.UserRole,entry)
                self.startup.addTopLevelItem(item)
                if entry['id']==identifier:self.startup.setCurrentItem(item)
            if not self.startup.currentItem() and self.startup.topLevelItemCount():self.startup.setCurrentItem(self.startup.topLevelItem(0))
            self.startup.resizeColumnToContents(0);self.startup.resizeColumnToContents(1);self.startup_selection()
        except (OSError,ValueError) as exc:
            if hasattr(self,'status'):self.status.setText(str(exc))

    def startup_selection(self, *_args):
        entry=self.current_startup();editable=bool(entry and entry['editable'])
        self.enable.setEnabled(editable and not entry['configured']);self.disable.setEnabled(editable and entry['configured'])
        self.restore.setEnabled(bool(entry and entry['restorable']))
        self.startup_detail.setText(('Origem: '+entry['path']+'\nComando declarado: '+entry['command']) if entry else 'Nenhum lançador de sessão foi encontrado.')

    def toggle_startup(self, enabled):
        entry=self.current_startup()
        if not entry:return
        try:
            backend.set_autostart(entry['id'],enabled);self.refresh_startup()
            self.status.setText('Preferência salva para a próxima entrada. O programa em execução não foi encerrado.')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def restore_startup(self):
        entry=self.current_startup()
        if not entry:return
        try:backend.restore_autostart(entry['id']);self.refresh_startup();self.status.setText('Estado anterior restaurado para esta conta.')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def build_defaults(self, body):
        body.addWidget(text_label('Escolha os aplicativos usados para abrir arquivos e links. As opções vêm dos programas registrados no sistema.'))
        preferences=self.section(body,'Padrões do sistema')
        self.button(preferences,'Navegador, e-mail e outros padrões','defaults','preferences-desktop-default-applications',description='Abra os aplicativos padrão nas preferências do KDE.')
        self.button(preferences,'Tipos de arquivo e extensões','filetypes','preferences-desktop-filetype-association',description='Edite as associações e a ordem dos aplicativos por tipo.')
        file_group=self.section(body,'Escolher pelo arquivo','Selecione um arquivo para conferir o tipo e alterar o aplicativo usado para esse tipo.')
        self.choose=SettingsButton(QIcon.fromTheme('document-open'),'Selecionar &arquivo');self.choose.clicked.connect(self.choose_file);file_group.addWidget(self.choose)
        self.association_label=text_label('Nenhum arquivo selecionado.');file_group.addWidget(self.association_label)
        self.applications=QComboBox();self.applications.setAccessibleName('Aplicativo registrado para associar ao tipo selecionado')
        self.applications.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.applications.setMinimumContentsLength(20)
        self.applications.setEnabled(False);file_group.addWidget(self.applications)
        file_group.addWidget(text_label('São listados os programas que declaram suporte ao tipo e o padrão atual. Outras opções registradas ficam no editor de tipos.'))
        row=QGridLayout();file_group.addLayout(row)
        self.apply_default=SettingsButton('&Usar para este tipo');self.apply_default.clicked.connect(self.set_default);self.apply_default.setEnabled(False);row.addWidget(self.apply_default,0,0)
        self.undo_default=SettingsButton('&Desfazer última associação');self.undo_default.clicked.connect(self.undo);self.undo_default.setEnabled(False);row.addWidget(self.undo_default,0,1)
        self.open_default=SettingsButton('A&brir arquivo para testar');self.open_default.clicked.connect(self.test_default);self.open_default.setEnabled(False);row.addWidget(self.open_default,1,0)
        body.addWidget(text_label('No Explorador, use Abrir com para experimentar outro aplicativo. Programas Windows e destinos web aparecem quando possuem um lançador compatível registrado.'))

    def choose_file(self):
        path,_filter=QFileDialog.getOpenFileName(self,'Consultar aplicativo padrão',str(Path.home()))
        if not path:return
        try:self.load_association(path)
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def load_association(self, path):
        self.association=backend.file_association(path);association=self.association;self.applications.clear()
        for entry in backend.applications():
            if association['mime'] in entry['types'] or entry['id']==association['default']:
                self.applications.addItem(entry['name']+' — '+entry['id'],entry['id'])
        self.association_label.setText('Arquivo: '+association['path']+'\nTipo: '+association['mime']+'\nAplicativo padrão: '+(association['default'] or 'Não informado pelo sistema'))
        index=self.applications.findData(association['default']);self.applications.setCurrentIndex(max(index,0))
        self.applications.setEnabled(self.applications.count()>0);self.apply_default.setEnabled(self.applications.count()>0);self.open_default.setEnabled(True)

    def set_default(self):
        if not self.association or not self.applications.currentData():return
        try:
            self.change=backend.set_default(self.association['mime'],self.applications.currentData())
            self.undo_default.setEnabled(bool(self.change['previous']))
            self.load_association(self.association['path']);self.status.setText('Associação confirmada pelo sistema. Use Abrir arquivo para testar.' if self.change['previous'] else 'Associação confirmada. Não havia padrão anterior; ajustes adicionais ficam no editor de tipos do KDE.')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def undo(self):
        if not self.change:return
        try:
            backend.undo_default(self.change);self.change=None;self.undo_default.setEnabled(False)
            if self.association:self.load_association(self.association['path'])
            self.status.setText('Aplicativo padrão anterior restaurado e conferido pelo sistema.')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def test_default(self):
        if not self.association:return
        if QMessageBox.question(self,'Abrir para testar','Abrir o arquivo selecionado no aplicativo padrão?\n'+self.association['path'])!=QMessageBox.StandardButton.Yes:return
        try:backend.test_default(self.association['path']);self.status.setText('Abertura solicitada ao sistema. Confira o arquivo no aplicativo escolhido.')
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def build_transfers(self, body):
        body.addWidget(text_label('O Explorador e as notificações do KDE acompanham as operações reais com seus arquivos.'))
        progress=self.section(body,'Progresso das transferências','Ao copiar ou mover, abra a notificação da operação ou o painel junto ao relógio.')
        self.transfer_open=self.button(progress,'Explorador de arquivos','files','system-file-manager',description='Abra pastas, copie, mova e confira o destino.')
        self.button(progress,'Notificações de arquivos','notifications','preferences-desktop-notification',description='Ajuste a apresentação do progresso e dos avisos.')
        conflicts=self.section(body,'Quando já existe um arquivo')
        conflicts.addWidget(text_label('O diálogo da operação pode oferecer substituir, manter ambos com outro nome ou ignorar. Confira nomes, tamanhos e datas antes de substituir. Uma comparação detalhada precisa de um comparador instalado.'))
        interrupted=self.section(body,'Pausa, cancelamento e falhas')
        interrupted.addWidget(text_label('Pausar e continuar dependem do protocolo e da operação. Cancelar interrompe o trabalho restante; itens concluídos podem permanecer no destino.'))
        interrupted.addWidget(text_label('Se faltar espaço ou o destino desconectar, siga o aviso da operação. Em rede, reconecte e repita somente os itens que falharam. Confira o destino antes de remover a origem.'))
        body.addWidget(text_label('Esta página abre os componentes existentes e orienta o uso da fila nativa do KDE.'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--page',choices=tuple(DesktopFlowsPage.SECTIONS)+tuple(DesktopFlowsPage.CATEGORIES),default='search');args=parser.parse_args()
    app=QApplication(sys.argv);app.setApplicationName('Linux BR — Pesquisa e arquivos');app.setDesktopFileName('linuxbr-desktop-flows')
    window=QMainWindow();window.setWindowTitle('Linux BR — Pesquisa, inicialização e arquivos');window.setWindowIcon(QIcon.fromTheme('preferences-system'))
    window.resize(930,720);window.setCentralWidget(DesktopFlowsPage(args.page));window.show();app.exec()


if __name__=='__main__':main()
