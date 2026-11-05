"""Package queue and native-manager confirmations inside the store."""
import datetime
import json
from pathlib import Path
import time
import uuid
from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox,QDialog,QDialogButtonBox,QHBoxLayout,QLabel,
    QGroupBox,QLineEdit,QListWidget,QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,QVBoxLayout)
import store_backend as backend
import store_transactions as transactions


class Operations(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Instalações, atualizações e remoções');self.resize(820,680)
        self.setWindowIcon(QIcon.fromTheme('system-software-install'))
        self.setStyleSheet('QGroupBox { border: 1px solid palette(mid); border-radius: 8px; margin-top: 8px; padding: 8px; } '
            'QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; font-weight: 600; }')
        self.queue=[];self.process=None;self.current=None;self.buffer=b'';self.item=None;self.update_process=None;self.updates_mode=False
        body=QVBoxLayout(self)
        info=QGroupBox('Aplicativo e instalação');information=QVBoxLayout(info);body.addWidget(info)
        heading=QHBoxLayout();self.application_icon=QLabel();self.application_icon.setPixmap(QIcon.fromTheme('application-x-executable').pixmap(32,32));heading.addWidget(self.application_icon)
        self.heading=QLabel();self.heading.setWordWrap(True);self.heading.setMinimumHeight(38);heading.addWidget(self.heading,1);information.addLayout(heading)
        self.targets=QComboBox();self.targets.setAccessibleName('Origem e alcance da instalação')
        self.targets.setMinimumContentsLength(35)
        self.targets.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);information.addWidget(self.targets)
        note=QLabel('DEB altera a instalação do sistema e solicita autorização quando necessário. '
            'Flatpak distingue sua conta e sistema. Remover programa preserva dados pessoais; '
            'atalhos e ambientes Windows têm ações próprias na Loja.')
        note.setWordWrap(True);information.addWidget(note)
        operations=QGroupBox('Operações');actions=QVBoxLayout(operations);body.addWidget(operations)
        row=QHBoxLayout();self.action_buttons=[]
        for text,action in (('Instalar…','install'),('Atualizar…','update'),('Remover programa…','remove')):
            button=QPushButton(text);button.clicked.connect(lambda _checked=False,a=action:self.enqueue(a))
            button.setIcon(QIcon.fromTheme({'install':'list-add','update':'system-software-update','remove':'edit-delete'}[action]))
            row.addWidget(button);self.action_buttons.append((button,action))
        actions.addLayout(row);self.targets.currentIndexChanged.connect(self.selection_changed)
        self.queue_group=QGroupBox('Fila de operações');queue=QVBoxLayout(self.queue_group);body.addWidget(self.queue_group)
        self.listing=QListWidget();self.listing.setMinimumHeight(42);self.listing.setMaximumHeight(64);queue.addWidget(self.listing)
        row=QHBoxLayout();self.progress=QProgressBar();self.progress.setRange(0,100);row.addWidget(self.progress,1)
        remove=QPushButton('Retirar aguardando');remove.setIcon(QIcon.fromTheme('list-remove'));remove.clicked.connect(self.remove_queued);row.addWidget(remove);queue.addLayout(row)
        self.cancel_current=QPushButton(QIcon.fromTheme('process-stop'),'Cancelar operação atual')
        self.cancel_current.setEnabled(False);self.cancel_current.setToolTip('Disponível somente nas etapas em que o gerenciador permite cancelar. Não encerra processos à força.')
        self.cancel_current.clicked.connect(self.request_cancel);queue.addWidget(self.cancel_current)
        records=QGroupBox('Andamento e histórico');records_layout=QVBoxLayout(records);body.addWidget(records,1)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMinimumHeight(96);self.log.setMaximumBlockCount(1500);records_layout.addWidget(self.log,1)
        history_button=QPushButton('Histórico');history_button.setIcon(QIcon.fromTheme('document-open-recent'));history_button.clicked.connect(self.show_history);records_layout.addWidget(history_button)
        self.flatpak_group=QGroupBox('Respostas ao instalador');answers=QVBoxLayout(self.flatpak_group);body.addWidget(self.flatpak_group)
        row=QHBoxLayout();self.flatpak_buttons=[]
        for text,icon,callback in (('Confirmar etapa','dialog-ok-apply',lambda:self.answer_flatpak(True)),
                              ('Recusar etapa (n)','dialog-cancel',lambda:self.answer_flatpak(False))):
            button=QPushButton(text);button.clicked.connect(callback);row.addWidget(button)
            button.setIcon(QIcon.fromTheme(icon))
            self.flatpak_buttons.append(button)
        answers.addLayout(row)
        row=QHBoxLayout();self.response=QLineEdit();self.response.setPlaceholderText('Resposta solicitada pelo Flatpak (por exemplo, número de uma opção)')
        self.response.returnPressed.connect(self.send_response);row.addWidget(self.response)
        send=QPushButton('Enviar resposta');send.setIcon(QIcon.fromTheme('mail-send'));send.clicked.connect(self.send_response);row.addWidget(send);answers.addLayout(row)
        self.flatpak_buttons.extend((self.response,send))
        self.state=QLabel('Nenhuma operação em andamento.');self.state.setWordWrap(True);body.addWidget(self.state)
        self.selection_changed();self.show_history();self.flatpak_controls();self.update_queue()

    def set_item(self,item):
        self.updates_mode=False;self.item=item;self.heading.setText(item['name']+' — escolha a instalação e a operação')
        icon=item.get('icon') or item.get('id','application-x-executable')
        self.application_icon.setPixmap((QIcon(icon) if icon.startswith('/') else QIcon.fromTheme(icon,QIcon.fromTheme('application-x-executable'))).pixmap(32,32))
        self.targets.clear()
        for target in backend.package_targets(item):
            self.targets.addItem(target['label']+(' · instalado' if target['installed'] else ' · disponibilidade será consultada'),target)
            self.targets.setItemData(self.targets.count()-1,target['label'],Qt.ItemDataRole.ToolTipRole)
        if self.targets.count()==0:
            self.heading.setText(item['name']+' — origem não identificada. Confira as fontes configuradas na Loja.')
        self.selection_changed();self.show();self.raise_();self.activateWindow()

    def selection_changed(self):
        target=self.targets.currentData()
        for button,action in self.action_buttons:
            button.setVisible(not self.updates_mode or action=='update')
            button.setEnabled(bool(target and (action=='install')!=target['installed']))

    def flatpak_controls(self):
        visible=bool(self.current and (self.current[1]['manager']=='flatpak' or self.current[1]['manager']=='file' and Path(self.current[1]['target']).suffix.lower()!='.deb'))
        self.flatpak_group.setVisible(visible)
        for widget in self.flatpak_buttons:widget.setVisible(visible)

    def enqueue(self,action):
        target=self.targets.currentData()
        if not target or not self.item:return
        try:request=transactions.checked_request(dict(target,action=action,name=target.get('name',self.item['name'])))
        except ValueError as error:
            QMessageBox.warning(self,'Instalação não identificada',str(error));return
        question={'install':'Instalar','update':'Atualizar','remove':'Remover o programa'}[action]
        detail=question+' “'+request['name']+'”?\n\n'+target['label']
        if action=='remove':detail+='\n\nNão apaga dados pessoais nem executa limpeza de dependências. A remoção DEB será recusada se exigir remover outros pacotes.'
        detail+='\n\nAs dependências e permissões serão apresentadas pelo gerenciador antes da confirmação final.'
        if QMessageBox.question(self,question,detail,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        if any(value[1]==request for value in self.queue) or self.current and self.current[1]==request:
            QMessageBox.information(self,'Operação já solicitada','Esta operação já está na fila.');return
        identifier=str(uuid.uuid4());self.queue.append((identifier,request))
        self.update_queue();self.start_next()

    def update_queue(self):
        self.queue_group.setVisible(bool(self.current or self.queue))
        self.listing.clear()
        if self.current:self.listing.addItem('Em andamento · '+self.describe(self.current[1]))
        for identifier,request in self.queue:
            self.listing.addItem('Aguardando · '+self.describe(request));self.listing.item(self.listing.count()-1).setData(Qt.ItemDataRole.UserRole,identifier)

    @staticmethod
    def describe(request):
        return {'install':'Instalar','update':'Atualizar','remove':'Remover'}[request['action']]+' '+request['name']+' · '+request['manager']+' · '+request['scope']+' · '+request['origin']

    def remove_queued(self):
        row=self.listing.currentItem();identifier=row.data(Qt.ItemDataRole.UserRole) if row else None
        if not identifier:return
        self.queue=[value for value in self.queue if value[0]!=identifier];self.update_queue()

    def start_next(self):
        if self.process or not self.queue:return
        self.current=self.queue.pop(0);identifier,request=self.current;self.buffer=b''
        self.flatpak_controls()
        self.log.clear();self.progress.setRange(0,0);self.update_queue()
        self.state.setText(self.describe(request)+' — aguardando o gerenciador.')
        process=QProcess(self);self.process=process
        process.readyReadStandardOutput.connect(self.read_output)
        process.readyReadStandardError.connect(lambda:self.log.insertPlainText(bytes(process.readAllStandardError()).decode('utf-8',errors='replace')))
        process.finished.connect(self.completed)
        process.errorOccurred.connect(lambda error:self.failed_to_start(process,error))
        process.start('/usr/bin/python3',[str(Path(__file__).with_name('store_transactions.py')),
            '--request',json.dumps(request,ensure_ascii=False),'--job',identifier])

    def failed_to_start(self,process,error):
        if process is not self.process or error!=QProcess.ProcessError.FailedToStart:return
        self.log.appendPlainText('Não foi possível iniciar o gerenciador: '+process.errorString());self.completed(1)

    def read_output(self):
        if not self.process:return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:value=json.loads(line)
            except (ValueError,UnicodeError):continue
            if value.get('event')=='output':self.log.insertPlainText(value.get('text',''))
            elif value.get('event')=='progress':
                percentage=value.get('percentage',101)
                self.progress.setRange(0,100 if 0<=percentage<=100 else 0)
                if percentage<=100:self.progress.setValue(percentage)
            elif value.get('event')=='confirmation':self.confirm_packages(value)
            elif value.get('event')=='cancelable':self.cancel_current.setEnabled(value.get('allowed') is True)

    def request_cancel(self):
        if not self.process or not self.cancel_current.isEnabled():return
        self.cancel_current.setEnabled(False);self.process.write(b'cancel\n')
        self.state.setText('Pedido de cancelamento enviado. Aguardando confirmação do gerenciador…')

    def confirm_packages(self,value):
        dialog=QDialog(self);dialog.setWindowTitle('Confirmar alterações DEB');dialog.resize(730,470)
        text='Alvo: '+value['target']+'\n\nO gerenciador calculou os componentes abaixo. A autorização do sistema será solicitada depois da sua confirmação.'
        check=value.get('preflight')
        if check:
            text+='\n\nVerificação antes de atualizar: '+check['checked_at']
            if check.get('free') is not None:text+='\nEspaço livre na raiz: '+backend.format_size(check['free'])
            text+='\n'+('\n'.join(check['warnings']) or 'Sem impedimentos detectados nas verificações disponíveis.')
        body=QVBoxLayout(dialog);label=QLabel(text);label.setWordWrap(True);body.addWidget(label)
        preview=QPlainTextEdit();preview.setReadOnly(True)
        preview.setPlainText('\n'.join(item['id']+' — '+item['summary'] for item in value['packages']) or 'Somente o pacote selecionado.');body.addWidget(preview)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Confirmar alterações')
        buttons.button(QDialogButtonBox.StandardButton.Ok).setIcon(QIcon.fromTheme('dialog-ok-apply'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setIcon(QIcon.fromTheme('dialog-cancel'))
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);body.addWidget(buttons)
        answer='approve\n' if dialog.exec()==QDialog.DialogCode.Accepted else 'reject\n'
        if self.process:self.process.write(answer.encode('ascii'))

    def answer_flatpak(self,accepted):
        if self.process and (self.current[1]['manager']=='flatpak' or self.current[1]['manager']=='file' and Path(self.current[1]['target']).suffix.lower()!='.deb'):
            self.process.write(b'y\n' if accepted else b'n\n')

    def send_response(self):
        if self.process and (self.current[1]['manager']=='flatpak' or self.current[1]['manager']=='file' and Path(self.current[1]['target']).suffix.lower()!='.deb'):
            value=self.response.text()
            if len(value)<=100 and all(ord(character)>=32 for character in value):
                self.process.write((value+'\n').encode('utf-8'));self.response.clear()

    def completed(self,code,*_):
        if not self.process:return
        identifier,request=self.current
        self.read_output();process=self.process;self.process=None;self.current=None;process.deleteLater()
        self.cancel_current.setEnabled(False)
        if code==0 and request['action'] in ('install','remove'):
            for index in range(self.targets.count()):
                target=self.targets.itemData(index)
                if target and all(target.get(key)==request[key] for key in ('manager','scope','target','origin')):
                    target=dict(target,installed=request['action']=='install');self.targets.setItemData(index,target)
            self.selection_changed()
        path=transactions.root()/'jobs'/(identifier+'.json')
        if not path.exists():
            try:
                transactions.atomic_json(path,dict(id=identifier,request=request,started=time.time(),ended=time.time(),
                    finished=True,status='failed',error='O processo do gerenciador não concluiu o acompanhamento. Confira o estado antes de repetir.'))
            except (OSError,ValueError) as error:self.log.appendPlainText('Não foi possível salvar o histórico: '+str(error))
        self.flatpak_controls()
        self.progress.setRange(0,100);self.progress.setValue(100 if code==0 else 0)
        self.state.setText('Operação concluída.' if code==0 else 'Operação não concluída. Confira o registro e o histórico.')
        self.update_queue();QTimer.singleShot(0,self.start_next)
        parent=self.parent()
        if parent and hasattr(parent,'select'):parent.select()

    def show_history(self):
        lines=[]
        for item in transactions.history():
            when=datetime.datetime.fromtimestamp(item['started']).strftime('%d/%m/%Y %H:%M')
            status={'success':'Concluída','failed':'Não concluída','stopped':'Não concluída após pedido de cancelamento','waiting':'Aguardava','running':'Resultado não registrado; confira o gerenciador'}.get(item['status'],item['status'])
            lines.append(when+' · '+status+' · '+self.describe(item['request'])+'\n'+item.get('error',''))
        text='\n\n'.join(lines) or 'Ainda não há operações registradas nesta conta.'
        if not self.process:self.log.setPlainText(text)
        else:
            dialog=QDialog(self);dialog.setWindowTitle('Histórico da Loja');dialog.resize(780,450)
            body=QVBoxLayout(dialog);view=QPlainTextEdit();view.setReadOnly(True);view.setPlainText(text);body.addWidget(view)
            button=QPushButton('Fechar');button.setIcon(QIcon.fromTheme('window-close'));button.clicked.connect(dialog.accept);body.addWidget(button);dialog.exec()

    def show_updates(self):
        self.show();self.raise_();self.activateWindow()
        if self.update_process:return
        self.updates_mode=True;self.item={'name':'Atualizações'};self.targets.clear();self.selection_changed()
        self.application_icon.setPixmap(QIcon.fromTheme('system-software-update').pixmap(32,32))
        self.heading.setText('Consultando atualizações nos índices locais. Esta consulta não altera pacotes nem fontes.')
        process=QProcess(self);self.update_process=process
        process.finished.connect(lambda code,*_:self.updates_finished(process,code))
        process.errorOccurred.connect(lambda error:self.updates_failed(process,error))
        process.start('/usr/bin/python3',[str(Path(__file__).with_name('store_transactions.py')),'--list-updates'])

    def updates_failed(self,process,error):
        if self.update_process is process and error==QProcess.ProcessError.FailedToStart:
            self.heading.setText('Não foi possível consultar atualizações: '+process.errorString());self.update_process=None;process.deleteLater()

    def updates_finished(self,process,code):
        if self.update_process is not process:return
        self.update_process=None;targets=[];errors=[]
        for line in bytes(process.readAllStandardOutput()).splitlines():
            try:value=json.loads(line)
            except (ValueError,UnicodeError):continue
            if value.get('event')=='updates':targets=value['targets'];errors=value['errors']
        if code:errors.append(bytes(process.readAllStandardError()).decode('utf-8',errors='replace') or 'Consulta interrompida.')
        self.targets.clear()
        for value in targets:
            self.targets.addItem(value['label'],value);self.targets.setItemData(self.targets.count()-1,value['label'],Qt.ItemDataRole.ToolTipRole)
        self.heading.setText(str(len(targets))+' atualizações nos índices locais. Selecione uma instalação e use Atualizar. '
            'Atualize os índices pela Loja se necessário. A transação final confere novamente a disponibilidade.'+
            ('\nConsultas incompletas: '+'; '.join(errors) if errors else ''))
        self.selection_changed();process.deleteLater()

    def closeEvent(self,event):
        if self.process or self.queue:
            QMessageBox.information(self,'Operação em andamento','Aguarde a conclusão ou recuse a etapa apresentada pelo gerenciador. '
                'Você pode minimizar esta janela enquanto aguarda.');event.ignore()
        else:super().closeEvent(event)

    def install_file(self,path,sha256):
        self.updates_mode=False;self.item=None;self.targets.clear();self.heading.setText('Instalar arquivo local: '+Path(path).name)
        request=transactions.checked_request(dict(manager='file',action='install',target=str(path),scope='system' if Path(path).suffix.lower()=='.deb' else 'user',origin='Arquivo local revisado',name=Path(path).name[:200],sha256=sha256))
        self.queue.append((str(uuid.uuid4()),request));self.selection_changed();self.show();self.raise_();self.start_next()
