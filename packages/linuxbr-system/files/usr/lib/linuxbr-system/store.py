#!/usr/bin/python3
"""Unified Portuguese discovery UI for Linux, Chromium sites and Wine software."""
import argparse
import subprocess
import sys
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QSplitter, QGridLayout, QScrollArea)
import store_backend as backend
import webapps_backend as web
from visual_style import BUTTONS


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Linux BR — Loja de aplicativos')
        self.resize(1040, 660)
        self.setWindowIcon(QIcon.fromTheme('system-software-install'))
        self.entries = backend.catalog()
        main = QWidget(); self.setCentralWidget(main); layout = QVBoxLayout(main)
        layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(12)
        title = QLabel('Loja de aplicativos'); title.setStyleSheet('font-size: 26px; font-weight: 600;')
        layout.addWidget(title)
        subtitle = QLabel('Encontre programas Linux, sites instaláveis e opções para usar com Wine.')
        subtitle.setWordWrap(True); layout.addWidget(subtitle)
        row = QHBoxLayout()
        self.view = QComboBox();self.view.addItem('Explorar catálogo', 'catalog');self.view.addItem('Meus aplicativos', 'installed')
        self.view.setAccessibleName('Visualização da loja');row.addWidget(self.view)
        self.query = QLineEdit(); self.query.setPlaceholderText('Buscar por nome ou finalidade…'); self.query.setClearButtonEnabled(True)
        self.query.setAccessibleName('Buscar aplicativos'); row.addWidget(self.query, 1)
        self.kind = QComboBox(); self.kind.addItem('Todos os tipos', '')
        for key, label in backend.KINDS.items(): self.kind.addItem(label, key)
        self.kind.setAccessibleName('Tipo de aplicativo'); row.addWidget(self.kind)
        self.category = QComboBox(); self.category.addItem('Todas as categorias', '')
        for category in sorted({item['category'] for item in self.entries}|{'Aplicativos instalados'}): self.category.addItem(category, category)
        self.category.setAccessibleName('Categoria'); row.addWidget(self.category); layout.addLayout(row)
        splitter = QSplitter(); layout.addWidget(splitter, 1)
        self.results = QListWidget(); self.results.setMinimumWidth(310); splitter.addWidget(self.results)
        self.results.setIconSize(QSize(32,32))
        detail = QWidget(); self.detail_layout = QVBoxLayout(detail); self.detail_layout.setSpacing(14)
        self.heading = QLabel(); self.heading.setStyleSheet('font-size: 22px; font-weight: 600;')
        self.description = QLabel(); self.note = QLabel(); self.source = QLabel(); self.metadata = QLabel()
        self.metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for label in (self.heading, self.description, self.note, self.source, self.metadata):
            label.setWordWrap(True); label.setTextFormat(Qt.TextFormat.PlainText); self.detail_layout.addWidget(label)
        self.primary = QPushButton(); self.primary.setProperty('primary', True); self.primary.clicked.connect(self.activate)
        self.detail_layout.addWidget(self.primary)
        self.manage_native = QPushButton('Instalar / atualizar / remover…')
        self.manage_native.setIcon(QIcon.fromTheme('system-software-install'))
        self.manage_native.clicked.connect(self.manage_linux); self.detail_layout.addWidget(self.manage_native)
        self.manage_windows = QPushButton('Gerenciar / desinstalar no ambiente Wine…')
        self.manage_windows.setIcon(QIcon.fromTheme('wine'))
        self.manage_windows.clicked.connect(self.manage_windows_program); self.detail_layout.addWidget(self.manage_windows)
        self.remove_button=QPushButton('Remover atalho do menu…');self.remove_button.clicked.connect(self.remove_local)
        self.remove_button.setIcon(QIcon.fromTheme('edit-delete'))
        self.detail_layout.addWidget(self.remove_button)
        self.new_session = QPushButton('Nova sessão / outra conta…')
        self.new_session.setIcon(QIcon.fromTheme('list-add-user'))
        self.new_session.clicked.connect(lambda: self.run(backend.action(self.selected())) if self.selected() else None)
        self.detail_layout.addWidget(self.new_session)
        self.website = QPushButton('Abrir site oficial'); self.website.clicked.connect(self.open_source); self.detail_layout.addWidget(self.website)
        self.website.setIcon(QIcon.fromTheme('internet-web-browser'))
        self.installer = QPushButton('Já baixei o EXE/MSI: abrir no Wine…')
        self.installer.setIcon(QIcon.fromTheme('application-x-ms-dos-executable'))
        self.installer.clicked.connect(lambda: self.run(['linuxbr-windows', '--page', 'install'])); self.detail_layout.addWidget(self.installer)
        self.compatibility=QPushButton('Receitas e matriz de compatibilidade…')
        self.compatibility.setIcon(QIcon.fromTheme('preferences-system-windows'))
        self.compatibility.clicked.connect(lambda:self.run(['linuxbr-windows','--page','recipes']))
        self.detail_layout.addWidget(self.compatibility)
        self.detail_layout.addStretch()
        area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(area.Shape.NoFrame)
        area.setWidget(detail);splitter.addWidget(area);splitter.setSizes([420,560])
        self.count = QLabel(); layout.addWidget(self.count)
        more = QGridLayout()
        for index,(text, callback) in enumerate((
            ('Pesquisar nas fontes da Loja', self.discover),
            ('Atualizar lista', self.refresh),
            ('Atualizações', self.open_updates),
            ('Gerenciar pacotes Linux', lambda: self.run(['linuxbr-store', '--installed'])),
            ('Meus aplicativos web', lambda: self.run(['linuxbr-webapps'])),
            ('Programas Windows e jogos', lambda: self.run(['linuxbr-windows'])))):
            button = QPushButton(text); button.clicked.connect(callback)
            button.setIcon(QIcon.fromTheme(('edit-find','view-refresh','system-software-update','package-x-generic','internet-web-browser','wine')[index]))
            more.addWidget(button,index//3,index%3)
        layout.addLayout(more)
        for signal in (self.query.textChanged, self.kind.currentIndexChanged, self.category.currentIndexChanged, self.view.currentIndexChanged): signal.connect(self.refresh)
        self.results.currentItemChanged.connect(self.select)
        self.refresh()
        self.icon_timer=QTimer(self);self.icon_timer.setInterval(2000)
        self.icon_timer.timeout.connect(self.refresh_icons);self.icon_timer.start()

    def refresh(self):
        previous = self.selected()
        self.results.clear()
        entries=backend.installed_entries(self.entries) if self.view.currentData()=='installed' else self.entries
        matches = backend.search(entries, self.query.text(), self.kind.currentData(), self.category.currentData())
        selected = 0
        for index, entry in enumerate(matches):
            item = QListWidgetItem(entry['name'] + '\n' + backend.KINDS[entry['kind']] + ' · ' + entry['category'])
            item.setData(Qt.ItemDataRole.UserRole, entry); self.results.addItem(item)
            if entry['kind']=='web':
                from webapp_icons import request_refresh
                item.setIcon(QIcon(str(web.icon_path(entry))));request_refresh(entry['url'])
            else:
                icon=entry.get('icon') or {'obs':'com.obsproject.Studio','steam':'steam','libreoffice':'libreoffice-startcenter'}.get(entry['id'],entry['id'])
                item.setIcon(QIcon(icon) if icon.startswith('/') else QIcon.fromTheme(icon,
                    QIcon.fromTheme('wine' if entry['kind']=='windows' else 'applications-other')))
            if previous and entry['id'] == previous['id']: selected = index
        self.count.setText(f'{len(matches)} aplicativos locais. Para a lista completa de pacotes Linux, use Gerenciar pacotes Linux.' if self.view.currentData()=='installed' else f'{len(matches)} resultados no catálogo selecionado. O Discover consulta outras opções nas fontes configuradas.')
        if matches: self.results.setCurrentRow(selected)
        else: self.select()

    def refresh_icons(self):
        for index in range(self.results.count()):
            item=self.results.item(index);entry=item.data(Qt.ItemDataRole.UserRole)
            if entry['kind']=='web':item.setIcon(QIcon(str(web.icon_path(entry))))

    def selected(self):
        item = self.results.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def select(self, *_):
        item = self.selected()
        try:local_command = backend.local_action(item)
        except (OSError,ValueError):local_command=None
        self.primary.setEnabled(not bool(item and item.get('desktop_id') and not local_command))
        for button in (self.primary, self.website, self.installer): button.setVisible(bool(item))
        self.manage_native.setVisible(bool(item and item['kind']=='linux'))
        self.manage_windows.setVisible(bool(item and item.get('program_id')))
        self.compatibility.setVisible(bool(item and item['kind']=='windows'))
        self.remove_button.setVisible(bool(item and (item.get('profile_id') or item.get('program_id'))))
        self.new_session.setVisible(bool(item and item['kind'] == 'web' and web.status(item)['installed']))
        if not item:
            self.heading.setText('Nenhum resultado'); self.description.setText('Tente outro termo ou pesquise mais no Discover.')
            self.note.clear(); self.source.clear(); self.metadata.clear(); return
        self.heading.setText(item['name']); self.description.setText(item['description'])
        self.note.setText(item.get('note', 'Escolha a origem e o alcance em Instalar / atualizar / remover. O Discover oferece outras fontes e pacotes.'))
        if local_command and item['kind']=='linux':
            self.note.setText(self.note.text() + '\n\nVocê pode abrir este aplicativo diretamente. Use Instalar / atualizar / remover para escolher a origem e o alcance.')
        self.source.setText(('Compatibilidade: ' if item.get('program_id') else 'Fonte: ') + item['source'])
        self.website.setText('Ajuda do Wine' if item.get('program_id') else 'Abrir site oficial')
        details=self.metadata_for(item)
        self.metadata.setText('\n'.join(label+': '+details[key] for key,label in
            (('type','Tipo'),('origin','Origem da instalação'),('version','Versão'),('size','Tamanho'))))
        self.website.setVisible(not bool(item.get('desktop_id')))
        label = {'linux': 'Instalar aplicativo…', 'web': 'Instalar aplicativo web…', 'windows': 'Baixar instalador no site oficial'}[item['kind']]
        if item['kind'] == 'web' and web.status(item)['installed']: label = 'Abrir aplicativo web'
        elif local_command: label = 'Abrir aplicativo'
        if item.get('profile_id'):label='Abrir este perfil'
        elif item.get('program_id'):label='Abrir programa Windows'
        self.primary.setText(label); self.installer.setVisible(item['kind'] == 'windows' and not item.get('program_id'))
        self.primary.setIcon(QIcon.fromTheme('media-playback-start' if local_command else
            {'linux':'system-software-install','web':'list-add','windows':'download'}[item['kind']]))

    def metadata_for(self,item):return backend.package_metadata(item)

    def run(self, argv):
        try:
            subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error: QMessageBox.warning(self, 'Não foi possível abrir', str(error))

    def activate(self):
        item = self.selected()
        if not item: return
        try:
            if item.get('profile_id') or item.get('program_id') or item.get('desktop_id'):
                self.run(backend.local_action(item))
            elif item['kind'] == 'web' and web.status(item)['installed']:
                self.run(['linuxbr-webapps', '--open-site', web.normalize_offer(item)['url']])
            elif item['kind']=='linux' and not backend.native_launch(item):self.manage_linux()
            else:
                # Recheck at click time: a package may have been removed in Discover.
                self.run(backend.native_launch(item) or backend.action(item))
        except (OSError, ValueError) as error: QMessageBox.warning(self, 'Não foi possível abrir', str(error))

    def remove_local(self):
        item=self.selected()
        if not item:return
        if QMessageBox.question(self,'Remover atalho','Remover '+item['name']+' do menu? O programa, seus arquivos e dados serão preservados.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:
            if item.get('profile_id'):web.remove(item['profile_id'])
            elif item.get('program_id'):
                from windows_runner import forget_program
                forget_program(item['program_id'])
            self.refresh()
        except (OSError,ValueError) as error:QMessageBox.warning(self,'Não foi possível remover',str(error))

    def open_source(self):
        item = self.selected()
        if item:
            try: self.run(['xdg-open', web.clean_url(item['source'])])
            except ValueError as error: QMessageBox.warning(self, 'Endereço inválido', str(error))

    def discover(self):
        self.run(['linuxbr-store', '--search', self.query.text().strip()] if self.query.text().strip() else ['linuxbr-store'])

    def manage_linux(self):
        item = self.selected()
        if item and item['kind'] == 'linux':
            from store_operations import Operations
            if not hasattr(self,'operations'):self.operations=Operations(self)
            self.operations.set_item(item)

    def open_updates(self):
        from store_operations import Operations
        if not hasattr(self,'operations'):self.operations=Operations(self)
        self.operations.show_updates()

    def closeEvent(self,event):
        operations=getattr(self,'operations',None)
        if operations and (operations.process or operations.queue):
            operations.show();operations.raise_();event.ignore()
            QMessageBox.information(self,'Operação em andamento','Conclua as operações na janela da Loja antes de fechar.');return
        super().closeEvent(event)

    def manage_windows_program(self):
        item=self.selected()
        if item and item.get('program_id'):
            try:self.run(backend.manage_action(item))
            except (OSError,ValueError) as error:QMessageBox.warning(self,'Programa indisponível',str(error))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.ActivationChange and self.isActiveWindow() and hasattr(self, 'results'): self.select()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--installed',action='store_true');parser.add_argument('--updates',action='store_true');args=parser.parse_args()
    app = QApplication(sys.argv); app.setDesktopFileName('linuxbr-store'); app.setStyleSheet(BUTTONS)
    window = Window()
    if args.installed:window.view.setCurrentIndex(1)
    if args.updates:QTimer.singleShot(0,window.open_updates)
    window.show(); sys.exit(app.exec())
