"""Review signed web application revisions without moving browser profiles."""
import json
import subprocess
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QMessageBox
from desktop_jobs import Query
import signed_catalog as backend


class WebUpdates(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=set();layout=QVBoxLayout(self)
        title=QLabel('Revisões dos aplicativos web');title.setStyleSheet('font-size:24px;font-weight:600');layout.addWidget(title)
        note=QLabel('Sites normalmente se atualizam no servidor do fornecedor. Aqui você revisa mudanças no cadastro e novidades oficialmente informadas. Chromium recebe atualizações pelo sistema.');note.setWordWrap(True);layout.addWidget(note)
        self.list=QListWidget();self.list.currentItemChanged.connect(self.selection);layout.addWidget(self.list,1)
        self.detail=QLabel();self.detail.setWordWrap(True);self.detail.setTextFormat(Qt.TextFormat.PlainText);self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);layout.addWidget(self.detail)
        bar=QHBoxLayout();self.refresh_button=QPushButton(QIcon.fromTheme('view-refresh'),'Verificar fontes');self.refresh_button.clicked.connect(lambda:self.refresh(True));bar.addWidget(self.refresh_button)
        self.apply_button=QPushButton(QIcon.fromTheme('dialog-ok-apply'),'Aplicar revisão do cadastro');self.apply_button.clicked.connect(self.apply);bar.addWidget(self.apply_button)
        self.open_button=QPushButton(QIcon.fromTheme('internet-web-browser'),'Revisar novo endereço');self.open_button.clicked.connect(self.open_new);bar.addWidget(self.open_button)
        self.ack=QPushButton(QIcon.fromTheme('mail-mark-read'),'Marcar como revisado');self.ack.clicked.connect(lambda:self.apply(True));bar.addWidget(self.ack);layout.addLayout(bar)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status);self.refresh()

    def selected(self):
        item=self.list.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self,online=False):
        if self.jobs:return
        self.refresh_button.setEnabled(False)
        def read():
            errors=[]
            if online:
                for source in backend.sources():
                    if not source['enabled']:continue
                    try:backend.refresh(source['name'])
                    except Exception as error:errors.append(source['name']+': '+str(error))
            return backend.updates(),errors
        job=Query(read,self);self.jobs.add(job);job.result.connect(self.loaded);job.failed.connect(self.status.setText);job.finished.connect(lambda:self.jobs.discard(job));job.finished.connect(lambda:self.refresh_button.setEnabled(True));job.finished.connect(self.selection);job.finished.connect(job.deleteLater);job.start();self.selection()

    def loaded(self,result):
        self.list.clear()
        for row in result[0]:
            item=QListWidgetItem(QIcon.fromTheme('internet-web-browser'),row['name']+' · revisão '+str(row['revision']));item.setData(Qt.ItemDataRole.UserRole,row);self.list.addItem(item)
        self.status.setText('\n'.join(result[1]) or (str(len(result[0]))+' revisões disponíveis.' if result[0] else 'Nenhuma revisão pendente nas fontes válidas.'))
        if self.list.count():self.list.setCurrentRow(0)

    def selection(self,*_):
        row=self.selected();ready=bool(row and not self.jobs)
        self.apply_button.setEnabled(ready and not row['changed_url'] and not row['disabled'] if row else False)
        self.open_button.setEnabled(ready and row['changed_url'] and not row['disabled'] if row else False);self.ack.setEnabled(ready)
        if not row:self.detail.setText('Escolha uma revisão para ver os detalhes.');return
        text=row['changelog'] or 'O fornecedor não informou detalhes desta revisão.'
        text+='\nFonte: '+row['source']+'\nVersão do serviço: '+(row['upstream_version'] or 'Não informada')
        if row['upstream_release_url']:text+='\nPublicação oficial: '+row['upstream_release_url']
        if row['changed_url']:text+='\nNovo endereço: '+row['url']+'\nUma nova instalação usará outro perfil. As contas anteriores não serão transferidas.'
        if row['disabled']:text+='\nEste registro foi desativado pelo fornecedor. Seu aplicativo e seus dados permanecem no computador.'
        self.detail.setText(text)

    def apply(self,acknowledge=False):
        row=self.selected()
        if not row:return
        if QMessageBox.question(self,'Confirmar revisão','Marcar esta revisão como lida?' if acknowledge else 'Aplicar a revisão do cadastro, preservando as contas e preferências?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:self.status.setText(backend.apply_update(row['profile'],row['revision'],acknowledge));self.refresh()
        except Exception as error:self.status.setText(str(error))

    def open_new(self):
        row=self.selected()
        if not row:return
        offer=dict(name=row['name'],url=row['url'],signed_source=row['source'],signed_app=row['app'])
        if not QProcess.startDetached('/usr/bin/linuxbr-webapps',['--offer',json.dumps(offer)])[0]:self.status.setText('Não foi possível abrir o instalador do aplicativo web.')
