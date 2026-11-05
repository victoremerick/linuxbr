"""Service creation form and readable service properties."""
import getpass
import json
import shlex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QDialogButtonBox, QComboBox,
    QFileDialog, QSpinBox, QMessageBox, QScrollArea, QWidget, QCheckBox)
import services_backend


class OverrideService(QDialog):
    def __init__(self,record,parent=None):
        super().__init__(parent);self.spec=None;self.setWindowTitle('Personalizar serviço do sistema');self.resize(720,600)
        layout=QVBoxLayout(self);note=QLabel('Estas opções criam uma personalização separada. O arquivo original do pacote e o processo atual são preservados. Zero mantém a configuração fornecida; outras personalizações podem prevalecer.')
        note.setWordWrap(True);layout.addWidget(note);form=QFormLayout();layout.addLayout(form)
        current={}
        if record['content'].startswith('# LinuxBR-Override: '):
            current=json.loads(record['content'].splitlines()[0].split(': ',1)[1])
        self.restart=QComboBox()
        for label,value in [('Manter configuração do fornecedor',''),('Não reiniciar','no'),('Reiniciar após falha','on-failure')]:self.restart.addItem(label,value)
        self.restart.setCurrentIndex(self.restart.findData(current.get('restart','')));form.addRow('Após falha',self.restart)
        self.values={}
        for key,label,maximum,suffix in [('restart_seconds','Intervalo',3600,' segundos'),('memory_mib','Memória máxima',1048576,' MiB'),('cpu_percent','CPU (100% = 1 núcleo)',102400,'%'),('tasks_max','Processos e threads',1048576,'')]:
            field=QSpinBox();field.setRange(0,maximum);field.setSpecialValueText('Manter configuração do fornecedor');field.setSuffix(suffix);field.setValue(current.get(key,0));form.addRow(label,field);self.values[key]=field
        self.privileges=QCheckBox('Impedir aquisição de novos privilégios');self.privileges.setChecked(current.get('no_new_privileges',False));form.addRow(self.privileges)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.preview.setPlainText('Personalização atual:\n'+(record['content'] or '(nenhuma)')+'\nArquivo do pacote: '+record['details'].get('FragmentPath','')+'\nTodas as personalizações: '+record['details'].get('DropInPaths',''));layout.addWidget(self.preview,1)
        review=QPushButton(QIcon.fromTheme('document-preview'),'Comparar configuração proposta');review.clicked.connect(lambda:self.preview.setPlainText('Atual:\n'+record['content']+'\nProposta:\n'+services_backend.override_render(self.read())));layout.addWidget(review)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def read(self):return dict(restart=self.restart.currentData(),no_new_privileges=self.privileges.isChecked(),**{key:field.value() for key,field in self.values.items()})

    def save(self):
        self.spec=self.read();services_backend.override_render(self.spec);self.accept()


