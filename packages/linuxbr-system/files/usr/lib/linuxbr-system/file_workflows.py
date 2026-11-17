"""Explorer tools opened from the ribbon and the file manager's context menu."""
from datetime import date, datetime, time, timedelta
from pathlib import Path
import os

from PyQt6.QtCore import QStorageInfo, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit, QListWidget, QListWidgetItem,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from batch_rename_backend import apply_plan
from desktop_jobs import Query
from file_tools import message, plain_label
from file_workflows_backend import State, checked_root, compare_folders, find_files, names_to_review, verified_copy


def local_path(value):
    url = QUrl(value)
    if url.isLocalFile():
        return url.toLocalFile()
    return value if value.startswith('/') else ''


def local_selection(values):
    return [Path(path) for value in values if (path := local_path(value))]


def button(text, icon, callback):
    control = QPushButton(QIcon.fromTheme(icon), text)
    control.setAutoDefault(False)
    control.clicked.connect(callback)
    return control


def confirm(parent, title, question, details):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(680, 330)
    layout = QVBoxLayout(dialog)
    layout.addWidget(plain_label(question))
    review = QPlainTextEdit('\n'.join(details))
    review.setReadOnly(True)
    layout.addWidget(review, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
    accept = buttons.addButton('Confirmar', QDialogButtonBox.ButtonRole.AcceptRole)
    accept.setAutoDefault(False)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return dialog.exec() == QDialog.DialogCode.Accepted


class WorkDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(750, 525)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.status = plain_label('')
        self.worker = None
        self.controls = QWidget(self)
        self.layout = QVBoxLayout(self.controls)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(self.controls, 1)
        self.body.addWidget(self.status)
        close = button('Fechar', 'window-close', self.reject)
        self.body.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def run(self, callback, complete):
        if self.worker is not None:
            return
        self.controls.setEnabled(False)
        self.status.setText('Operação em andamento…')
        task = Query(callback, self)
        self.worker = task
        task.result.connect(complete)
        task.failed.connect(self.status.setText)
        task.finished.connect(self.finished)
        task.start()

    def finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.controls.setEnabled(True)

    def reject(self):
        if self.worker is None:
            super().reject()

    def closeEvent(self, event):
        if self.worker is None:
            super().closeEvent(event)
        else:
            event.ignore()


def folder_field(parent, value):
    row = QHBoxLayout()
    field = QLineEdit(value)
    field.setPlaceholderText('Selecione o caminho da pasta')
    row.addWidget(field)

    def choose():
        location = QFileDialog.getExistingDirectory(parent, 'Escolher pasta', field.text() or str(Path.home()))
        if location:
            field.setText(location)

    row.addWidget(button('Procurar…', 'folder-open', choose))
    return row, field


class Comparison(WorkDialog):
    def __init__(self, folders, parent=None):
        super().__init__('Comparar pastas', parent)
        form = QFormLayout()
        self.folders = []
        for index, label in enumerate(('&Primeira pasta', '&Segunda pasta')):
            row, field = folder_field(self, local_path(folders[index]) if index < len(folders) else '')
            self.folders.append(field)
            form.addRow(label, row)
        self.checksum = QCheckBox('Conferir conteúdo por SHA-256')
        form.addRow(self.checksum)
        self.layout.addLayout(form)
        self.layout.addWidget(button('Comparar', 'document-preview', self.compare),
                              alignment=Qt.AlignmentFlag.AlignLeft)
        self.results = QTableWidget(0, 2)
        self.results.setHorizontalHeaderLabels(['Arquivo', 'Diferença'])
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.layout.addWidget(self.results, 1)

    def compare(self):
        first, second = (field.text().strip() for field in self.folders)
        reference = self.checksum.isChecked()
        self.results.setRowCount(0)
        self.run(lambda: compare_folders(first, second, reference), self.show_results)

    def show_results(self, rows):
        self.results.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.results.setItem(index, column, item)
        self.status.setText(f'{len(rows)} arquivos com diferenças.' if rows else 'Nenhuma diferença encontrada.')


class Searches(WorkDialog):
    def __init__(self, folder, parent=None):
        super().__init__('Consultas salvas', parent)
        self.state = State()
        self.saved = QComboBox()
        self.saved.setAccessibleName('Consulta salva')
        self.saved.currentTextChanged.connect(self.load)
        self.name = QLineEdit()
        self.roots = QPlainTextEdit(local_path(folder))
        self.roots.setPlaceholderText('Um caminho por linha')
        self.roots.setMaximumHeight(90)
        self.filters = {}
        form = QFormLayout()
        form.addRow('Consulta salva', self.saved)
        form.addRow('&Nome da consulta', self.name)
        root_box = QVBoxLayout()
        root_box.addWidget(self.roots)
        root_box.addWidget(button('Adicionar pasta…', 'folder-new', self.add_folder),
                           alignment=Qt.AlignmentFlag.AlignLeft)
        form.addRow('&Pastas da pesquisa', root_box)
        for key, label, placeholder in (
                ('pattern', '&Nome do arquivo', 'Ex.: *.relatório*'),
                ('extension', '&Extensão', 'Ex.: pdf'),
                ('minimum', 'Tamanho &mínimo em bytes', 'Ex.: 1024'),
                ('maximum', 'Tamanho má&ximo em bytes', 'Ex.: 1048576'),
                ('from_date', 'Modificado a &partir de', 'AAAA-MM-DD'),
                ('to_date', 'Modificado &até', 'AAAA-MM-DD')):
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            self.filters[key] = field
            form.addRow(label, field)
        self.layout.addLayout(form)
        actions = QHBoxLayout()
        actions.addWidget(button('Pesquisar', 'edit-find', self.search))
        actions.addWidget(button('Salvar consulta', 'document-save', self.save))
        actions.addWidget(button('Remover consulta', 'edit-delete', self.remove))
        actions.addStretch()
        self.layout.addLayout(actions)
        self.results = QListWidget(self)
        self.results.setAccessibleName('Arquivos encontrados')
        self.results.itemActivated.connect(lambda item: QDesktopServices.openUrl(QUrl.fromLocalFile(item.text())))
        self.layout.addWidget(self.results, 1)
        self.refresh()

    def add_folder(self):
        location = QFileDialog.getExistingDirectory(self, 'Adicionar pasta', str(Path.home()))
        if location:
            self.roots.appendPlainText(location)

    def refresh(self, selected=''):
        self.saved.blockSignals(True)
        self.saved.clear()
        self.saved.addItem('')
        self.saved.addItems(sorted(self.state.read().get('searches', {})))
        self.saved.setCurrentText(selected)
        self.saved.blockSignals(False)

    def load(self, label):
        data = self.state.read().get('searches', {}).get(label)
        if data is None:
            return
        self.name.setText(label)
        self.roots.setPlainText('\n'.join(data['roots']))
        for key, field in self.filters.items():
            field.setText(data.get(key, ''))

    def criteria(self):
        roots = [line.strip() for line in self.roots.toPlainText().splitlines() if line.strip()]
        if not roots:
            raise ValueError('Adicione pelo menos uma pasta à pesquisa.')
        data = {'roots': roots, **{key: field.text().strip() for key, field in self.filters.items()}}
        minimum, maximum = (int(data[key]) if data[key] else None for key in ('minimum', 'maximum'))
        if (any(value is not None and value < 0 for value in (minimum, maximum))
                or (minimum is not None and maximum is not None and minimum > maximum)):
            raise ValueError('Informe tamanhos válidos e confira a ordem dos limites.')
        first, last = (date.fromisoformat(data[key]) if data[key] else None for key in ('from_date', 'to_date'))
        if first and last and first > last:
            raise ValueError('A data inicial deve vir antes da data final.')
        start = datetime.combine(first, time()).timestamp() if first else None
        end = datetime.combine(last + timedelta(days=1), time()).timestamp() if last else None
        return data, (roots, data['pattern'], data['extension'], minimum, maximum, start, end)

    def search(self):
        try:
            _, arguments = self.criteria()
        except (ValueError, OverflowError) as error:
            self.status.setText(str(error))
            return
        self.results.clear()
        self.run(lambda: find_files(*arguments), self.show_results)

    def save(self):
        try:
            data, _ = self.criteria()
            label = self.name.text().strip()
            if not label or len(label) > 80:
                raise ValueError('Informe um nome de até 80 caracteres para a consulta.')
            with self.state.update() as value:
                value.setdefault('searches', {})[label] = data
            self.refresh(label)
            self.status.setText('Consulta salva.')
        except (ValueError, OSError, OverflowError) as error:
            self.status.setText(str(error))

    def remove(self):
        label = self.saved.currentText()
        if not label or not confirm(self, 'Remover consulta', 'Exclua a consulta salva selecionada.', [label]):
            return
        try:
            with self.state.update() as value:
                value.setdefault('searches', {}).pop(label, None)
            self.refresh()
            self.status.setText('Consulta removida.')
        except (ValueError, OSError) as error:
            self.status.setText(str(error))

    def show_results(self, result):
        paths, truncated = result
        self.results.addItems([str(path) for path in paths])
        self.status.setText(f'{len(paths)} arquivos encontrados.' +
                            (' Refine os filtros para consultar os demais.' if truncated else ''))


class Tags(WorkDialog):
    def __init__(self, items, parent=None):
        super().__init__('Etiquetas de projeto', parent)
        self.items = items
        self.state = State()
        self.tag = QComboBox()
        self.tag.setEditable(True)
        self.tag.setAccessibleName('Etiqueta de projeto')
        self.tag.currentTextChanged.connect(self.show_items)
        self.layout.addWidget(plain_label('Selecione uma etiqueta para acessar os arquivos do projeto.'))
        self.layout.addWidget(self.tag)
        commands = QHBoxLayout()
        apply = button('Marcar arquivos selecionados', 'tag-new', self.apply)
        apply.setEnabled(bool(items))
        commands.addWidget(apply)
        commands.addWidget(button('Remover marcação dos itens', 'edit-delete', self.remove))
        commands.addStretch()
        self.layout.addLayout(commands)
        self.results = QListWidget()
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results.itemActivated.connect(self.open_file)
        self.layout.addWidget(self.results, 1)
        self.refresh()

    def refresh(self, selected=''):
        self.tag.blockSignals(True)
        self.tag.clear()
        self.tag.addItems(sorted(self.state.read().get('tags', {})))
        if selected:
            self.tag.setCurrentText(selected)
        self.tag.blockSignals(False)
        self.show_items(self.tag.currentText())

    def show_items(self, label):
        if not hasattr(self, 'results'):
            return
        self.results.clear()
        try:
            items = self.state.read().get('tags', {}).get(label, [])
            for path in items:
                row = QListWidgetItem(path)
                self.results.addItem(row)
            self.status.setText(f'{len(items)} itens marcados.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def apply(self):
        try:
            label = self.tag.currentText().strip()
            self.state.set_tag(label, self.items, add=True)
            self.refresh(label)
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def remove(self):
        try:
            label = self.tag.currentText().strip()
            self.state.set_tag(label, [item.text() for item in self.results.selectedItems()], add=False)
            self.refresh(label)
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def open_file(self, item):
        path = Path(item.text())
        if not path.exists():
            self.status.setText('Esse item não está disponível. Confira se ele foi movido ou se a unidade está conectada.')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class Transfer(WorkDialog):
    def __init__(self, items, folder, parent=None):
        super().__init__('Cópia verificável e movimentação', parent)
        self.items = items
        self.layout.addWidget(plain_label('Copie arquivos com verificação SHA-256. Para retomar uma cópia interrompida, selecione os mesmos arquivos e a mesma pasta de destino.'))
        self.layout.addWidget(plain_label('Movimentações em lote feitas nesta janela podem ser revertidas pelo histórico.'))
        form = QFormLayout()
        row, self.destination = folder_field(self, local_path(folder))
        form.addRow('&Destino', row)
        self.layout.addLayout(form)
        self.results = QPlainTextEdit('\n'.join(str(item) for item in items))
        self.results.setReadOnly(True)
        self.layout.addWidget(self.results, 1)
        actions = QHBoxLayout()
        for title, icon, move in [('Copiar e verificar', 'edit-copy', False), ('Mover em lote', 'edit-cut', True)]:
            action = button(title, icon, lambda _, value=move: self.transfer(value))
            action.setEnabled(bool(items))
            actions.addWidget(action)
        actions.addStretch()
        self.layout.addLayout(actions)

    def transfer(self, move):
        try:
            destination = checked_root(self.destination.text().strip())
            fs = bytes(QStorageInfo(str(destination)).fileSystemType()).lower()
            if fs in {b'ntfs', b'ntfs3', b'fuseblk', b'vfat', b'exfat', b'cifs', b'smb3', b'msdos'}:
                conflicts = names_to_review(self.items, destination)
                if conflicts:
                    raise ValueError('\n'.join(conflicts))
            changes = []
            targets = set()
            for source in self.items:
                target = destination / source.name
                if ((move and os.path.lexists(target)) or target in targets
                        or destination.is_relative_to(source) or source.parent.resolve() == destination):
                    raise ValueError(f'O destino precisa estar disponível e fora da origem: {target}')
                info = source.lstat()
                if move and info.st_dev != destination.stat().st_dev:
                    raise ValueError('Mover em lote exige origem e destino na mesma unidade. Para copiar entre unidades, use Copiar e verificar.')
                if not move and (not source.is_file() or source.is_symlink()):
                    raise ValueError('A cópia verificável aceita arquivos comuns. Para copiar pastas ou links, use a cópia do Explorador.')
                changes.append((source, target, (info.st_dev, info.st_ino), ''))
                targets.add(target)
            selected = set(self.items)
            if any(selected.intersection(source.parents) for source in self.items):
                raise ValueError('Selecione a pasta ou seus itens em operações separadas.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        title = 'Mover em lote' if move else 'Cópia verificável'
        if not confirm(self, title, 'Revise cada item antes de iniciar.',
                       [f'{source}\n→ {target}' for source, target, _, _ in changes]):
            return

        def operation():
            if move:
                apply_plan(changes, on_commit=lambda completed: State().remember('Movimentação', completed))
                return [f'{source.name} — movido' for source, _, _, _ in changes]
            done = []
            state = State()
            for source, target, _, _ in changes:
                try:
                    checksum = verified_copy(source, target, state)
                except (OSError, ValueError) as error:
                    return done, str(error)
                done.append(f'{source.name}\nSHA-256 {checksum}')
            return done, ''

        def completed(result):
            done, error = (result, '') if move else result
            self.results.setPlainText('\n\n'.join(done))
            self.status.setText(error or 'Operação concluída.')

        self.run(operation, completed)


def undo(parent=None):
    try:
        state = State()
        history = state.read().get('undo', [])
        if not history:
            message(parent, 'Desfazer em lote', 'Ainda não existem operações em lote no histórico.')
            return
        last = history[0]
        details = []
        for source, target, _ in last['changes']:
            conflict = ' (destino ocupado)' if os.path.lexists(source) else ''
            details.append(f'{target}\n→ {source}{conflict}')
        if confirm(parent, 'Desfazer em lote', f'Revise os itens da operação {last["operation"].lower()}.', details):
            state.undo(last)
            message(parent, 'Desfazer em lote', 'Os itens voltaram aos locais anteriores.')
    except (OSError, ValueError) as error:
        message(parent, 'Desfazer em lote', str(error), warning=True)


class Workflows(WorkDialog):
    def __init__(self, folder, selected, parent=None):
        super().__init__('Ferramentas de arquivos', parent)
        items = local_selection(selected)
        self.layout.addWidget(plain_label(f'{len(items)} itens locais selecionados no Explorador.'))
        commands = (
            ('Etiquetas de projeto', 'tag', lambda: Tags(items, self).exec()),
            ('Consultas salvas', 'edit-find', lambda: Searches(folder, self).exec()),
            ('Comparar pastas', 'document-preview', lambda: Comparison([folder], self).exec()),
            ('Cópia verificável ou mover em lote', 'edit-copy', lambda: Transfer(items, folder, self).exec()),
            ('Desfazer em lote', 'edit-undo', lambda: undo(self)),
        )
        for label, icon, callback in commands:
            self.layout.addWidget(button(label, icon, callback))
        self.layout.addStretch()
