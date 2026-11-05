"""Optional resources with distinct service and package operations."""
import json
from pathlib import Path
from PyQt6.QtCore import Qt,QProcess
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,QHeaderView,QPushButton,QComboBox,QMessageBox,QDialog,QPlainTextEdit,QDialogButtonBox
from desktop_jobs import Query,Command
import features_backend as backend


class Features(QWidget):
    def __init__(self):
        super().__init__();self.jobs=set();self.commands=[];layout=QVBoxLayout(self)
        title=QLabel('Ativar ou desativar recursos do Linux BR');title.setStyleSheet('font-size:24px;font-weight:600');layout.addWidget(title)
        note=QLabel('Desativar serviços reduz atividades em segundo plano. Remover pacotes libera espaço, sem apagar dados pessoais. Programas fechados não consomem memória apenas por estarem instalados.');note.setWordWrap(True);layout.addWidget(note)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Recurso','Pacotes instalados','Espaço dos pacotes','Serviços']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows);self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers);self.table.itemSelectionChanged.connect(self.selected_changed);layout.addWidget(self.table,1)
        self.impact=QLabel();self.impact.setWordWrap(True);layout.addWidget(self.impact)
        row=QHBoxLayout()
        for caption,icon,action in [('Ativar serviços','media-playback-start','enable'),('Desativar serviços','media-playback-stop','disable'),('Instalar recurso…','list-add','install'),('Remover pacotes…','edit-delete','remove')]:
            button=QPushButton(QIcon.fromTheme(icon),caption);button.clicked.connect(lambda _,a=action:self.choose(a));row.addWidget(button)
        layout.addLayout(row);row=QHBoxLayout();self.profile=QComboBox();self.profile.addItems(backend.PROFILES);row.addWidget(self.profile)
        preview=QPushButton(QIcon.fromTheme('document-preview'),'Revisar perfil de serviços…');preview.clicked.connect(self.profile_plan);row.addWidget(preview)
        undo=QPushButton(QIcon.fromTheme('edit-undo'),'Reverter última alteração de serviços');undo.clicked.connect(self.undo);row.addWidget(undo);layout.addLayout(row)
        row=QHBoxLayout();index=QPushButton(QIcon.fromTheme('system-search'),'Configurar indexação da minha conta');index.clicked.connect(self.indexing);row.addWidget(index)
        refresh=QPushButton(QIcon.fromTheme('view-refresh'),'Atualizar');refresh.clicked.connect(self.refresh);row.addWidget(refresh);layout.addLayout(row)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.refresh()

    def query(self,operation,done):
        task=Query(operation,self);self.jobs.add(task);task.result.connect(done);task.failed.connect(self.status.setText);task.finished.connect(lambda:self.jobs.discard(task));task.finished.connect(task.deleteLater);task.start()

    def refresh(self):
        if self.jobs:return
        self.status.setText('Consultando recursos…');self.query(backend.inventory,self.loaded)

    def loaded(self,rows):
        self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            states=row['states'];active=sum(s['ActiveState']=='active' for s in states.values());blocked=sum(s['LoadState']=='masked' for s in states.values())
            values=[row['name'],str(len(row['installed']))+'/'+str(len(row['packages'])),f"{row['size']/1024**2:.1f} MiB",f'{active} ativos · {blocked} bloqueados' if states else 'Sem serviço residente instalado']
            for j,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row)
                if j==0:item.setIcon(QIcon.fromTheme(row['icon']))
                self.table.setItem(i,j,item)
        self.status.setText('Espaço inclui os pacotes listados; bibliotecas compartilhadas e dados pessoais não entram na estimativa. A prévia informa as dependências reais.')

    def selected(self):
        item=self.table.item(self.table.currentRow(),0);return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selected_changed(self):
        row=self.selected();self.impact.setText(row['impact'] if row else '')

    def confirm(self,title,text):
        dialog=QDialog(self);dialog.setWindowTitle(title);dialog.resize(760,540);layout=QVBoxLayout(dialog);view=QPlainTextEdit(text);view.setReadOnly(True);layout.addWidget(view);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);return dialog.exec()==QDialog.DialogCode.Accepted

    def execute(self,request):
        dialog=Command('Alterar recursos do Linux BR',['/usr/bin/pkexec','/usr/bin/python3',str(Path(__file__).with_name('features_backend.py'))],self,json.dumps(request).encode());self.commands.append(dialog);dialog.completed.connect(lambda _:self.refresh())

    def choose(self,action):
        row=self.selected()
        if not row:return
        if action in ('enable','disable'):
            if not row['states']:self.status.setText('Use instalar/remover para este recurso. Não há serviços instalados controlados por esta página.');return
            text=row['impact']+'\n\n'+('Ativar' if action=='enable' else 'Desativar e bloquear novas ativações de')+':\n'+'\n'.join(row['states'])+'\n\nNão é necessário reiniciar o computador. A mudança será imediata.'
            if self.confirm('Revisar alteração de serviços',text):self.execute(dict(action='services',selection={row['id']:action=='enable'}))
        else:
            def planned(plan):
                if self.confirm('Revisar alteração de pacotes',row['impact']+'\n\n'+plan['details']+'\n\nA remoção não purga arquivos pessoais. Para desfazer, reinstale o recurso; versões anteriores podem não estar disponíveis. Reinicie se o sistema indicar essa necessidade após a operação.'):
                    self.execute(dict(action=action,feature=row['id'],sha256=plan['sha256']))
            self.query(lambda:backend.package_plan(row['id'],action),planned)

    def profile_plan(self):
        enabled=backend.PROFILES[self.profile.currentText()];selection={key:key in enabled for key,value in backend.FEATURES.items() if value['units'] and not value.get('manual')}
        text='Perfil: '+self.profile.currentText()+'\n\nEste perfil altera somente serviços já instalados. Instale os recursos ausentes separadamente.\n\n'
        text+='\n\n'.join(('Ativar: ' if value else 'Desativar: ')+backend.FEATURES[key]['name']+'\n'+backend.FEATURES[key]['impact'] for key,value in selection.items())
        if self.confirm('Revisar perfil',text):self.execute(dict(action='services',selection=selection))

    def indexing(self):
        import shutil,os
        if not shutil.which('kcmshell6') or 'LinuxBRMinimal' in os.environ.get('XDG_CURRENT_DESKTOP',''):
            QMessageBox.information(self,'Indexação','A sessão mínima não inicia o indexador do desktop. Na edição Desktop, configure a indexação por conta.');return
        if not QProcess.startDetached('/usr/bin/kcmshell6',['kcm_baloofile'])[0]:self.status.setText('Não foi possível abrir as configurações de indexação.')

    def undo(self):
        if QMessageBox.question(self,'Reverter serviços','Restaurar o estado registrado antes da última alteração? Isso pode iniciar ou parar serviços.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.execute(dict(action='undo'))
