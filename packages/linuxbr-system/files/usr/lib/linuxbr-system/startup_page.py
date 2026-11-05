"""Startup application controls and related administration entry points."""
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from desktop_jobs import Query
import startup_backend as backend


class Startup(QWidget):
    def __init__(self):
        super().__init__()
        self.jobs = set()
        layout = QVBoxLayout(self)
        title = QLabel('Programas de inicialização')
        title.setStyleSheet('font-size:26px;font-weight:600')
        layout.addWidget(title)
        note = QLabel('Controle os aplicativos que iniciam ao entrar na sua conta. As mudanças valem no próximo login e não encerram programas em execução. Serviços e tarefas agendadas têm controles próprios abaixo.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Pesquisar nome, comando ou origem')
        self.search.textChanged.connect(self.filter)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Aplicativo', 'Inicialização', 'Origem', 'Comando'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.selection)
        layout.addWidget(self.table, 1)
        self.detail = QLabel('Selecione um aplicativo para consultar sua origem.')
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.detail)
        row = QHBoxLayout()
        location=QPushButton(QIcon.fromTheme('folder-open'),'Abrir pasta da entrada');location.clicked.connect(self.open_location);row.addWidget(location)
        self.controls = []
        for title, icon, operation in [('Habilitar', 'dialog-ok-apply', True),
                                       ('Desabilitar', 'dialog-cancel', False),
                                       ('Desfazer última alteração', 'edit-undo', None)]:
            button = QPushButton(QIcon.fromTheme(icon), title)
            button.clicked.connect(lambda _, value=operation: self.change(value))
            row.addWidget(button)
            self.controls.append(button)
        self.refresh_button = QPushButton(QIcon.fromTheme('view-refresh'), 'Atualizar')
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        related = QHBoxLayout()
        for title, icon, argv in [('Adicionar aplicativo ou script…', 'list-add', ['/usr/bin/kcmshell6', 'kcm_autostart']),
                                  ('Serviços', 'preferences-system-services', ['linuxbr-system', '--page', 'services']),
                                  ('Tarefas agendadas', 'appointment-new', ['linuxbr-system', '--page', 'scheduler'])]:
            button = QPushButton(QIcon.fromTheme(icon), title)
            button.clicked.connect(lambda _, command=argv: self.launch(command))
            related.addWidget(button)
        layout.addLayout(related)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.refresh()

    def query(self, callback, done):
        job = Query(callback, self)
        self.jobs.add(job)
        self.refresh_button.setEnabled(False)
        self.selection()
        job.result.connect(done)
        job.failed.connect(self.status.setText)
        job.finished.connect(lambda: self.jobs.discard(job))
        job.finished.connect(lambda: self.refresh_button.setEnabled(not self.jobs))
        job.finished.connect(self.selection)
        job.finished.connect(job.deleteLater)
        job.start()

    def refresh(self):
        if not self.jobs:
            self.status.setText('Consultando a inicialização da sua conta…')
            self.query(backend.inventory, self.loaded)

    def loaded(self, rows):
        self.table.setRowCount(0)
        for row in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            for column, key in enumerate(('name', 'status', 'origin', 'command')):
                item = QTableWidgetItem(row.get(key, ''))
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.table.setItem(index, column, item)
        self.filter()
        self.selection()
        self.status.setText(f'{len(rows)} entradas de aplicativos encontradas. O impacto no desempenho ainda não foi medido.')

    def filter(self):
        query = self.search.text().casefold()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, query not in ' '.join(self.table.item(row, column).text() for column in range(4)).casefold())

    def selected(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selection(self):
        row = self.selected()
        for button in self.controls:
            button.setEnabled(bool(row and row['editable'] and not row['protected'] and not self.jobs))
        self.detail.setText((row['path']+('\n'+row.get('description','') if row.get('description') else '')+('\nFornecedor declarado: '+row['vendor'] if row.get('vendor') else '') + ('\nComponente necessário para a sessão e autenticação.' if row['protected'] else '')) if row else 'Selecione um aplicativo para consultar sua origem.')

    def open_location(self):
        from pathlib import Path
        row=self.selected()
        if row:self.launch(['/usr/bin/xdg-open',str(Path(row['path']).parent)])

    def change(self, enabled):
        row = self.selected()
        if not row or self.jobs:
            return
        title = 'Restaurar a configuração anterior' if enabled is None else 'Habilitar no login' if enabled else 'Desabilitar no login'
        if QMessageBox.question(self, title, title + ': ' + row['name'] + '?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        def run():
            message = backend.change(row['id'], row['sha256'], enabled, restore=enabled is None)
            return message, backend.inventory()
        def done(result):
            self.loaded(result[1])
            self.status.setText(result[0])
        self.query(run, done)

    def launch(self, argv):
        if not QProcess.startDetached(argv[0], argv[1:])[0]:
            self.status.setText('Não foi possível abrir a ferramenta solicitada.')
