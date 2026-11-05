"""Clipboard preferences and application permission pages."""
import configparser
import json
import os
from pathlib import Path
import subprocess
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QSpinBox,QCheckBox,QPushButton,QComboBox,QPlainTextEdit,QMessageBox
from desktop_jobs import Query,Command
import app_permissions


class Clipboard(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);title=QLabel('Área de transferência');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        note=QLabel('Gerencie o histórico local de itens copiados. Dados sensíveis copiados por aplicativos podem aparecer no histórico; a limpeza abaixo não altera seus documentos.');note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();layout.addLayout(form);self.size=QSpinBox();self.size.setRange(1,2048);form.addRow('Máximo de itens:',self.size)
        self.options={}
        for key,label,default in [('KeepClipboardContents','Lembrar histórico entre sessões',True),('NoEmptyClipboard','Manter conteúdo quando o aplicativo de origem fechar',True),('SyncClipboards','Copiar também o texto selecionado com o mouse',False),('IgnoreSelection','Ignorar seleções não copiadas explicitamente',True),('IgnoreImages','Não armazenar imagens no histórico',True)]:
            check=QCheckBox(label);self.options[key]=(check,default);form.addRow(check)
        row=QHBoxLayout()
        for label,icon,callback in [('Aplicar','dialog-ok-apply',self.apply),('Recarregar','view-refresh',self.load),('Abrir histórico','edit-paste',lambda:self.call('showKlipperPopupMenu')),('Limpar histórico…','edit-clear-history',self.clear)]:
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);layout.addStretch();self.load()

    def load(self):
        parser=configparser.ConfigParser(interpolation=None,strict=False);parser.optionxform=str
        try:
            parser.read(Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'klipperrc');section=parser['General'] if parser.has_section('General') else {}
            self.size.setValue(int(section.get('MaxClipItems',20)))
            for key,(check,default) in self.options.items():check.setChecked(str(section.get(key,str(default))).casefold()=='true')
            self.status.setText('Preferências carregadas. Nenhum conteúdo do histórico é exibido nesta página.')
        except (OSError,ValueError,configparser.Error) as error:self.status.setText('Não foi possível ler as preferências: '+str(error))

    def call(self,method):
        try:
            import dbus
            interface=dbus.Interface(dbus.SessionBus().get_object('org.kde.klipper','/klipper'),'org.kde.klipper.klipper');getattr(interface,method)();return True
        except Exception as error:self.status.setText('Não foi possível acessar a área de transferência da sessão: '+str(error));return False

    def apply(self):
        try:
            values=dict(MaxClipItems=str(self.size.value()));values.update({key:'true' if check.isChecked() else 'false' for key,(check,_) in self.options.items()})
            for key,value in values.items():subprocess.run(['/usr/bin/kwriteconfig6','--file','klipperrc','--group','General','--key',key,value],check=True,capture_output=True,timeout=5)
            if self.call('reloadConfig'):self.status.setText('Preferências aplicadas à área de transferência desta sessão.')
        except (OSError,subprocess.SubprocessError) as error:self.status.setText('Não foi possível aplicar todas as preferências: '+str(error))

    def clear(self):
        if QMessageBox.question(self,'Limpar histórico','Apagar o histórico local de itens copiados? Esta ação não pode ser desfeita.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:
            if self.call('clearClipboardHistory'):self.status.setText('Histórico limpo. O conteúdo atual pode continuar disponível no aplicativo de origem.')


class Permissions(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=set();self.commands=[];layout=QVBoxLayout(self);title=QLabel('Permissões de aplicativos');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        note=QLabel('Estas opções alteram permissões Flatpak para sua conta, incluindo aplicativos instalados no sistema. Programas nativos sem isolamento e permissões dos sites têm controles diferentes. Restrições de pastas não anulam outras concessões mais amplas; confira o relatório efetivo abaixo.');note.setWordWrap(True);layout.addWidget(note)
        self.apps=QComboBox();self.apps.setAccessibleName('Aplicativo Flatpak');layout.addWidget(self.apps);form=QFormLayout();layout.addLayout(form);self.options={}
        for key,label in [('camera','Câmera pelo portal'),('audio','Som e microfone pelo acesso PulseAudio'),('network','Acesso direto à rede'),('home','Concessão à pasta pessoal'),('documents','Concessão a Documentos'),('downloads','Concessão a Downloads'),('devices','Concessão ampla a dispositivos')]:
            combo=QComboBox();combo.addItem('Manter configuração atual',None);combo.addItem('Permitir',True);combo.addItem('Revogar esta concessão',False);form.addRow(label+':',combo);self.options[key]=combo
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setAccessibleName('Permissões efetivas informadas pelo Flatpak');layout.addWidget(self.details,1)
        row=QHBoxLayout()
        for label,icon,callback in [('Aplicar alterações','dialog-ok-apply',self.apply),('Recarregar aplicativos','view-refresh',self.refresh),('Restaurar ajustes Flatpak…','edit-undo',self.reset),('Esquecer decisões dos portais…','edit-clear-history',self.reset_portals)]:
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.apps.currentIndexChanged.connect(self.load_details);self.refresh()

    def query(self,callback,done):
        task=Query(callback,self);self.jobs.add(task);task.result.connect(done);task.failed.connect(self.status.setText);task.finished.connect(lambda:self.jobs.discard(task));task.finished.connect(task.deleteLater);task.start()

    def refresh(self):
        def loaded(rows):
            self.apps.clear()
            for row in rows:self.apps.addItem(row['name']+' · '+row['id']+' · '+('sua conta' if row['scope']=='user' else 'sistema'),row)
            self.status.setText(str(len(rows))+' instalações Flatpak encontradas.' if rows else 'Nenhum aplicativo Flatpak instalado. Aplicativos nativos comuns não oferecem estes mesmos controles de isolamento.')
        self.query(app_permissions.applications,loaded)

    def load_details(self):
        item=self.apps.currentData()
        for combo in self.options.values():combo.setCurrentIndex(0)
        if item:self.query(lambda:app_permissions.details(item['id'],item['scope']),self.details.setPlainText)
        else:self.details.clear()

    def command(self,title,argv,request=None):
        dialog=Command(title,argv,self,json.dumps(request).encode() if request else None);self.commands.append(dialog);dialog.completed.connect(lambda _:self.load_details())

    def apply(self):
        row=self.apps.currentData()
        if not row:return
        changes={key:combo.currentData() for key,combo in self.options.items() if combo.currentData() is not None}
        if not changes:return
        self.command('Aplicar permissões',['/usr/bin/python3',str(Path(__file__).with_name('app_permissions.py')),'--apply'],dict(app=row['id'],changes=changes))

    def reset(self):
        row=self.apps.currentData()
        if row and QMessageBox.question(self,'Restaurar permissões','Remover todos os ajustes Flatpak feitos pela sua conta para '+row['name']+'? As permissões do pacote e as configurações globais voltarão a valer.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.command('Restaurar ajustes Flatpak',['/usr/bin/flatpak','override','--user','--reset',row['id']])

    def reset_portals(self):
        row=self.apps.currentData()
        if row and QMessageBox.question(self,'Esquecer decisões dos portais','Esquecer decisões dos portais para '+row['name']+'? O aplicativo poderá solicitar as permissões novamente.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.command('Esquecer permissões dos portais',['/usr/bin/flatpak','permission-reset',row['id']])
