"""Open the host's temporary SMB access manager from folder properties."""

import argparse
from datetime import datetime
import json
import sys

from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)


SCOPE = {'read': 'Leitura', 'edit': 'Edição'}
STATE = {'pending': 'Preparação pendente', 'active': 'Ativo', 'revoking': 'Em revogação'}


class ShareGrants(QDialog):
    def __init__(self, folder):
        super().__init__()
        self.setWindowTitle('Acessos temporários a pastas compartilhadas')
        self.setWindowIcon(QIcon.fromTheme('folder-publicshare'))
        self.resize(870, 580)
        self.folder = folder
        self.process = None
        self.entries = []
        body = QVBoxLayout(self)
        description = QLabel('Crie um endereço SMB temporário para uma conta Samba deste computador. '
                             'A pasta já deve estar publicada e a conta precisa das permissões locais correspondentes.')
        description.setWordWrap(True)
        body.addWidget(description)
        form = QFormLayout()
        self.account = QLineEdit()
        self.scope = QComboBox()
        for key, value in SCOPE.items():
            self.scope.addItem(value, key)
        self.minutes = QSpinBox()
        self.minutes.setRange(5, 10080)
        self.minutes.setValue(60)
        self.minutes.setSuffix(' min')
        directory = QLineEdit(folder)
        directory.setReadOnly(True)
        form.addRow('Pasta', directory)
        form.addRow('Conta do Samba', self.account)
        form.addRow('Permissão no endereço temporário', self.scope)
        form.addRow('Validade', self.minutes)
        body.addLayout(form)
        self.create = QPushButton(QIcon.fromTheme('list-add'), 'Criar acesso temporário')
        self.create.clicked.connect(self.issue)
        body.addWidget(self.create, alignment=Qt.AlignmentFlag.AlignLeft)
        self.result = QLineEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText('O endereço será exibido após a criação.')
        self.result.setAccessibleName('Endereço de rede temporário')
        body.addWidget(self.result)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        body.addWidget(self.status)
        body.addWidget(QLabel('Concessões deste computador'))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Pasta', 'Conta', 'Permissão', 'Expira em', 'Endereço SMB', 'Estado'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.controls)
        body.addWidget(self.table, 1)
        toolbar = QHBoxLayout()
        self.refresh = QPushButton(QIcon.fromTheme('view-refresh'), 'Consultar concessões')
        self.refresh.clicked.connect(self.list_grants)
        self.revoke = QPushButton(QIcon.fromTheme('edit-delete'), 'Revogar acesso selecionado…')
        self.revoke.clicked.connect(self.revoke_grant)
        toolbar.addWidget(self.refresh)
        toolbar.addWidget(self.revoke)
        toolbar.addStretch()
        body.addLayout(toolbar)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons)
        self.controls()

    def controls(self):
        idle = self.process is None
        self.create.setEnabled(idle and bool(self.folder))
        self.refresh.setEnabled(idle)
        self.revoke.setEnabled(idle and 0 <= self.table.currentRow() < len(self.entries)
                               and bool(self.table.selectedItems()))

    def invoke(self, args, done):
        if self.process is not None:
            return
        process = self.process = QProcess(self)
        self.controls()
        self.status.setText('Aguarde a autenticação e a resposta do Samba…')

        def finished(code):
            if self.process is not process:
                return
            output = bytes(process.readAllStandardOutput()).decode('utf-8', 'replace')
            errors = bytes(process.readAllStandardError()).decode('utf-8', 'replace')
            self.process = None
            process.deleteLater()
            self.controls()
            if code:
                self.status.setText(errors.strip()[:1200] or 'A operação não foi concluída.')
                return
            try:
                done(json.loads(output))
            except (ValueError, TypeError, KeyError):
                self.status.setText('O serviço retornou informações inesperadas.')

        process.finished.connect(lambda code, _: finished(code))
        process.errorOccurred.connect(lambda error: finished(1) if error == QProcess.ProcessError.FailedToStart else None)
        process.start('/usr/bin/pkexec', ['/usr/bin/linuxbr-share-grants-admin', *args])

    def show_entries(self, rows):
        self.entries = rows
        self.table.setRowCount(len(rows))
        self.table.clearSelection()
        for row, entry in enumerate(rows):
            date = datetime.fromisoformat(entry['expires']).astimezone().strftime('%d/%m/%Y %H:%M')
            for col, value in enumerate((entry['folder'], entry['account'], SCOPE[entry['scope']],
                                         date, entry['address'], STATE[entry['state']])):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self.status.setText(f'{len(rows)} concessões neste computador.' if rows else 'Nenhuma concessão neste computador.')
        self.controls()

    def list_grants(self):
        self.invoke(['list'], self.show_entries)

    def issue(self):
        args = ['issue', self.folder, self.account.text().strip(), self.scope.currentData(), str(self.minutes.value())]

        def created(entry):
            self.result.setText(entry['address'])
            self.result.setFocus()
            self.result.selectAll()
            self.list_grants()

        self.invoke(args, created)

    def revoke_grant(self):
        index = self.table.currentRow()
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        if QMessageBox.question(
                self, 'Revogar concessão',
                'Revogar o endereço temporário e encerrar as conexões abertas por ele?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            self.invoke(['revoke', entry['alias']], lambda _: self.list_grants())

    def reject(self):
        if self.process is None:
            super().reject()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', nargs='?', default='')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    ShareGrants(args.folder).exec()
