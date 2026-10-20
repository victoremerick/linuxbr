#!/usr/bin/python3
"""Linux BR Drive Manager — Qt UI, asynchronous storage operations."""
import json
import sys
from pathlib import Path
from PyQt6.QtCore import QProcess, QTimer, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QIcon, QAction
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QInputDialog, QToolBar, QMenu, QFrame, QSplitter, QProgressBar)
from diskmap import DiskMap
from partition_dialog import PartitionDialog, TITLES
from core import LETTERS
from client import ServiceStore
from properties import Properties, usage_widget


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Gerenciamento de discos — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('linuxbr-files'))
        self.resize(1040, 620)
        self.setMinimumSize(640, 480)
        self.store = ServiceStore()
        self.rows = []
        self.process = None
        self.operation_progress = QProgressBar()
        self.operation_progress.setRange(0, 0); self.operation_progress.setFixedWidth(140)
        self.operation_progress.setAccessibleName('Operação de particionamento em andamento')
        self.statusBar().addPermanentWidget(self.operation_progress); self.operation_progress.hide()
        self.data = dict(letters={}, shares={})
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 20)
        title = QLabel('Gerenciamento de discos')
        title.setStyleSheet('font-size: 26px; font-weight: 600;')
        layout.addWidget(title)
        layout.addWidget(QLabel('Volumes, partições e unidades de rede'))
        toolbar = QToolBar('Ações de armazenamento', self)
        toolbar.setMovable(False); toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.buttons = {}
        actions = [('Atualizar', 'view-refresh', self.refresh), ('Abrir', 'document-open', self.open_selected),
                   ('Propriedades', 'document-properties', self.show_properties),
                   ('Montar', 'media-mount', lambda: self.operate('mount')),
                   ('Desmontar', 'media-eject', lambda: self.operate('unmount')),
                   ('Alterar letra', 'edit-rename', self.change_letter),
                   ('Reservas', 'drive-harddisk', self.reservations),
                   ('Adicionar rede', 'list-add', self.add_share), ('Remover rede', 'list-remove', self.remove_share)]
        unit_menu = QMenu('Gerenciar unidade', toolbar)
        network_menu = QMenu('Rede', toolbar)
        for name, icon, callback in actions:
            action = QAction(QIcon.fromTheme(icon), name, self); action.triggered.connect(callback)
            self.buttons[name] = action
            if name in ('Atualizar', 'Abrir', 'Propriedades'): toolbar.addAction(action)
            elif name in ('Adicionar rede', 'Remover rede'): network_menu.addAction(action)
            else: unit_menu.addAction(action)
        toolbar.addSeparator(); toolbar.addAction(unit_menu.menuAction()); toolbar.addAction(network_menu.menuAction())
        partition_menu = QMenu('Partições', toolbar)
        self.partition_actions = {}
        for operation, title in TITLES.items():
            action = QAction(title + '…', self)
            action.triggered.connect(lambda checked=False, op=operation: self.edit_partition(op))
            partition_menu.addAction(action); self.partition_actions[operation] = action
        toolbar.addAction(partition_menu.menuAction())
        layout.addWidget(toolbar)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Unidade', 'Nome', 'Tipo', 'Capacidade', 'Formato', 'Local / estado', 'Espaço usado / livre'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.cellDoubleClicked.connect(self.open_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.volume_menu)
        self.diskmap = DiskMap()
        self.diskmap.selected.connect(self.table.selectRow)
        self.diskmap.context_requested.connect(self.map_menu)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.diskmap)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([260, 280])
        layout.addWidget(self.splitter)
        note = QLabel('As letras também aparecem em Este computador no Explorador de arquivos. As montagens continuam sendo gerenciadas pelo Linux.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def error(self, text):
        QMessageBox.warning(self, 'Drive Manager', text)

    def selected(self):
        i = self.table.currentRow()
        return self.rows[i] if 0 <= i < len(self.rows) else None

    def selection_changed(self):
        row = self.selected() or {}
        self.diskmap.select(self.table.currentRow())
        idle = self.process is None
        for button in self.buttons.values(): button.setEnabled(idle)
        self.buttons['Propriedades'].setEnabled(idle and bool(row) and not row.get('unallocated'))
        self.buttons['Abrir'].setEnabled(idle and bool(row.get('mounts') or row.get('url')))
        self.buttons['Montar'].setEnabled(idle and bool(row.get('mountable')) and not row.get('mounts'))
        self.buttons['Desmontar'].setEnabled(idle and bool(row.get('mountable')) and bool(row.get('mounts')))
        self.buttons['Alterar letra'].setEnabled(idle and bool(row.get('key')) and row.get('key') != 'system' and not row.get('protected'))
        self.buttons['Remover rede'].setEnabled(idle and bool(row.get('url')))
        disk = row.get('partition_disk', {})
        editable = idle and bool(disk) and not disk.get('reason')
        for operation, action in self.partition_actions.items():
            allowed = bool(row.get('unallocated')) if operation == 'create' else bool(row.get('parent')) and not row.get('unallocated')
            if operation == 'resize': allowed = allowed and row.get('fs') == 'ext4'
            action.setEnabled(editable and allowed)
            action.setToolTip(disk.get('reason') or ('Requer partição ext4 desmontada.' if operation == 'resize' else 'Selecione uma partição ou espaço não alocado.'))

    def worker(self, args, callback):
        if self.process is not None: return
        process = QProcess(self)
        self.process = process
        self.operation_progress.setVisible(args[0] == 'partition')
        self.selection_changed()
        self.statusBar().showMessage('Consultando armazenamento…' if args[0] == 'list' else 'Aguardando operação e autorização do sistema…')
        def done(code, status):
            self.process = None
            self.operation_progress.hide()
            try:
                payload = json.loads(bytes(process.readAllStandardOutput()).decode())
                if code or 'error' in payload: raise ValueError(payload.get('error', 'Operação não concluída.'))
                callback(payload['result'])
            except (ValueError, OSError, KeyError) as error:
                self.statusBar().showMessage(str(error))
                if args[0] != 'list': self.error(str(error))
                if args[0] == 'partition': QTimer.singleShot(0, self.refresh)
            finally:
                process.deleteLater()
                self.selection_changed()
        process.finished.connect(done)
        def failed(error):
            if error == QProcess.ProcessError.FailedToStart:
                self.process = None
                self.operation_progress.hide()
                self.statusBar().showMessage('Não foi possível iniciar o serviço de consulta.')
                process.deleteLater()
                self.selection_changed()
        process.errorOccurred.connect(failed)
        script = 'client.py' if args[0] == 'list' else 'backend.py'
        process.start(sys.executable, [str(Path(__file__).with_name(script)), *args])

    def refresh(self):
        if self.process is not None: return
        self.worker(['list'], self.populate)

    def populate(self, rows):
        service_error = ''
        service_data = None
        if isinstance(rows, dict):
            service_data = rows['data']
            service_error = rows.get('error', '')
            rows = rows['rows']
        rows = [dict(row) for row in rows if not row.get('unallocated')]
        current = self.selected()
        selected_id = (current.get('key'), current.get('path')) if current else None
        self.data = service_data if service_data is not None else self.store.discover(rows)
        for url, label in self.data['shares'].items():
            rows.append(dict(key='smb:' + url, name=label, kind='Rede SMB', url=url,
                             size=0, fs='', mounts=[], path=''))
        for disk_row in list(rows):
            disk = disk_row.get('partition_disk')
            if not disk or disk_row.get('path') != disk['path']: continue
            for gap in disk['gaps']:
                rows.append(dict(key='', name='Não alocado', kind='Espaço livre', size=gap['size'], fs='', mounts=[],
                                 device=disk['device'], path=f"free:{disk['path']}:{gap['start']}", parent=disk['path'],
                                 offset=gap['start'], unallocated=True, partition_disk=disk, protected=True))
        self.rows = rows
        self.diskmap.populate(rows, self.data['letters'])
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            hidden = bool(row.get('is_disk') and any(v.get('parent') == row.get('path') and v.get('parent') for v in rows))
            letter = 'C' if row['key'] == 'system' else self.data['letters'].get(row['key'], '')
            size = f"{row['size'] / 1024**3:.1f} GiB" if row['size'] else '—'
            location = 'Disponível para nova partição' if row.get('unallocated') else row.get('url') or ', '.join(row['mounts']) or row.get('device', '') + ' · não montado'
            values = [letter + ':' if letter else '—', row['name'], row['kind'], size, row['fs'] or '—', location]
            for j, value in enumerate(values): self.table.setItem(i, j, QTableWidgetItem(value))
            if not hidden:
                self.table.setCellWidget(i, 6, QLabel('—') if row.get('unallocated') else usage_widget(row))
            self.table.setRowHidden(i, hidden)
            icon = 'folder-network' if row.get('url') else 'drive-removable-media' if row['kind'] == 'Removível' else 'drive-harddisk'
            self.table.item(i, 0).setIcon(QIcon.fromTheme(icon))
            if selected_id == (row.get('key'), row.get('path')): self.table.selectRow(i)
        self.table.blockSignals(False)
        self.statusBar().showMessage(service_error or f'{len(rows)} itens · serviço de unidades ativo · integração com o Explorador de arquivos')
        self.selection_changed()

    def volume_menu(self, position):
        index = self.table.indexAt(position)
        if not index.isValid(): return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        for name in ('Abrir', 'Propriedades', 'Montar', 'Desmontar', 'Alterar letra'):
            menu.addAction(self.buttons[name])
        menu.addSeparator()
        for action in self.partition_actions.values(): menu.addAction(action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def map_menu(self, index, position):
        self.table.selectRow(index)
        menu = QMenu(self)
        for action in self.partition_actions.values(): menu.addAction(action)
        menu.addSeparator(); menu.addAction(self.buttons['Propriedades'])
        menu.exec(position)

    def edit_partition(self, operation):
        row = self.selected()
        if self.process is not None or not row or not row.get('partition_disk'): return
        self.timer.stop()
        try:
            dialog = PartitionDialog(dict(row), operation, self)
            if dialog.exec() == dialog.DialogCode.Accepted:
                self.worker(['partition', json.dumps(dialog.request())], self.partition_done)
        finally:
            self.timer.start(5000)

    def partition_done(self, result):
        QMessageBox.information(self, 'Gerenciamento de discos', str(result))
        self.refresh()

    def show_properties(self):
        row = self.selected()
        if not row: return
        letter = 'C' if row['key'] == 'system' else self.data['letters'].get(row['key'], '')
        dialog = Properties(dict(row), letter, self)
        dialog.exec()

    def open_selected(self, *args):
        row = self.selected()
        if not row: return
        url = QUrl(row['url']) if row.get('url') else QUrl.fromLocalFile(row['mounts'][0]) if row.get('mounts') else None
        if url is not None and not QDesktopServices.openUrl(url): self.error('Não foi possível abrir o gerenciador de arquivos.')

    def operate(self, operation):
        row = self.selected()
        if not row or not row.get('mountable'): return
        self.worker([operation, row['path'], row['key'], row['device']], lambda result: self.refresh())

    def change_letter(self):
        row = self.selected()
        if not row or not row['key'] or row['key'] == 'system': return
        available = [c for c in LETTERS if c not in self.data['letters'].values() or self.data['letters'].get(row['key']) == c]
        letter, ok = QInputDialog.getItem(self, 'Letra da unidade', 'Escolha uma letra:', available, editable=False)
        if ok:
            try: self.store.assign(row['key'], letter); self.refresh()
            except (ValueError, OSError) as error: self.error(str(error))

    def add_share(self):
        url, ok = QInputDialog.getText(self, 'Adicionar compartilhamento', 'Endereço: smb://servidor/compartilhamento')
        if not ok: return
        label, ok = QInputDialog.getText(self, 'Nome do compartilhamento', 'Nome para exibição:')
        if not ok: return
        try: self.store.add_share(url, label); self.refresh()
        except (ValueError, OSError) as error: self.error(str(error))

    def remove_share(self):
        row = self.selected()
        if row and row.get('url'):
            try: self.store.forget(row['key']); self.refresh()
            except (ValueError, OSError) as error: self.error(str(error))

    def reservations(self):
        active = {r['key'] for r in self.rows}
        entries = {f'{v}: — {k}': k for k, v in self.data['letters'].items() if k not in active}
        if not entries:
            QMessageBox.information(self, 'Reservas', 'Nenhuma unidade desconectada tem letra reservada.')
            return
        value, ok = QInputDialog.getItem(self, 'Liberar letra reservada', 'Selecione a reserva a remover:', sorted(entries), editable=False)
        if ok:
            try: self.store.forget(entries[value]); self.refresh()
            except (ValueError, OSError) as error: self.error(str(error))

    def closeEvent(self, event):
        if self.process is not None:
            self.statusBar().showMessage('Aguarde a operação terminar antes de fechar.')
            event.ignore()
        else: event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('Linux BR Drive Manager')
    window = Window()
    window.show()
    sys.exit(app.exec())
