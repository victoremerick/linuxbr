"""Preview batch changes in the file tools dialog."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from batch_rename_backend import apply_plan, plan
from file_workflows_backend import State


class BatchRename(QDialog):
    def __init__(self, items):
        super().__init__()
        self.items = list(dict.fromkeys(Path(item).absolute() for item in items))
        self.rows = []
        self.setWindowTitle('Renomear em lote')
        self.resize(780, 500)
        body = QVBoxLayout(self)
        help_text = QLabel('Monte o novo nome e confira a prévia antes de aplicar. As extensões são mantidas.')
        help_text.setWordWrap(True)
        body.addWidget(help_text)
        form = QFormLayout()
        self.pattern = QLineEdit('{nome}')
        self.find = QLineEdit()
        self.replace = QLineEdit()
        for label, field in [('Novo &nome', self.pattern), ('&Localizar no nome', self.find), ('Substituir &por', self.replace)]:
            form.addRow(label, field)
            field.textChanged.connect(self.refresh)
        body.addLayout(form)
        self.replace.setEnabled(False)
        self.find.textChanged.connect(lambda value: self.replace.setEnabled(bool(value)))
        inserts = QHBoxLayout()
        inserts.addWidget(QLabel('Inserir no nome'))
        for title, token in [('Nome original', '{nome}'), ('Data de alteração', '{data}'), ('Número', '{n}')]:
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _=False, value=token: self.insert_token(value))
            inserts.addWidget(button)
        inserts.addStretch()
        body.addLayout(inserts)
        self.table = QTableWidget(0, 3)
        self.table.setAccessibleName('Prévia dos novos nomes')
        self.table.verticalHeader().hide()
        self.table.setHorizontalHeaderLabels(['Nome atual', 'Novo nome', 'Situação'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        body.addWidget(self.table)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        for button in buttons.buttons():
            button.setAutoDefault(False)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons)
        self.refresh()
        self.pattern.setFocus()

    def insert_token(self, token):
        self.pattern.insert(token)
        self.pattern.setFocus()

    def refresh(self):
        try:
            self.rows = plan(self.items, self.pattern.text(), self.find.text(), self.replace.text())
        except (OSError, ValueError) as error:
            self.rows = []
            self.status.setText(str(error))
            conflicts = 0
        else:
            conflicts = sum(bool(status and status != 'Sem alteração') for _, _, _, status in self.rows)
            self.status.setText(
                f'Corrija os conflitos indicados na tabela ({conflicts}).' if conflicts
                else 'Altere o novo nome para ver a prévia.' if all(status for _, _, _, status in self.rows)
                else 'Confira os novos nomes antes de aplicar.'
            )
        self.table.setRowCount(len(self.rows))
        for row, (source, target, _, status) in enumerate(self.rows):
            for column, value in enumerate((source.name, target.name if target else '', status or 'Disponível')):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        count = sum(not status for _, _, _, status in self.rows)
        self.apply_button.setText(f'Renomear {count} itens' if count != 1 else 'Renomear 1 item')
        self.apply_button.setEnabled(count > 0 and conflicts == 0)

    def apply(self):
        if not self.apply_button.isEnabled():
            return
        try:
            apply_plan(self.rows, on_commit=lambda changes: State().remember('Renomeação', changes))
        except ValueError as error:
            QMessageBox.warning(self, 'Renomeação não concluída', str(error))
            self.refresh()
        else:
            self.accept()
