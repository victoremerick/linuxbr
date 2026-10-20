"""Local group management embedded in Linux BR accounts."""
import grp
import pwd
import shutil
from pathlib import Path
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, QComboBox, QLabel, QMessageBox)


class GroupsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.process = None
        body = QVBoxLayout(self)
        note = QLabel('Grupos locais definem permissões. A associação a grupos do domínio é administrada pela empresa.')
        note.setWordWrap(True); body.addWidget(note)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Grupo', 'GID', 'Membros locais'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.select_group)
        body.addWidget(self.table)
        self.controls = QWidget(); line = QVBoxLayout(self.controls)
        first = QHBoxLayout(); self.group = QLineEdit(); self.group.setPlaceholderText('Novo grupo')
        first.addWidget(self.group)
        self.create_button = QPushButton('Criar grupo'); self.create_button.clicked.connect(lambda:self.change('create'))
        first.addWidget(self.create_button)
        self.delete_button = QPushButton('Excluir grupo'); self.delete_button.clicked.connect(lambda:self.change('delete'))
        first.addWidget(self.delete_button); line.addLayout(first)
        second = QHBoxLayout(); self.user = QComboBox(); second.addWidget(self.user)
        self.add_button = QPushButton('Adicionar usuário'); self.add_button.clicked.connect(lambda:self.change('add'))
        self.remove_button = QPushButton('Remover usuário'); self.remove_button.clicked.connect(lambda:self.change('remove'))
        second.addWidget(self.add_button); second.addWidget(self.remove_button); line.addLayout(second)
        body.addWidget(self.controls)
        self.status = QLabel(); self.status.setWordWrap(True); body.addWidget(self.status)
        self.refresh()

    def refresh(self):
        from groups_backend import local_groups, local_users
        groups, users = local_groups(), local_users()
        rows = [g for g in groups.values() if int(g[2]) >= 1000 or g[0] == 'sudo']
        rows.sort(key=lambda g:g[0])
        self.table.setRowCount(len(rows))
        for i, entry in enumerate(rows):
            for j, text in enumerate((entry[0],entry[2],entry[3].replace(',', ', '))):
                self.table.setItem(i,j,QTableWidgetItem(text))
        self.user.clear()
        self.user.addItems(sorted(name for name, fields in users.items() if int(fields[2]) >= 1000))
        self.select_group()

    def select_group(self):
        row = self.table.currentRow(); selected = row >= 0 and self.table.item(row,0)
        self.delete_button.setEnabled(bool(selected) and self.table.item(row,0).text() != 'sudo')
        self.add_button.setEnabled(bool(selected) and self.user.count() > 0)
        self.remove_button.setEnabled(bool(selected) and self.user.count() > 0)

    def change(self, action):
        group = self.group.text().strip() if action == 'create' else self.table.item(self.table.currentRow(),0).text() if self.table.currentRow() >= 0 else ''
        user = self.user.currentText() if action in ('add','remove') else ''
        if not group: self.status.setText('Escolha ou informe um grupo.'); return
        if action in ('delete','remove') and QMessageBox.question(self, 'Confirmar alteração',
                f'{"Excluir o grupo" if action == "delete" else "Remover a conta do grupo"} {group}?') != QMessageBox.StandardButton.Yes: return
        from groups_backend import local_groups
        # Apply the same validation before prompting for administrative access.
        try:
            if action == 'create' and group in local_groups(): raise ValueError('Este grupo já existe.')
            if action not in ('create','delete','add','remove'): raise ValueError('Ação inválida.')
        except ValueError as error:
            self.status.setText(str(error)); return
        self.controls.setEnabled(False); self.status.setText('Aguardando autenticação administrativa…')
        process = self.process = QProcess(self)
        process.setProgram(shutil.which('pkexec') or '/usr/bin/pkexec')
        process.setArguments(['/usr/bin/python3',str(Path(__file__).with_name('groups_backend.py')),action,group]+([user] if user else []))
        process.finished.connect(lambda code,status:self.finished(process,code))
        process.errorOccurred.connect(lambda error:self.finished(process,1) if error == QProcess.ProcessError.FailedToStart else None)
        process.start()

    def finished(self, process, code):
        if self.process is not process: return
        self.process = None; self.controls.setEnabled(True)
        message = bytes(process.readAllStandardError()).decode(errors='replace').strip()
        self.status.setText('Grupo atualizado.' if code == 0 else 'Não foi possível alterar o grupo. ' + (message or 'Verifique a autenticação e tente novamente.'))
        process.deleteLater(); self.refresh()
