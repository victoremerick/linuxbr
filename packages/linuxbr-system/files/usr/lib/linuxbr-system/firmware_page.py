"""Firmware updates reviewed per device using the fwupd service."""
import json
import re
import subprocess
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox
from desktop_jobs import Query,Command


def devices():
    result=subprocess.run(['/usr/bin/fwupdmgr','--json','get-updates'],capture_output=True,text=True,timeout=45)
    try:value=json.loads(result.stdout)
    except ValueError:raise ValueError(result.stderr.strip() or result.stdout.strip() or 'O serviço não forneceu informações de firmware.') from None
    rows=value.get('Devices',[])
    if not isinstance(rows,list):raise ValueError('Resposta de firmware inválida.')
    return rows


class Firmware(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=set();self.commands=[];layout=QVBoxLayout(self);title=QLabel('Firmware dos dispositivos');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        note=QLabel('Atualizações fornecidas pelo fwupd. Selecione um dispositivo e confira fornecedor e versão antes de instalar. Não desligue o equipamento durante a atualização.');note.setWordWrap(True);layout.addWidget(note)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Dispositivo','Versão atual','Versão disponível','Fornecedor']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows);self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers);layout.addWidget(self.table,1)
        row=QHBoxLayout()
        for text,icon,callback in [('Consultar atualizações','view-refresh',self.refresh),('Atualizar metadados','download',self.metadata),('Detalhes','document-properties',self.details),('Instalar no dispositivo…','system-software-update',self.install)]:
            button=QPushButton(QIcon.fromTheme(icon),text);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.status=QLabel('Consulte as atualizações para verificar o suporte dos dispositivos.');self.status.setWordWrap(True);layout.addWidget(self.status)

    def refresh(self):
        if self.jobs:return
        task=Query(devices,self);self.jobs.add(task);task.result.connect(self.loaded);task.failed.connect(self.status.setText);task.finished.connect(lambda:self.jobs.discard(task));task.finished.connect(task.deleteLater);task.start();self.status.setText('Consultando o serviço de firmware…')

    def loaded(self,rows):
        self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            release=next(iter(row.get('Releases',[])),{})
            for j,value in enumerate([row.get('Name','Dispositivo'),row.get('Version','Não informada'),release.get('Version','Não informada'),release.get('Vendor',row.get('Vendor','Não informado'))]):
                item=QTableWidgetItem(str(value));item.setData(Qt.ItemDataRole.UserRole,row);self.table.setItem(i,j,item)
        self.status.setText(str(len(rows))+' dispositivos com atualizações apresentadas pelo serviço.' if rows else 'Nenhuma atualização apresentada pelo fwupd. Isto não confirma suporte a todos os dispositivos.')

    def selected(self):
        item=self.table.item(self.table.currentRow(),0);return item.data(Qt.ItemDataRole.UserRole) if item else None

    def command(self,title,argv):
        dialog=Command(title,argv,self);self.commands.append(dialog);dialog.completed.connect(lambda _:self.refresh())

    def metadata(self):self.command('Atualizar metadados de firmware',['/usr/bin/fwupdmgr','refresh'])

    def details(self):
        row=self.selected()
        if row:
            box=QMessageBox(self);box.setWindowTitle('Detalhes do firmware');box.setTextFormat(Qt.TextFormat.PlainText);box.setText(row.get('Name','Dispositivo'));box.setDetailedText(json.dumps(row,ensure_ascii=False,indent=2));box.exec()

    def install(self):
        row=self.selected()
        if not row:return
        identifier=row.get('DeviceId','');release=next(iter(row.get('Releases',[])),{})
        if not re.fullmatch(r'[a-fA-F0-9]{40}',identifier):QMessageBox.warning(self,'Dispositivo não identificado','O serviço não apresentou um identificador válido para este dispositivo.');return
        text='Atualizar '+row.get('Name','dispositivo')+' de '+str(row.get('Version','?'))+' para '+str(release.get('Version','?'))+'?\n\nFornecedor: '+str(release.get('Vendor',row.get('Vendor','Não informado')))+'\nMantenha a alimentação conectada. A atualização pode exigir reinicialização; o serviço verificará os requisitos.'
        if QMessageBox.question(self,'Revisar atualização de firmware',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.command('Atualizar firmware de '+row.get('Name','dispositivo'),['/usr/bin/fwupdmgr','--assume-yes','--no-reboot-check','update',identifier])
