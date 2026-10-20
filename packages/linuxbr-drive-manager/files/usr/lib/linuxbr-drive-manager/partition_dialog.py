"""Explicit, reviewable plans before UDisks requests administrator authorization."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, QComboBox,
                            QSpinBox, QCheckBox, QDialogButtonBox, QLineEdit)
from partitioning import MIB, FORMATS, plan

TITLES = dict(create='Criar partição', delete='Excluir partição', format='Formatar partição', resize='Redimensionar partição')


class PartitionDialog(QDialog):
    def __init__(self, row, action, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLES[action]); self.resize(540, 350)
        self.row = row; self.action = action; self.disk = row['partition_disk']
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 24, 24, 24)
        summary = QLabel(f"{TITLES[action]}\nDisco: {self.disk['device']} ({self.disk['scheme'].upper()})\n"
                         f"Volume: {row.get('device') or row['name']}\nTamanho atual: {row['size']/MIB:.0f} MiB")
        summary.setTextFormat(Qt.TextFormat.PlainText); summary.setWordWrap(True); layout.addWidget(summary)
        form = QFormLayout(); layout.addLayout(form)
        self.size = QSpinBox(); self.size.setSuffix(' MiB'); self.size.setRange(32, 2147483647)
        if action == 'create': maximum = row['size']//MIB
        elif action == 'resize':
            end = min([p['start'] for p in self.disk['parts'] if p['start'] > row['offset']] + [self.disk['end']])
            maximum = (end-row['offset'])//MIB
        else: maximum = max(32, row['size']//MIB)
        self.size.setMaximum(min(maximum, 2147483647)); self.size.setValue(min(row['size']//MIB, 2147483647))
        if action in ('create', 'resize'): form.addRow('Novo tamanho:', self.size)
        self.format = QComboBox(); self.format.addItems(FORMATS)
        if action in ('create', 'format'): form.addRow('Sistema de arquivos:', self.format)
        explanation = ('Todos os arquivos desta partição serão perdidos.' if action in ('delete', 'format') else
                       'Será criada e formatada uma partição no espaço selecionado.' if action == 'create' else
                       'Faça backup antes de continuar. A operação move dados e não deve ser interrompida. '
                       'Antes de redimensionar, o ext4 será verificado e preparado com gravação de metadados. '
                       'Se a verificação inicial encontrar erros, a operação será bloqueada. '
                       'O tamanho mínimo real será verificado pela ferramenta ext4; não é calculado apenas pelo espaço usado.')
        note = QLabel(explanation); note.setWordWrap(True); layout.addWidget(note)
        self.typed = QLineEdit()
        if action in ('delete', 'format'):
            form.addRow(f'Digite {row["device"]} para confirmar:', self.typed)
        self.confirm = QCheckBox('Revisei o dispositivo e confirmo esta alteração.'); layout.addWidget(self.confirm)
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.apply = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply.setText(TITLES[action]); self.apply.setEnabled(False); self.apply.setAutoDefault(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        buttons.rejected.connect(self.reject); self.apply.clicked.connect(self.accept)
        layout.addWidget(buttons)
        for signal in (self.confirm.toggled, self.typed.textChanged, self.size.valueChanged, self.format.currentTextChanged):
            signal.connect(self.validate)
        self.validate()

    def request(self):
        return dict(action=self.action, disk=self.disk['path'], token=self.disk['token'],
                    path=self.row['path'], start=self.row.get('offset', 0), size=self.size.value()*MIB,
                    format=self.format.currentText())

    def validate(self, *args):
        try:
            plan(self.disk, self.request())
            valid = self.confirm.isChecked() and (self.action not in ('delete', 'format') or self.typed.text() == self.row['device'])
            self.error.setText(''); self.apply.setEnabled(valid)
        except ValueError as error:
            self.error.setText(str(error)); self.apply.setEnabled(False)
