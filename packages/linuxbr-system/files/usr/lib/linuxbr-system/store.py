#!/usr/bin/python3
"""Unified Portuguese discovery UI for Linux, Chromium sites and Wine software."""
import subprocess
import sys
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QSplitter)
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
        self.query = QLineEdit(); self.query.setPlaceholderText('Buscar por nome ou finalidade…'); self.query.setClearButtonEnabled(True)
        self.query.setAccessibleName('Buscar aplicativos'); row.addWidget(self.query, 1)
        self.kind = QComboBox(); self.kind.addItem('Todos os tipos', '')
        for key, label in backend.KINDS.items(): self.kind.addItem(label, key)
        self.kind.setAccessibleName('Tipo de aplicativo'); row.addWidget(self.kind)
        self.category = QComboBox(); self.category.addItem('Todas as categorias', '')
        for category in sorted({item['category'] for item in self.entries}): self.category.addItem(category, category)
        self.category.setAccessibleName('Categoria'); row.addWidget(self.category); layout.addLayout(row)
        splitter = QSplitter(); layout.addWidget(splitter, 1)
        self.results = QListWidget(); self.results.setMinimumWidth(310); splitter.addWidget(self.results)
        self.results.setIconSize(QSize(32,32))
        detail = QWidget(); self.detail_layout = QVBoxLayout(detail); self.detail_layout.setSpacing(14)
        self.heading = QLabel(); self.heading.setStyleSheet('font-size: 22px; font-weight: 600;')
        self.description = QLabel(); self.note = QLabel(); self.source = QLabel()
        for label in (self.heading, self.description, self.note, self.source):
            label.setWordWrap(True); label.setTextFormat(Qt.TextFormat.PlainText); self.detail_layout.addWidget(label)
        self.primary = QPushButton(); self.primary.setProperty('primary', True); self.primary.clicked.connect(self.activate)
        self.detail_layout.addWidget(self.primary)
        self.manage_native = QPushButton('Gerenciar instalação no Discover')
        self.manage_native.clicked.connect(self.manage_linux); self.detail_layout.addWidget(self.manage_native)
        self.new_session = QPushButton('Nova sessão / outra conta…')
        self.new_session.clicked.connect(lambda: self.run(backend.action(self.selected())) if self.selected() else None)
        self.detail_layout.addWidget(self.new_session)
        self.website = QPushButton('Abrir site oficial'); self.website.clicked.connect(self.open_source); self.detail_layout.addWidget(self.website)
        self.installer = QPushButton('Já baixei o EXE/MSI: abrir no Wine…')
        self.installer.clicked.connect(lambda: self.run(['linuxbr-windows', '--page', 'install'])); self.detail_layout.addWidget(self.installer)
        self.detail_layout.addStretch(); splitter.addWidget(detail); splitter.setSizes([420, 560])
        self.count = QLabel(); layout.addWidget(self.count)
        more = QHBoxLayout()
        for text, callback in (
            ('Pesquisar mais no Discover', self.discover),
            ('Instalados e atualizações', lambda: self.run(['plasma-discover', '--mode', 'Installed'])),
            ('Meus aplicativos web', lambda: self.run(['linuxbr-webapps'])),
            ('Programas Windows e jogos', lambda: self.run(['linuxbr-windows']))):
            button = QPushButton(text); button.clicked.connect(callback); more.addWidget(button)
        layout.addLayout(more)
        for signal in (self.query.textChanged, self.kind.currentIndexChanged, self.category.currentIndexChanged): signal.connect(self.refresh)
        self.results.currentItemChanged.connect(self.select)
        self.refresh()
        self.icon_timer=QTimer(self);self.icon_timer.setInterval(2000)
        self.icon_timer.timeout.connect(self.refresh_icons);self.icon_timer.start()

    def refresh(self):
        previous = self.selected()
        self.results.clear()
        matches = backend.search(self.entries, self.query.text(), self.kind.currentData(), self.category.currentData())
        selected = 0
        for index, entry in enumerate(matches):
            item = QListWidgetItem(entry['name'] + '\n' + backend.KINDS[entry['kind']] + ' · ' + entry['category'])
            item.setData(Qt.ItemDataRole.UserRole, entry); self.results.addItem(item)
            if entry['kind']=='web':
                from webapp_icons import request_refresh
                item.setIcon(QIcon(str(web.icon_path(entry))));request_refresh(entry['url'])
            if previous and entry['id'] == previous['id']: selected = index
        self.count.setText(f'{len(matches)} resultados no catálogo selecionado. O Discover consulta outras opções nas fontes configuradas.')
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
        local_command = backend.native_launch(item)
        for button in (self.primary, self.website, self.installer): button.setVisible(bool(item))
        self.manage_native.setVisible(bool(local_command))
        self.new_session.setVisible(bool(item and item['kind'] == 'web' and web.status(item)['installed']))
        if not item:
            self.heading.setText('Nenhum resultado'); self.description.setText('Tente outro termo ou pesquise mais no Discover.')
            self.note.clear(); self.source.clear(); return
        self.heading.setText(item['name']); self.description.setText(item['description'])
        self.note.setText(item.get('note', 'A instalação, a origem e as atualizações são gerenciadas pelo Discover.'))
        if local_command:
            self.note.setText(self.note.text() + '\n\nVocê pode abrir este aplicativo diretamente. Para atualizar ou remover, use Gerenciar instalação no Discover.')
        self.source.setText('Fonte: ' + item['source'])
        label = {'linux': 'Encontrar / instalar no Discover', 'web': 'Instalar aplicativo web…', 'windows': 'Baixar instalador no site oficial'}[item['kind']]
        if item['kind'] == 'web' and web.status(item)['installed']: label = 'Abrir aplicativo web'
        elif local_command: label = 'Abrir aplicativo'
        self.primary.setText(label); self.installer.setVisible(item['kind'] == 'windows')

    def run(self, argv):
        try:
            subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error: QMessageBox.warning(self, 'Não foi possível abrir', str(error))

    def activate(self):
        item = self.selected()
        if not item: return
        try:
            if item['kind'] == 'web' and web.status(item)['installed']:
                self.run(['linuxbr-webapps', '--open-site', web.normalize_offer(item)['url']])
            else:
                # Recheck at click time: a package may have been removed in Discover.
                self.run(backend.native_launch(item) or backend.action(item))
        except (OSError, ValueError) as error: QMessageBox.warning(self, 'Não foi possível abrir', str(error))

    def open_source(self):
        item = self.selected()
        if item:
            try: self.run(['xdg-open', web.clean_url(item['source'])])
            except ValueError as error: QMessageBox.warning(self, 'Endereço inválido', str(error))

    def discover(self):
        self.run(['plasma-discover', '--search', self.query.text().strip()] if self.query.text().strip() else ['plasma-discover'])

    def manage_linux(self):
        item = self.selected()
        if item and item['kind'] == 'linux':
            self.run(backend.action(item))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.ActivationChange and self.isActiveWindow() and hasattr(self, 'results'): self.select()


if __name__ == '__main__':
    app = QApplication(sys.argv); app.setDesktopFileName('linuxbr-store'); app.setStyleSheet(BUTTONS)
    window = Window(); window.show(); sys.exit(app.exec())