class CreateService(QDialog):
    def __init__(self, scope, parent=None, existing=None):
        super().__init__(parent)
        self.scope = scope
        self.spec = None
        self.setWindowTitle('Criar serviço — ' + ('Minha conta' if scope == 'user' else 'Todo o computador'))
        self.setWindowIcon(QIcon.fromTheme('preferences-system-services'))
        self.resize(730, 650)
        layout = QVBoxLayout(self)
        note = QLabel('Altere a configuração e revise antes de salvar. A versão anterior ficará disponível para restauração. O processo atual não será reiniciado automaticamente.' if existing else 'Configure um programa para execução em segundo plano. O serviço será criado parado; você poderá iniciar e habilitar depois. Aplicativos com janelas devem usar Programas de inicialização.')
        note.setWordWrap(True)
        layout.addWidget(note)
        lifecycle=QLabel('Serviços da sua conta executam durante a sessão. Para iniciar no boot e continuar após sair, habilite explicitamente Execução sem login na lista de serviços.' if scope=='user' else 'Serviços do computador podem executar desde o boot, mesmo sem uma pessoa conectada. A conta e o grupo definem os privilégios do programa.')
        lifecycle.setWordWrap(True);layout.addWidget(lifecycle)
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        content=QWidget();form = QFormLayout(content)
        scroll.setWidget(content);layout.addWidget(scroll,1)
        self.name = QLineEdit()
        self.name.setPlaceholderText('meu-servico')
        self.description = QLineEdit()
        self.program = QLineEdit()
        picker = QWidget()
        row = QHBoxLayout(picker)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.program)
        browse = QPushButton(QIcon.fromTheme('document-open'), 'Procurar…')
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        self.arguments = QLineEdit()
        self.arguments.setPlaceholderText('Use aspas para argumentos que contenham espaços')
        self.directory = QLineEdit()
        self.user = QLineEdit(getpass.getuser())
        self.user.setEnabled(scope == 'system')
        self.group=QLineEdit();self.group.setPlaceholderText('Grupo principal da conta, se vazio');self.group.setEnabled(scope=='system')
        self.restart = QComboBox()
        self.restart.addItem('Não reiniciar automaticamente', 'no')
        self.restart.addItem('Reiniciar após falha, com limite de tentativas', 'on-failure')
        self.delay = QSpinBox()
        self.delay.setRange(1, 3600)
        self.delay.setValue(10)
        self.delay.setSuffix(' segundos')
        self.environment = QPlainTextEdit()
        self.environment.setMaximumHeight(85)
        self.environment.setPlaceholderText('Uma variável por linha: NOME=valor\nNão coloque senhas nesta configuração.')
        for label, field in [('Identificador', self.name), ('Descrição', self.description),
                             ('Programa', picker), ('Argumentos', self.arguments),
                             ('Pasta de trabalho', self.directory), ('Executar como', self.user),
                             ('Grupo de execução',self.group),
                             ('Após falha', self.restart), ('Intervalo', self.delay),
                             ('Variáveis de ambiente', self.environment)]:
            form.addRow(label, field)
        self.timing={}
        for key,label,minimum,maximum,default in [('restart_burst','Máximo de inícios no intervalo',1,20,3),('restart_window','Intervalo de contagem (segundos)',30,3600,300),('start_seconds','Tempo máximo para iniciar (segundos)',1,3600,90),('stop_seconds','Tempo máximo para parar (segundos)',1,3600,30),('start_delay','Aguardar antes de executar (segundos)',0,300,0)]:
            field=QSpinBox();field.setRange(minimum,maximum);field.setValue(default);self.timing[key]=field;form.addRow(label,field)
        self.mask=QLineEdit('0077');form.addRow('Permissão padrão dos novos arquivos (umask)',self.mask)
        self.dependencies={}
        for key,label in [('requires','Depende de'),('wants','Dependências opcionais'),('after','Iniciar após')]:
            field=QLineEdit();field.setPlaceholderText('Unidades separadas por espaços, como network-online.target')
            self.dependencies[key]=field;form.addRow(label,field)
        self.limits={}
        for key,label,maximum,suffix in [('memory_mib','Memória máxima',1048576,' MiB'),('cpu_percent','Cota de CPU (100% = 1 núcleo)',102400,'%'),('tasks_max','Máximo de processos e threads',1048576,'')]:
            field=QSpinBox();field.setRange(0,maximum);field.setSpecialValueText('Sem limite específico');field.setSuffix(suffix)
            self.limits[key]=field;form.addRow(label,field)
        self.isolation=QCheckBox('Sistema de arquivos somente leitura, sem acesso às pastas pessoais')
        self.isolation.setEnabled(scope=='system');form.addRow('Isolamento',self.isolation)
        self.private_network=QCheckBox('Isolar a rede: somente interface local');self.private_network.setEnabled(scope=='system');form.addRow('Acesso à rede',self.private_network)
        explanation=QLabel('No isolamento, o programa só poderá gravar na pasta temporária privada. Dependências obrigatórias também serão iniciadas. A ordem de início não cria dependência por si só.')
        explanation.setWordWrap(True);form.addRow(explanation)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(125)
        self.preview.hide()
        layout.addWidget(self.preview)
        show = QPushButton(QIcon.fromTheme('document-preview'), 'Revisar configuração')
        show.clicked.connect(self.review)
        layout.addWidget(show)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salvar alterações' if existing else 'Criar serviço')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if existing:
            self.setWindowTitle('Editar serviço — ' + existing['name'])
            self.name.setText(existing['name']);self.name.setEnabled(False)
            self.description.setText(existing.get('description',''))
            self.program.setText(existing['argv'][0])
            self.arguments.setText(shlex.join(existing['argv'][1:]))
            self.directory.setText(existing.get('directory',''))
            self.user.setText(existing.get('user',getpass.getuser()))
            self.group.setText(existing.get('group',''));self.mask.setText(existing.get('umask','0077'))
            for key,field in self.timing.items():field.setValue(existing.get(key,field.value()))
            self.private_network.setChecked(existing.get('private_network',False))
            self.restart.setCurrentIndex(self.restart.findData(existing.get('restart','no')))
            self.delay.setValue(existing.get('restart_seconds',10))
            self.environment.setPlainText('\n'.join(key+'='+value for key,value in existing.get('environment',{}).items()))
            for key,field in self.dependencies.items():field.setText(' '.join(existing.get(key,[])))
            for key,field in self.limits.items():field.setValue(existing.get(key,0))
            self.isolation.setChecked(existing.get('isolation',False))

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Selecionar programa', '/usr/bin')
        if path:
            self.program.setText(path)

    def read(self):
        environment = {}
        for line in self.environment.toPlainText().splitlines():
            if not line.strip():
                continue
            if '=' not in line:
                raise ValueError('Use NOME=valor em cada variável.')
            key, value = line.split('=', 1)
            if key in environment:
                raise ValueError('Variável repetida: ' + key)
            environment[key] = value
        spec = dict(name=self.name.text().strip(), description=self.description.text(),
                    argv=[self.program.text(), *shlex.split(self.arguments.text())],
                    directory=self.directory.text(), user=self.user.text(),
                    restart=self.restart.currentData(), restart_seconds=self.delay.value(),
                    environment=environment)
        spec.update({key:field.text().split() for key,field in self.dependencies.items()})
        spec.update({key:field.value() for key,field in self.limits.items()})
        spec['isolation']=self.isolation.isChecked()
        spec.update({key:field.value() for key,field in self.timing.items()});spec['umask']=self.mask.text();spec['private_network']=self.private_network.isChecked()
        if self.scope=='system':spec['group']=self.group.text()
        _, rendered = services_backend.render(self.scope, spec)
        return spec, rendered

    def review(self):
        try:
            _, rendered = self.read()
            self.preview.setPlainText(rendered)
            self.preview.show()
        except Exception as error:
            QMessageBox.warning(self, 'Revise os campos', str(error))

    def save(self):
        try:
            spec, _ = self.read()
        except Exception as error:
            QMessageBox.warning(self, 'Revise os campos', str(error))
            return
        if self.scope == 'system' and spec['user'] == 'root':
            if QMessageBox.warning(self, 'Privilégios administrativos', 'O programa será executado com controle administrativo do computador quando iniciado. Deseja criar assim?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
                return
        self.spec = spec
        self.accept()


def show_details(parent, values):
    dialog = QDialog(parent)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.setWindowTitle('Propriedades do serviço')
    dialog.setWindowIcon(QIcon.fromTheme('preferences-system-services'))
    dialog.resize(760, 580)
    layout = QVBoxLayout(dialog)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    form = QFormLayout(content)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    labels = [('Id', 'Identificador'), ('Description', 'Descrição'), ('LoadState', 'Carregamento'),
              ('ActiveState', 'Estado'), ('SubState', 'Situação'), ('UnitFileState', 'Inicialização'),
              ('MainPID', 'Processo'), ('User', 'Conta configurada'), ('WorkingDirectory', 'Pasta de trabalho'),
              ('MemoryCurrent', 'Memória atual'), ('CPUUsageNSec', 'Tempo de CPU acumulado'),
              ('NRestarts', 'Reinícios automáticos'), ('Result', 'Último resultado'),
              ('ExecMainStatus', 'Código de saída'), ('ActiveEnterTimestamp', 'Ativo desde'),
              ('Restart', 'Política de reinício'), ('FragmentPath', 'Arquivo da unidade'),
              ('DropInPaths', 'Personalizações'), ('Requires', 'Dependências obrigatórias'),
              ('Wants', 'Dependências opcionais'), ('After', 'Iniciar após'), ('TriggeredBy', 'Ativado por'),
              ('RequiredBy','Dependentes obrigatórios'),('WantedBy','Dependentes opcionais'),
              ('Group','Grupo configurado'),('Package','Pacote de origem'),('Maintainer','Mantenedor do pacote'),
              ('Protection','Proteção nesta interface'),('StartLimitBurst','Limite de inícios'),
              ('StartLimitIntervalUSec','Intervalo do limite'),('TimeoutStartUSec','Tempo máximo de início'),
              ('TimeoutStopUSec','Tempo máximo de parada'),('PrivateNetwork','Rede isolada'),('UMask','Permissão padrão de arquivos')]
    translations = {'active': 'Ativo', 'inactive': 'Inativo', 'failed': 'Falha', 'running': 'Em execução',
                    'dead': 'Parado', 'loaded': 'Carregado', 'enabled': 'Habilitado', 'disabled': 'Desabilitado',
                    'static': 'Ativado por outros componentes', 'masked': 'Bloqueado',
                    'success': 'Concluído sem erro', 'on-failure': 'Reiniciar após falha', 'no': 'Não reiniciar'}
    for key, label in labels:
        value = values.get(key, '')
        if key=='User' and not value:value='Minha conta' if values.get('Scope')=='user' else 'Usuário dinâmico' if values.get('DynamicUser')=='yes' else 'root (padrão do serviço de sistema)'
        if key in ('MemoryCurrent', 'CPUUsageNSec'):
            if value.isdigit() and int(value) < 2**64 - 1:
                value = f'{int(value)/1024**2:.1f} MiB' if key == 'MemoryCurrent' else f'{int(value)/1e9:.2f} segundos'
            else:
                value = 'Não disponível'
        elif key in ('ActiveState', 'SubState', 'LoadState', 'UnitFileState', 'Result', 'Restart'):
            value = translations.get(value, value)
        field = QLabel(value or 'Não informado')
        field.setTextFormat(Qt.TextFormat.PlainText)
        field.setWordWrap(True)
        field.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(label, field)
    scroll.setWidget(content)
    layout.addWidget(scroll)
    location=values.get('FragmentPath','')
    if location.startswith('/'):
        from pathlib import Path
        from PyQt6.QtCore import QProcess
        open_folder=QPushButton(QIcon.fromTheme('folder-open'),'Abrir pasta da configuração')
        open_folder.clicked.connect(lambda:QProcess.startDetached('/usr/bin/xdg-open',[str(Path(location).parent)]));layout.addWidget(open_folder)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.close)
    layout.addWidget(buttons)
    dialog.show()
    return dialog
