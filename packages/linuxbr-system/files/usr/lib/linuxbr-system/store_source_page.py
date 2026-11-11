"""Source management pages for the application store."""
import json
import base64
from pathlib import Path
import re
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,
    QTableWidgetItem,QHeaderView,QMessageBox,QDialog,QFormLayout,QLineEdit,QComboBox,QDialogButtonBox,QPlainTextEdit,QFileDialog,QInputDialog)
from PyQt6.QtGui import QIcon
from desktop_jobs import Query,Command
import store_sources as backend
import catalog_sources
import signed_catalog
import store_optional


class Sources(QWidget):
    optional_changed = pyqtSignal()
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=set();self.commands=[];layout=QVBoxLayout(self)
        heading=QLabel('Fontes de aplicativos');heading.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(heading)
        note=QLabel('Uma fonte fornece programas e atualizações. Adicione somente servidores em que você confia. APT altera o sistema; Flatpak distingue sua conta e o sistema. Catálogos web e Windows são gerenciados separadamente.');note.setWordWrap(True);layout.addWidget(note)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Formato','Nome','Alcance / endereço','Estado']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows);self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers);layout.addWidget(self.table,1)
        row=QHBoxLayout()
        for text,icon,callback in [('Adicionar fonte','list-add',self.add),('Habilitar / desabilitar','dialog-ok-apply',self.toggle),('Editar fonte APT própria','configure',self.edit),('Remover fonte','edit-delete',self.remove),('Ver detalhes','document-properties',self.details),('Atualizar lista','view-refresh',self.refresh)]:
            button=QPushButton(QIcon.fromTheme(icon),text);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.refresh()
        setup=QPushButton(QIcon.fromTheme('preferences-system'),'Configurar Snap ou Homebrew…')
        setup.clicked.connect(self.setup_optional);layout.addWidget(setup)
        row=QHBoxLayout();apt=QPushButton(QIcon.fromTheme('view-refresh'),'Atualizar índices APT');apt.clicked.connect(self.refresh_apt);row.addWidget(apt)
        flatpak=QPushButton(QIcon.fromTheme('view-refresh'),'Atualizar catálogo Flatpak da minha conta');flatpak.clicked.connect(lambda:self.command('Atualizar catálogo Flatpak',['/usr/bin/flatpak','--user','update','--appstream']));row.addWidget(flatpak);layout.addLayout(row)
        signed=QPushButton(QIcon.fromTheme('security-high'),'Atualizar catálogos assinados');signed.clicked.connect(self.refresh_signed);layout.addWidget(signed)
        trust=QPushButton(QIcon.fromTheme('view-certificate'),'Revisar chave do catálogo selecionado');trust.clicked.connect(self.review_key);layout.addWidget(trust)
        key=QPushButton(QIcon.fromTheme('dialog-password'),'Importar chave pública APT…');key.clicked.connect(self.import_key);layout.addWidget(key)

    def import_key(self):
        path,_=QFileDialog.getOpenFileName(self,'Chave pública do fornecedor','','Chave OpenPGP (*.asc *.gpg);;Todos os arquivos (*)')
        if not path:return
        try:
            with open(path,'rb') as stream:data=stream.read(32769)
            fingerprint=backend.inspect_key(data);name,ok=QInputDialog.getText(self,'Identificador da chave','Letras minúsculas, números e traços:')
            if not ok:return
            if not backend.SLUG.fullmatch(name):raise ValueError('Identificador inválido.')
            if not self.confirm('Confira esta impressão digital com o fornecedor, por um canal independente:\n\n'+fingerprint+'\n\nImportar a chave pública? Ela será usada somente por fontes que a indicarem em Signed-By.'):return
            suffix='.asc' if data.lstrip().startswith(b'-----BEGIN PGP PUBLIC KEY BLOCK-----') else '.gpg'
            self.apt(dict(action='install-key',name=name,data=base64.b64encode(data).decode(),fingerprint=fingerprint));self.status.setText('Após concluir a autorização, selecione /etc/apt/keyrings/linuxbr-'+name+suffix+' ao cadastrar a fonte.')
        except (OSError,ValueError) as error:QMessageBox.warning(self,'Chave não importada',str(error))

    def refresh_apt(self):
        dialog=Command('Atualizar índices de pacotes',['/usr/bin/python3',str(Path(__file__).with_name('store_transactions.py')),'--refresh-indexes'],self,structured=True);self.commands.append(dialog)

    def refresh(self):
        if self.jobs:return
        query=Query(lambda:backend.apt_sources()+backend.flatpak_sources('user')+backend.flatpak_sources('system')+catalog_sources.sources()+signed_catalog.sources()+store_optional.sources(),self);self.jobs.add(query);query.result.connect(self.loaded);query.failed.connect(self.status.setText);query.finished.connect(lambda:self.jobs.discard(query));query.finished.connect(query.deleteLater);query.start();self.status.setText('Consultando fontes configuradas…')

    def loaded(self,rows):
        self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            state = row.get('status') or ('Habilitada' if row['enabled'] else 'Desabilitada')
            for j,value in enumerate([row['kind'],row['name'],row.get('path',row.get('scope','')+' · '+row.get('url','')),state]):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row);self.table.setItem(i,j,item)
        self.status.setText(str(len(rows))+' fontes. Alterar uma fonte não atualiza os índices automaticamente.')

    def selected(self):
        item=self.table.item(self.table.currentRow(),0);return item.data(Qt.ItemDataRole.UserRole) if item else None

    def command(self,title,argv,request=None,success_message=None):
        dialog=Command(title,argv,self,json.dumps(request).encode() if request else None,success_message=success_message);self.commands.append(dialog);dialog.completed.connect(lambda _:self.refresh())

    def apt(self,request):
        messages={'add':'Fonte adicionada. Atualize os índices APT para consultar seus aplicativos.','edit':'Fonte atualizada. Atualize os índices APT para consultar os aplicativos disponíveis.','enable':'Fonte habilitada. Atualize os índices APT para consultar seus aplicativos.','disable':'Fonte desabilitada. Os programas já instalados permanecem no computador.','remove':'Fonte removida. Os programas já instalados permanecem no computador.','install-key':'Chave pública importada. Selecione essa chave ao cadastrar a fonte do fornecedor.'}
        self.command('Alterar fonte APT',['/usr/bin/pkexec','/usr/bin/python3',str(Path(__file__).with_name('store_sources.py')),'--apply'],request,success_message=messages.get(request['action'],'Fontes de aplicativos atualizadas.'))

    def confirm(self,text):return QMessageBox.question(self,'Confirmar fonte',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes

    def toggle(self):
        row=self.selected()
        if row and row.get('optional_manager'):
            self.toggle_optional(row)
            return
        if not row or not self.confirm(('Desabilitar' if row['enabled'] else 'Habilitar')+' a fonte '+row['name']+'? Em APT, a ação abrange todas as entradas do arquivo exibido.'):return
        if row['kind']=='Catálogo assinado':signed_catalog.change(row['name']);self.refresh()
        elif row['kind']=='Catálogo':catalog_sources.change(row['name']);self.refresh()
        elif row['kind']=='APT':self.apt(dict(action='disable' if row['enabled'] else 'enable',path=row['path'],sha256=row['sha256']))
        else:self.command('Alterar fonte Flatpak',['/usr/bin/flatpak','--'+row['scope'],'remote-modify','--disable' if row['enabled'] else '--enable',row['name']])

    def remove(self):
        row=self.selected()
        if row and row.get('optional_manager'):
            if row['enabled']:
                self.toggle_optional(row)
            return
        if not row or not self.confirm('Remover a fonte '+row['name']+'? Os programas instalados permanecem, mas podem deixar de receber atualizações por ela.'):return
        if row['kind']=='Catálogo assinado':signed_catalog.change(row['name'],True);self.refresh()
        elif row['kind']=='Catálogo':catalog_sources.change(row['name'],True);self.refresh()
        elif row['kind']=='APT':self.apt(dict(action='remove',path=row['path'],sha256=row['sha256']))
        else:self.command('Remover fonte Flatpak',['/usr/bin/flatpak','--'+row['scope'],'remote-delete','--noninteractive',row['name']])

    def toggle_optional(self, row):
        action = 'Desabilitar' if row['enabled'] else 'Habilitar'
        if not self.confirm(action + ' ' + row['name'] + ' nesta conta? Os aplicativos instalados permanecem no computador.'):
            return
        try:
            store_optional.set_enabled(row['optional_manager'], not row['enabled'])
            self.optional_changed.emit()
            self.refresh()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Fonte não alterada', str(error))

    def setup_optional(self):
        row = self.selected()
        if not row or not row.get('optional_manager'):
            QMessageBox.information(self, 'Fontes opcionais', 'Selecione Snap Store ou Homebrew Core na lista.')
            return
        manager = row['optional_manager']
        if not store_optional.allowed(manager):
            QMessageBox.information(self, 'Fonte bloqueada', 'A organização bloqueou esta fonte na Loja.')
        elif manager == 'snap':
            if row.get('confinement') == 'partial':
                QMessageBox.information(self, 'Confinamento da Snap Store', row['content'])
                return
            if self.confirm('Abrir o pacote snapd no gerenciador APT da Loja? Instale-o e confira o serviço antes de habilitar a fonte.'):
                from store_operations import Operations
                window = self.window()
                if not hasattr(window, 'operations'):
                    window.operations = Operations(window)
                window.operations.set_item(dict(id='deb:snapd', name='snapd', kind='linux', repository_package='snapd'))
        elif self.confirm('Abrir o guia oficial do Homebrew para Linux? Use o prefixo padrão e retorne à Loja na conta proprietária.'):
            self.command('Abrir guia do Homebrew', ['/usr/bin/xdg-open', 'https://docs.brew.sh/Homebrew-on-Linux'])

    def details(self):
        row=self.selected()
        if row:QMessageBox.information(self,'Detalhes da fonte',row.get('content',json.dumps(row,ensure_ascii=False,indent=2)))

    def edit(self):
        row=self.selected()
        if not row:return
        if row['kind']!='APT' or not row.get('managed'):QMessageBox.information(self,'Fonte existente','Fontes APT externas são preservadas; use habilitar/desabilitar. Somente fontes criadas nesta Loja têm seus campos substituídos pelo editor.');return
        self.add(row)

    def add(self,existing=None):
        if isinstance(existing,bool):existing=None
        dialog=QDialog(self);dialog.setWindowTitle('Editar fonte' if existing else 'Adicionar fonte');dialog.resize(650,440);layout=QVBoxLayout(dialog);form=QFormLayout();layout.addLayout(form)
        kind=QComboBox();kind.addItems(['APT assinado','Flatpak (.flatpakrepo)','Catálogo web/Windows (JSON)','Catálogo de webapps assinado']);scope=QComboBox();scope.addItem('Minha conta','user');scope.addItem('Todo o sistema','system');name=QLineEdit();url=QLineEdit();suite=QLineEdit('trixie');components=QLineEdit('main');key=QLineEdit('/usr/share/keyrings/debian-archive-keyring.gpg')
        for caption,widget in [('Formato:',kind),('Identificador:',name),('URL HTTPS:',url),('Suíte APT:',suite),('Componentes APT:',components),('Chave APT instalada:',key),('Alcance Flatpak:',scope)]:form.addRow(caption,widget)
        def fields():
            for widget in (suite,components,key):widget.setEnabled(kind.currentIndex()==0)
            scope.setEnabled(kind.currentIndex()==1)
        kind.currentIndexChanged.connect(fields);fields()
        if existing:
            kind.setEnabled(False);name.setEnabled(False);name.setText(existing['name'].removeprefix('linuxbr-extra-').removesuffix('.sources'))
            values=dict(re.findall(r'^([A-Za-z-]+):\s*(.*)$',existing['content'],re.M));url.setText(values.get('URIs',''));suite.setText(values.get('Suites','trixie'));components.setText(values.get('Components','main'));key.setText(values.get('Signed-By',''))
        note=QLabel('APT exige assinatura e uma chave instalada em /etc/apt/keyrings ou /usr/share/keyrings. Flatpak recebe o descritor oficial .flatpakrepo, incluindo sua chave. A confiança no fornecedor deve ser conferida antes de adicionar.');note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:
            backend.https_url(url.text().strip())
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,59}',name.text().strip()):raise ValueError('Use um identificador com letras minúsculas, números e traços.')
            if kind.currentIndex()==0:
                request=dict(action='edit' if existing else 'add',name=name.text().strip(),url=url.text().strip(),suite=suite.text().strip(),components=components.text().strip(),key=key.text().strip())
                if existing:request.update(path=existing['path'],sha256=existing['sha256'])
                backend.source_text(request);self.apt(request)
            elif kind.currentIndex()==1:
                if not url.text().strip().split('?')[0].endswith('.flatpakrepo'):raise ValueError('Informe o endereço do descritor oficial .flatpakrepo.')
                self.command('Adicionar fonte Flatpak',['/usr/bin/flatpak','--'+scope.currentData(),'remote-add','--noninteractive','--from',name.text().strip(),url.text().strip()])
            elif kind.currentIndex()==3:
                title=name.text().strip();address=url.text().strip()
                def inspected(descriptor):
                    if not self.confirm('Fonte: '+descriptor['name']+'\nEndereço: '+descriptor['catalog_url']+'\n\nConfira a impressão digital com o fornecedor:\n'+descriptor['fingerprint']+'\n\nConfiar nesta chave para os catálogos desta fonte?'):return
                    self.signed_query(lambda:signed_catalog.add(title,descriptor,descriptor['fingerprint']),lambda count:self.status.setText(str(count)+' aplicativos importados de uma fonte assinada.'))
                self.signed_query(lambda:signed_catalog.inspect(address),inspected)
            else:
                title=name.text().strip();address=url.text().strip();query=Query(lambda:catalog_sources.add(title,address),self);self.jobs.add(query);query.result.connect(lambda count:self.status.setText(str(count)+' aplicativos importados. Atualize o catálogo da Loja para encontrá-los.'));query.failed.connect(lambda error:QMessageBox.warning(self,'Catálogo não importado',error));query.finished.connect(lambda:self.jobs.discard(query));query.finished.connect(query.deleteLater);query.finished.connect(self.refresh);query.start()
        except (OSError,ValueError) as error:QMessageBox.warning(self,'Fonte inválida',str(error))

    def signed_query(self,operation,done):
        query=Query(operation,self);self.jobs.add(query);query.result.connect(done);query.failed.connect(self.status.setText);query.finished.connect(lambda:self.jobs.discard(query));query.finished.connect(query.deleteLater);query.finished.connect(self.refresh);query.start()

    def refresh_signed(self):
        def refresh():
            results=[]
            for source in signed_catalog.sources():
                if not source['enabled']:continue
                try:results.append(source['name']+': '+str(signed_catalog.refresh(source['name']))+' registros verificados')
                except Exception as error:results.append(source['name']+': '+str(error))
            return '\n'.join(results) or 'Nenhuma fonte assinada cadastrada.'
        self.signed_query(refresh,self.status.setText)

    def review_key(self):
        row=self.selected()
        if not row or row['kind']!='Catálogo assinado':
            self.status.setText('Selecione um catálogo assinado para revisar sua chave.');return
        old=row['fingerprint']
        def reviewed(descriptor):
            if descriptor['fingerprint']==old:
                self.status.setText('A fonte continua usando a mesma chave.');return
            if not self.confirm('A chave de assinatura mudou. Confirme a nova impressão digital com o responsável pela fonte por outro canal antes de continuar.\n\nAnterior: '+old+'\n\nNova: '+descriptor['fingerprint']+'\n\nAutorizar a substituição?'):return
            self.signed_query(lambda:signed_catalog.rotate(row['name'],descriptor,old,descriptor['fingerprint']),lambda count:self.status.setText('Chave substituída; '+str(count)+' registros verificados.'))
        self.signed_query(lambda:signed_catalog.inspect(row['url']),reviewed)
