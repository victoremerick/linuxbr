"""Services, event logs, environment variables and scheduled tasks."""
import json
from pathlib import Path
import re
import shlex
import subprocess
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QTabWidget,QPlainTextEdit,QLineEdit,QMessageBox,QDialog,QFormLayout,QDialogButtonBox,QFileDialog,QCheckBox
from desktop_jobs import Query,Command
import administration_backend as backend


def table(headers,editable=False):
    value=QTableWidget(0,len(headers));value.setHorizontalHeaderLabels(headers);value.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);value.setSelectionBehavior(value.SelectionBehavior.SelectRows)
    if not editable:value.setEditTriggers(value.EditTrigger.NoEditTriggers)
    return value


class Administration(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=set();self.commands=[];self.environment_record=None;self.generation=0;layout=QVBoxLayout(self);title=QLabel('Ferramentas administrativas');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        self.scope=QComboBox();self.scope.addItem('Minha conta','user');self.scope.addItem('Todo o computador','system');layout.addWidget(self.scope)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        services=QWidget();body=QVBoxLayout(services);self.filter=QLineEdit();self.filter.setPlaceholderText('Filtrar serviços pelo nome ou descrição…');self.filter.textChanged.connect(self.filter_services);body.addWidget(self.filter);self.services=table(['Unidade','Estado','Inicialização','Descrição','Proteção']);body.addWidget(self.services)
        self.hide_essential=QCheckBox('Ocultar componentes protegidos');self.hide_essential.toggled.connect(self.filter_services);body.addWidget(self.hide_essential)
        lifecycle=QPushButton(QIcon.fromTheme('user-identity'),'Execução dos serviços da minha conta sem login…');lifecycle.clicked.connect(self.linger);body.addWidget(lifecycle)
        row=QHBoxLayout()
        create_service=QPushButton(QIcon.fromTheme('list-add'),'Criar serviço…');create_service.clicked.connect(self.create_service);body.addWidget(create_service)
        details=QPushButton(QIcon.fromTheme('document-properties'),'Propriedades do serviço');details.clicked.connect(self.service_details);body.addWidget(details)
        editrow=QHBoxLayout()
        for label,icon,restore in [('Editar configuração do serviço…','document-edit',False),('Restaurar configuração anterior…','edit-undo',True)]:
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(lambda _,r=restore:self.edit_service(r));editrow.addWidget(button)
        body.addLayout(editrow)
        transfers=QHBoxLayout()
        for caption,icon,operation in [('Importar…','document-import','import'),('Exportar…','document-export','export'),('Duplicar…','edit-copy','duplicate'),('Remover serviço criado…','edit-delete','remove')]:
            button=QPushButton(QIcon.fromTheme(icon),caption);button.clicked.connect(lambda _,op=operation:self.transfer_service(op));transfers.addWidget(button)
        body.addLayout(transfers)
        for caption,action,icon in [('Iniciar','start','media-playback-start'),('Parar','stop','media-playback-stop'),('Reiniciar','restart','system-reboot'),('Habilitar no início','enable','dialog-ok-apply'),('Desabilitar no início','disable','dialog-cancel')]:
            button=QPushButton(QIcon.fromTheme(icon),caption);button.clicked.connect(lambda _=False,a=action:self.service_action(a));row.addWidget(button)
        body.addLayout(row)
        advanced=QHBoxLayout()
        for caption,action,icon in [('Recarregar configuração','reload','view-refresh'),('Bloquear futuras ativações','mask','object-locked'),('Desbloquear','unmask','object-unlocked')]:
            button=QPushButton(QIcon.fromTheme(icon),caption);button.clicked.connect(lambda _,a=action:self.service_action(a));advanced.addWidget(button)
        body.addLayout(advanced);logs=QPushButton(QIcon.fromTheme('view-list-text'),'Consultar eventos do serviço selecionado');logs.clicked.connect(self.service_logs);body.addWidget(logs);self.tabs.addTab(services,'Serviços')
        events=QWidget();event_layout=QVBoxLayout(events);self.log_unit=None;self.log_text=''
        self.log_filter=QLineEdit();self.log_filter.setPlaceholderText('Buscar no texto dos eventos…');self.log_filter.textChanged.connect(self.filter_logs);event_layout.addWidget(self.log_filter)
        self.logs=QPlainTextEdit();self.logs.setReadOnly(True);event_layout.addWidget(self.logs,1)
        controls=QHBoxLayout();export=QPushButton(QIcon.fromTheme('document-export'),'Exportar eventos exibidos…');export.clicked.connect(self.export_logs);controls.addWidget(export)
        all_logs=QPushButton(QIcon.fromTheme('view-list-details'),'Todos os eventos');all_logs.clicked.connect(self.all_logs);controls.addWidget(all_logs);event_layout.addLayout(controls)
        self.tabs.addTab(events,'Eventos')
        self.log_timer=QTimer(self);self.log_timer.setInterval(5000);self.log_timer.timeout.connect(lambda:self.refresh() if self.isVisible() and self.tabs.currentIndex()==1 and not self.jobs else None);self.log_timer.start()
        environment=QWidget();body=QVBoxLayout(environment);note=QLabel('Variáveis persistentes para novas sessões. Alterações da sua conta têm prioridade no desktop. Confira PATH e outras variáveis importantes antes de aplicar.');note.setWordWrap(True);body.addWidget(note);self.variables=table(['Nome','Valor'],True);body.addWidget(self.variables)
        row=QHBoxLayout()
        for caption,callback in [('Adicionar variável',lambda:self.variables.insertRow(self.variables.rowCount())),('Remover variável',lambda:self.variables.removeRow(self.variables.currentRow())),('Aplicar variáveis',self.save_environment)]:
            button=QPushButton(caption);button.clicked.connect(callback);row.addWidget(button)
        body.addLayout(row);self.tabs.addTab(environment,'Variáveis de ambiente')
        reload_environment=QPushButton(QIcon.fromTheme('view-refresh'),'Recarregar ambiente dos novos serviços da minha conta')
        reload_environment.clicked.connect(lambda:self.command('Recarregar ambiente pessoal',['/usr/bin/systemctl','--user','daemon-reload']) if self.confirm('Recarregar as variáveis dos novos serviços da sua conta? Processos já em execução não serão reiniciados. Aplicativos do desktop recebem os valores em uma nova sessão.') else None);body.addWidget(reload_environment)
        scheduler=QWidget();body=QVBoxLayout(scheduler);note=QLabel('Tarefas pessoais são executadas quando a sua sessão de usuário está disponível. Tarefas do computador exigem autorização e podem executar com privilégios administrativos.');note.setWordWrap(True);body.addWidget(note);self.tasks=table(['Nome','Agendamento','Habilitação','Próxima execução']);body.addWidget(self.tasks)
        row=QHBoxLayout();create=QPushButton(QIcon.fromTheme('list-add'),'Criar tarefa');create.clicked.connect(self.create_task);row.addWidget(create)
        for caption,action in [('Executar agora','run'),('Habilitar','enable'),('Desabilitar','disable'),('Remover','remove')]:
            button=QPushButton(caption);button.clicked.connect(lambda _=False,a=action:self.task_action(a));row.addWidget(button)
        body.addLayout(row);self.tabs.addTab(scheduler,'Agendador de Tarefas')
        for index,icon in enumerate(('preferences-system-services','view-list-text','utilities-terminal','view-calendar-timeline')):self.tabs.setTabIcon(index,QIcon.fromTheme(icon))
        for button in environment.findChildren(QPushButton):button.setIcon(QIcon.fromTheme({'Adicionar variável':'list-add','Remover variável':'list-remove','Aplicar variáveis':'dialog-ok-apply'}.get(button.text(),'configure')))
        for button in scheduler.findChildren(QPushButton):button.setIcon(QIcon.fromTheme({'Criar tarefa':'list-add','Executar agora':'media-playback-start','Habilitar':'dialog-ok-apply','Desabilitar':'dialog-cancel','Remover':'edit-delete'}.get(button.text(),'view-calendar-timeline')))
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);refresh=QPushButton(QIcon.fromTheme('view-refresh'),'Recarregar');refresh.clicked.connect(self.refresh);layout.addWidget(refresh)
        self.scope.currentIndexChanged.connect(self.refresh);self.tabs.currentChanged.connect(self.refresh);self.refresh()

    def query(self,callback,done):
        generation=self.generation;task=Query(callback,self);self.jobs.add(task);task.result.connect(lambda value:done(value) if generation==self.generation else None);task.failed.connect(lambda value:self.status.setText(value) if generation==self.generation else None);task.finished.connect(lambda:self.jobs.discard(task));task.finished.connect(task.deleteLater);task.start()

    def refresh(self):
        self.generation+=1;self.environment_record=None
        scope=self.scope.currentData();page=self.tabs.currentIndex()
        if page==0:
            self.services.setRowCount(0)
            def read():
                from services_backend import inventory
                return inventory(scope)
            self.query(read,self.loaded_services)
        elif page==1:
            unit=self.log_unit
            def read_logs():
                result=subprocess.run(['/usr/bin/journalctl',*(['--user'] if scope=='user' else []),*(['-u',unit] if unit else []),'-n','500','--no-pager','-o','short-iso'],capture_output=True,text=True,timeout=15);return result.stdout+result.stderr
            self.query(read_logs,self.loaded_logs)
        elif page==2:self.variables.setRowCount(0);self.query(lambda:backend.environment(scope),self.loaded_environment)
        elif page==3:self.tasks.setRowCount(0);self.query(lambda:backend.tasks(scope),self.loaded_tasks)

    def loaded_services(self,rows):
        from services_backend import guarded
        self.services.setRowCount(len(rows))
        for i,row in enumerate(rows):
            row['protected']=guarded(row['unit']);row['protection']='Protegido' if row['protected'] else 'Administrável'
            for j,key in enumerate(('unit','active','enabled','description','protection')):
                value=str(row.get(key,''))
                if key in ('active','enabled'):value={'active':'Ativo','inactive':'Inativo','failed':'Falha','not-loaded':'Não carregado','enabled':'Habilitado','disabled':'Desabilitado','static':'Por dependência','masked':'Bloqueado','alias':'Alias','generated':'Gerado automaticamente','indirect':'Indireto','enabled-runtime':'Habilitado nesta sessão','masked-runtime':'Bloqueado nesta sessão'}.get(value,value or 'Não informado')
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row);self.services.setItem(i,j,item)
        self.filter_services();self.status.setText(str(len(rows))+' serviços apresentados pelo sistema.')

    def filter_services(self):
        query=self.filter.text().casefold()
        for i in range(self.services.rowCount()):
            item=self.services.item(i,0);record=item.data(Qt.ItemDataRole.UserRole)
            self.services.setRowHidden(i,query not in ' '.join(self.services.item(i,j).text() for j in range(self.services.columnCount())).casefold() or self.hide_essential.isChecked() and record.get('protected',False))

    def linger(self):
        import getpass
        import services_backend
        username=getpass.getuser()
        def review(record):
            enable=not record['enabled']
            text=('Permitir que os serviços pessoais habilitados de '+username+' iniciem no boot e continuem após sair? Tarefas pessoais também poderão executar sem login. Isso pode manter programas consumindo recursos em segundo plano.' if enable else 'Voltar a limitar os serviços pessoais de '+username+' à disponibilidade da sessão? Serviços e tarefas poderão parar ou deixar de executar após sair.')
            if self.confirm(text):self.command('Execução sem login',['/usr/bin/pkexec','/usr/bin/python3',str(Path(__file__).with_name('services_backend.py'))],dict(action='linger',scope='user',username=username,enabled=enable,expected=record['enabled']))
        self.query(lambda:services_backend.linger_state(username),review)

    def selected(self,table):
        row=table.item(table.currentRow(),0);return row.data(Qt.ItemDataRole.UserRole) if row else None

    def confirm(self,text):return QMessageBox.question(self,'Confirmar alteração',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes

    def command(self,title,argv,request=None):
        dialog=Command(title,argv,self,json.dumps(request).encode() if request else None);self.commands.append(dialog);dialog.completed.connect(lambda _:self.refresh())

    def apply(self,request):
        argv=['/usr/bin/python3',str(Path(__file__).with_name('administration_backend.py')),'--apply']
        if request['scope']=='system':argv.insert(0,'/usr/bin/pkexec')
        self.command('Aplicar configuração administrativa',argv,request)

    def service_action(self,action):
        row=self.selected(self.services)
        if not row:return
        unit=row['unit']
        if not re.fullmatch(r'[A-Za-z0-9_@:.\\-]+\.service',unit):return
        label={'start':'Iniciar','stop':'Parar','restart':'Reiniciar','enable':'Habilitar no início','disable':'Desabilitar no início','reload':'Recarregar','mask':'Bloquear novas ativações (sem parar o processo atual)','unmask':'Desbloquear'}.get(action,action)
        if not self.confirm(label+' · '+unit+' · '+self.scope.currentText()+'? A mudança pode afetar aplicativos dependentes.'):return
        from services_backend import guarded
        if guarded(unit):QMessageBox.information(self,'Componente essencial','Use a página específica para configurar este componente protegido.');return
        argv=['/usr/bin/python3',str(Path(__file__).with_name('services_backend.py'))]
        if self.scope.currentData()=='system':argv.insert(0,'/usr/bin/pkexec')
        self.command('Alterar serviço',argv,dict(action='control',scope=self.scope.currentData(),unit=unit,operation=action))

    def transfer_service(self,operation):
        from services_dialogs import CreateService
        from services_backend import render
        scope=self.scope.currentData()
        argv=['/usr/bin/python3',str(Path(__file__).with_name('services_backend.py'))]
        if scope=='system':argv.insert(0,'/usr/bin/pkexec')
        def create(spec):
            dialog=CreateService(scope,self,existing=spec);dialog.name.setEnabled(True)
            dialog.setWindowTitle('Revisar serviço importado' if operation=='import' else 'Duplicar serviço')
            if operation=='duplicate':dialog.name.setText(spec['name'][:55]+'-copia')
            if dialog.exec()==QDialog.DialogCode.Accepted:self.command('Criar serviço',argv,dict(scope=scope,action='create',spec=dialog.spec))
        if operation=='import':
            filename,_=QFileDialog.getOpenFileName(self,'Importar definição de serviço','','Definição JSON (*.json)')
            if not filename:return
            try:
                with open(filename,'rb') as stream:raw=stream.read(65537)
                if len(raw)>65536:raise ValueError('Definição muito grande.')
                data=json.loads(raw)
                if data.get('schema')!=1 or data.get('kind')!='linuxbr-service':raise ValueError('Formato de serviço desconhecido.')
                render(scope,data['spec'],validate_runtime=False);create(data['spec'])
            except Exception as error:QMessageBox.warning(self,'Importação não realizada',str(error))
            return
        row=self.selected(self.services)
        if not row:return
        unit=row['unit']
        def read():
            result=subprocess.run(argv,input=json.dumps(dict(action='read',scope=scope,unit=unit)),capture_output=True,text=True,timeout=120)
            if result.returncode:raise ValueError(result.stderr.strip() or 'Não foi possível ler a definição.')
            return json.loads(result.stdout)
        def loaded(record):
            if operation=='duplicate':create(record['spec'])
            elif operation=='remove':
                if self.confirm('Remover '+unit+'? É necessário que esteja parado, desabilitado e sem acionadores.'):
                    self.command('Remover serviço',argv,dict(scope=scope,action='remove',unit=unit,sha256=record['sha256']))
            elif operation=='export':
                filename,_=QFileDialog.getSaveFileName(self,'Exportar definição',unit+'.json','Definição JSON (*.json)')
                if not filename:return
                try:
                    from store_sources import atomic_write
                    atomic_write(Path(filename),json.dumps(dict(schema=1,kind='linuxbr-service',scope=scope,spec=record['spec']),ensure_ascii=False,indent=2).encode(),0o600)
                    self.status.setText('Definição exportada. Variáveis de ambiente fazem parte do arquivo; compartilhe somente após revisar.')
                except OSError as error:QMessageBox.warning(self,'Exportação não realizada',str(error))
        self.query(read,loaded)

    def create_service(self):
        from services_dialogs import CreateService
        scope=self.scope.currentData();dialog=CreateService(scope,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        argv=['/usr/bin/python3',str(Path(__file__).with_name('services_backend.py'))]
        if scope=='system':argv.insert(0,'/usr/bin/pkexec')
        self.command('Criar serviço',argv,dict(scope=scope,spec=dialog.spec))

    def service_details(self):
        from services_backend import details
        from services_dialogs import show_details
        row=self.selected(self.services)
        if not row:return
        scope=self.scope.currentData();unit=row['unit']
        self.query(lambda:details(scope,unit),lambda values:show_details(self,values))

    def edit_service(self,restore=False):
        row=self.selected(self.services)
        if not row:return
        scope=self.scope.currentData();unit=row['unit']
        if not unit.startswith('linuxbr-custom-'):
            self.override_service(unit,scope,restore);return
        argv=['/usr/bin/python3',str(Path(__file__).with_name('services_backend.py'))]
        if scope=='system':argv.insert(0,'/usr/bin/pkexec')
        def read():
            result=subprocess.run(argv,input=json.dumps(dict(action='read',scope=scope,unit=unit)),capture_output=True,text=True,timeout=120)
            if result.returncode:raise ValueError(result.stderr.strip() or 'Não foi possível ler o serviço.')
            return json.loads(result.stdout)
        def loaded(record):
            from services_dialogs import CreateService
            request=dict(scope=scope,unit=unit,sha256=record['sha256'],action='restore' if restore else 'edit')
            if restore:
                if not self.confirm('Restaurar a configuração anterior de '+unit+'? O processo atual não será reiniciado.'):return
            else:
                dialog=CreateService(scope,self,existing=record['spec'])
                if dialog.exec()!=QDialog.DialogCode.Accepted:return
                request['spec']=dialog.spec
            self.command('Restaurar serviço' if restore else 'Salvar serviço',argv,request)
        self.query(read,loaded)

    def override_service(self,unit,scope,restore):
        argv=['/usr/bin/python3',str(Path(__file__).with_name('services_backend.py'))]
        if scope=='system':argv.insert(0,'/usr/bin/pkexec')
        def read():
            result=subprocess.run(argv,input=json.dumps(dict(action='override-read',scope=scope,unit=unit)),capture_output=True,text=True,timeout=120)
            if result.returncode:raise ValueError(result.stderr.strip() or 'Não foi possível ler a personalização.')
            return json.loads(result.stdout)
        def loaded(record):
            request=dict(scope=scope,unit=unit,sha256=record['sha256'],action='override-restore' if restore else 'override')
            if restore:
                if not self.confirm('Restaurar a personalização anterior de '+unit+' sem reiniciar o processo?'):return
            else:
                from services_dialogs import OverrideService
                dialog=OverrideService(record,self)
                if dialog.exec()!=QDialog.DialogCode.Accepted:return
                request['spec']=dialog.spec
            self.command('Personalizar serviço',argv,request)
        self.query(read,loaded)

    def service_logs(self):
        row=self.selected(self.services)
        if not row:return
        self.log_unit=row['unit'];self.tabs.setCurrentIndex(1)

    def loaded_logs(self,value):
        self.log_text=value;self.filter_logs()
        self.status.setText(('Eventos de '+self.log_unit if self.log_unit else 'Eventos gerais')+' · últimos 500 registros · atualização a cada 5 segundos enquanto esta página estiver visível.')

    def filter_logs(self):
        needle=self.log_filter.text().casefold()
        text='\n'.join(line for line in self.log_text.splitlines() if needle in line.casefold())
        if text!=self.logs.toPlainText():self.logs.setPlainText(text)

    def all_logs(self):
        self.log_unit=None;self.refresh()

    def export_logs(self):
        filename,_=QFileDialog.getSaveFileName(self,'Exportar eventos','eventos.txt','Texto (*.txt)')
        if not filename:return
        try:
            from store_sources import atomic_write
            atomic_write(Path(filename),self.logs.toPlainText().encode(),0o600)
        except OSError as error:QMessageBox.warning(self,'Exportação não realizada',str(error))

    def loaded_environment(self,record):
        self.environment_record=record;self.variables.setRowCount(len(record['values']))
        for i,(key,value) in enumerate(sorted(record['values'].items())):self.variables.setItem(i,0,QTableWidgetItem(key));self.variables.setItem(i,1,QTableWidgetItem(value))
        self.status.setText('Variáveis carregadas de '+record['path'])

    def save_environment(self):
        if not self.environment_record:return
        values={}
        for i in range(self.variables.rowCount()):
            key=self.variables.item(i,0);value=self.variables.item(i,1)
            if not key or not key.text().strip():continue
            if key.text().strip() in values:QMessageBox.warning(self,'Variável repetida','Use somente uma linha por nome de variável.');return
            values[key.text().strip()]=value.text() if value else ''
        try:backend.checked_variables(values)
        except ValueError as error:QMessageBox.warning(self,'Variável inválida',str(error));return
        if self.confirm('Aplicar as variáveis de '+self.scope.currentText()+'? Novas sessões receberão os valores.'):self.apply(dict(action='environment',scope=self.scope.currentData(),values=values,sha256=self.environment_record['sha256']))

    def loaded_tasks(self,rows):
        self.tasks.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,key in enumerate(('name','calendar','enabled','next')):
                item=QTableWidgetItem(str(row.get(key,'')));item.setData(Qt.ItemDataRole.UserRole,row);self.tasks.setItem(i,j,item)
        self.status.setText(str(len(rows))+' tarefas criadas pelo gerenciador neste alcance.')

    def create_task(self):
        scope=self.scope.currentData();dialog=QDialog(self);dialog.setWindowTitle('Criar tarefa agendada');layout=QVBoxLayout(dialog);form=QFormLayout();layout.addLayout(form);name=QLineEdit();program=QLineEdit();arguments=QLineEdit();calendar=QLineEdit('*-*-* 09:00:00')
        for caption,widget in [('Nome:',name),('Programa (caminho absoluto):',program),('Argumentos:',arguments),('Agendamento:',calendar)]:form.addRow(caption,widget)
        choose=QPushButton('Selecionar programa…');choose.clicked.connect(lambda:program.setText(QFileDialog.getOpenFileName(dialog,'Selecionar programa','/usr/bin')[0] or program.text()));layout.addWidget(choose)
        note=QLabel('Exemplos: daily, Mon..Fri 09:00, *-*-* 20:30:00. Os argumentos não passam por um shell. Alcance: '+self.scope.currentText()+'.');note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:argv=[program.text().strip(),*shlex.split(arguments.text())]
        except ValueError as error:QMessageBox.warning(self,'Argumentos inválidos',str(error));return
        if scope=='system' and not self.confirm('Criar uma tarefa administrativa do computador?\n\n'+' '.join(argv)+'\n\nAgendamento: '+calendar.text()):return
        self.apply(dict(action='create-task',scope=scope,name=name.text().strip(),argv=argv,calendar=calendar.text().strip()))

    def task_action(self,action):
        row=self.selected(self.tasks)
        if row and self.confirm(action+' · '+row['name']+'? A remoção impede execuções futuras; tarefas já iniciadas podem continuar.'):self.apply(dict(action='task',scope=self.scope.currentData(),id=row['id'],operation=action))
