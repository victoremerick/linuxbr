"""Readable adapter information with background refresh."""
from PyQt6.QtCore import Qt, QProcess, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QScrollArea, QFormLayout,QMessageBox)
from desktop_jobs import Query,Command
import network_details


class NetworkDetails(QWidget):
    def __init__(self):
        super().__init__()
        self.jobs = set()
        self.rows = []
        self.commands=[]
        layout = QVBoxLayout(self)
        title = QLabel('Detalhes da conexão')
        title.setStyleSheet('font-size:26px;font-weight:600')
        layout.addWidget(title)
        note = QLabel('Consulte os endereços e as propriedades de cada adaptador. Uma conexão ativa não garante acesso à internet.')
        note.setWordWrap(True)
        layout.addWidget(note)
        bar = QHBoxLayout()
        self.adapters = QComboBox()
        self.adapters.setAccessibleName('Adaptador de rede')
        self.adapters.currentIndexChanged.connect(self.show_details)
        bar.addWidget(self.adapters, 1)
        self.refresh_button = QPushButton(QIcon.fromTheme('view-refresh'), 'Atualizar')
        self.refresh_button.clicked.connect(self.refresh)
        bar.addWidget(self.refresh_button)
        layout.addLayout(bar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll, 1)
        actions = QHBoxLayout()
        self.copy_button = QPushButton(QIcon.fromTheme('edit-copy'), 'Copiar detalhes')
        self.copy_button.clicked.connect(self.copy)
        actions.addWidget(self.copy_button)
        edit = QPushButton(QIcon.fromTheme('document-edit'), 'Configurar conexões')
        edit.clicked.connect(self.edit)
        actions.addWidget(edit)
        layout.addLayout(actions)
        actions=QHBoxLayout()
        self.reconnect_button=QPushButton(QIcon.fromTheme('network-connect'),'Reativar conexão');self.reconnect_button.clicked.connect(self.reconnect);actions.addWidget(self.reconnect_button)
        self.diagnose_button=QPushButton(QIcon.fromTheme('tools-wizard'),'Diagnóstico de rede');self.diagnose_button.clicked.connect(self.diagnose);actions.addWidget(self.diagnose_button);layout.addLayout(actions)
        self.portal_button = QPushButton(QIcon.fromTheme('internet-web-browser'), 'Abrir portal de autenticação')
        self.portal_button.setVisible(False)
        self.portal_button.clicked.connect(self.open_portal)
        actions.addWidget(self.portal_button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.show_details()
        self.refresh()

    def refresh(self):
        if self.jobs:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText('Consultando adaptadores…')
        job = Query(network_details.inventory, self)
        self.jobs.add(job)
        job.result.connect(self.loaded)
        job.failed.connect(lambda _: self.status.setText('Não foi possível consultar os adaptadores. Tente atualizar.'))
        job.finished.connect(lambda: self.jobs.discard(job))
        job.finished.connect(lambda: self.refresh_button.setEnabled(True))
        job.finished.connect(job.deleteLater)
        job.start()

    def loaded(self, devices):
        selected = (self.adapters.currentData() or {}).get('GENERAL.DEVICE')
        self.adapters.blockSignals(True)
        self.adapters.clear()
        index = 0
        for number, device in enumerate(devices):
            name = device.get('GENERAL.DEVICE', '')
            connection = device.get('GENERAL.CONNECTION', '')
            self.adapters.addItem(name + (' · ' + connection if connection else ''), device)
            if name == selected:
                index = number
        self.adapters.setCurrentIndex(index)
        self.adapters.blockSignals(False)
        self.show_details()
        self.status.setText('Informações atualizadas.' if devices else 'Nenhum adaptador encontrado.')

    def show_details(self):
        device = self.adapters.currentData()
        self.portal_button.setVisible(any(
            (device or {}).get(f'GENERAL.IP{family}-CONNECTIVITY', '').partition(' ')[0] == '2'
            for family in (4, 6)
        ))
        self.rows = network_details.fields(device) if device else []
        self.copy_button.setEnabled(bool(self.rows))
        self.diagnose_button.setEnabled(bool(device))
        try:
            network_details.reconnect_command(device or {})
        except ValueError:
            self.reconnect_button.setEnabled(False)
        else:
            self.reconnect_button.setEnabled(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        if not self.rows:
            empty = QLabel('Nenhum adaptador disponível para consulta.')
            empty.setWordWrap(True)
            form.addRow(empty)
        for label, value in self.rows:
            field = QLabel(value)
            field.setTextFormat(Qt.TextFormat.PlainText)
            field.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
            field.setWordWrap(True)
            field.setAccessibleName(label)
            form.addRow(label, field)
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(body)

    def copy(self):
        QApplication.clipboard().setText('\n'.join(f'{key}: {value}' for key, value in self.rows))
        self.status.setText('Detalhes copiados. Endereços de rede podem identificar seu computador.')

    def edit(self):
        import shutil
        import os
        if not shutil.which('kcmshell6') or 'LinuxBRMinimal' in os.environ.get('XDG_CURRENT_DESKTOP','') and shutil.which('nm-connection-editor'):
            if not QProcess.startDetached('/usr/bin/nm-connection-editor', [])[0]:
                self.status.setText('Não foi possível abrir o editor de conexões.')
            return
        if not QProcess.startDetached('/usr/bin/kcmshell6', ['kcm_networkmanagement'])[0]:
            self.status.setText('Não foi possível abrir a configuração de conexões.')

    def reconnect(self):
        try:argv=network_details.reconnect_command(self.adapters.currentData() or {})
        except ValueError as error:self.status.setText(str(error));return
        if QMessageBox.warning(self,'Reativar conexão','A conexão selecionada será reativada pelo gerenciador. O acesso à rede e sessões remotas podem ser interrompidos. Endereços automáticos continuam sob controle do DHCP; a reativação não garante um endereço diferente. Continuar?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        dialog=Command('Reativar conexão',argv,self,success_message='Conexão reativada. Confira os endereços atualizados.');self.commands.append(dialog);dialog.completed.connect(lambda _:self.refresh())

    def diagnose(self):
        if self.jobs:
            return
        name = (self.adapters.currentData() or {}).get('GENERAL.DEVICE')
        if not name:
            self.status.setText('Selecione um adaptador para diagnosticar a conexão.')
            return
        self.status.setText('Verificando conexão, gateway e DNS…')
        self.diagnose_button.setEnabled(False)
        self.adapters.setEnabled(False)
        self.refresh_button.setEnabled(False)
        job = Query(lambda: network_details.connectivity_check(name), self)
        self.jobs.add(job)
        job.result.connect(lambda result: self.show_diagnosis(name, result))
        job.failed.connect(lambda _: self.status.setText('Não foi possível concluir o diagnóstico. Tente novamente.'))
        job.finished.connect(lambda: self.jobs.discard(job))
        job.finished.connect(lambda: self.diagnose_button.setEnabled(bool(self.adapters.currentData())))
        job.finished.connect(lambda: self.adapters.setEnabled(True))
        job.finished.connect(lambda: self.refresh_button.setEnabled(True))
        job.finished.connect(job.deleteLater)
        job.start()

    def show_diagnosis(self, name, result):
        if (self.adapters.currentData() or {}).get('GENERAL.DEVICE') != name:
            return
        rows, connectivity = result
        self.portal_button.setVisible(connectivity == 'portal')
        self.status.setText('\n'.join(f'{label}: {message}' for label, message in rows))

    def open_portal(self):
        # A captive network can only redirect an unencrypted HTTP request.
        if not QDesktopServices.openUrl(QUrl('http://example.com/')):
            self.status.setText('Não foi possível abrir o navegador padrão.')
