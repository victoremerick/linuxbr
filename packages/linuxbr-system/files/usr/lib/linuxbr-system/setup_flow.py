"""Optional first-use checklist; completion is explicitly marked by the user."""
import json
import os
from pathlib import Path
import sys
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QLabel, QMessageBox,
                            QPushButton, QLineEdit, QVBoxLayout, QWizard, QWizardPage)
from recovery import launch
from visual_style import BUTTONS

STEPS = [
    ('accounts','Conferir sua conta','Confira o nome da conta, a imagem e as opções de acesso. Use uma conta própria para cada pessoa.',
     'Abrir contas',['linuxbr-system','--page','Contas']),
    ('migration','Trazer meus arquivos','Copie pastas de um disco Windows ou de uma cópia de segurança e confira a integridade, preservando a origem.',
     'Trazer meus arquivos',['linuxbr-migration']),
    ('network','Conectar à internet','Confira o Wi-Fi ou a rede por cabo e abra um site para confirmar a conexão.',
     'Abrir rede',['linuxbr-system','--page','Rede']),
    ('region','Conferir idioma e teclado','Escolha seu fuso horário e confira cedilha, acentos, data e teclado ABNT2.',
     'Abrir hora e idioma',['linuxbr-system','--page','Hora e idioma']),
    ('display','Ajustar a tela','Confira resolução e escala para deixar textos e botões confortáveis.',
     'Abrir telas',['linuxbr-system','--page','Telas']),
    ('devices','Conferir som e dispositivos','Confira áudio, microfone, impressora e os dispositivos que você usa. Drivers dependem do modelo do equipamento.',
     'Abrir dispositivos',['linuxbr-system','--page','Dispositivos']),
    ('daily','Conferir as tarefas do dia a dia','Configure pendrives, pastas compartilhadas, impressoras e os aplicativos que abrem seus arquivos.',
     'Abrir uso diário',['linuxbr-system','--page','Uso diário']),
    ('backup','Proteger seus arquivos','Conecte um disco externo e escolha um plano de backup. Prefira cópias com versões para recuperar alterações e exclusões.',
     'Configurar backup',['linuxbr-recovery']),
    ('updates','Conferir atualizações','Abra a Loja Linux BR, confira as fontes e revise as atualizações disponíveis.',
     'Abrir atualizações',['linuxbr-store','--updates']),
    ('apps','Escolher seus aplicativos','A loja reúne aplicativos Linux, programas Windows e sites com perfis separados. Instale apenas o que você precisa.',
     'Abrir Loja Linux BR',['linuxbr-store']),
]


def preferences_path():
    return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'linuxbr/setup.json'


def load_progress():
    try:
        data=json.loads(preferences_path().read_text(encoding='utf-8'))
        return {key:value is True for key,value in data.get('done',{}).items()}
    except (OSError,ValueError,AttributeError):return {}


def save_progress(done):
    path=preferences_path();path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary=tempfile.mkstemp(prefix='.setup-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump({'version':1,'done':done},stream,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


class SetupWizard(QWizard):
    def __init__(self):
        super().__init__();self.setWindowTitle('Preparar meu computador — Linux BR')
        from desktop_theme import initialize
        initialize()
        self.setWindowIcon(QIcon.fromTheme('tools-wizard'));self.setStyleSheet(BUTTONS)
        self.resize(730,480);self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setButtonText(QWizard.WizardButton.BackButton,'Voltar')
        self.setButtonText(QWizard.WizardButton.NextButton,'Continuar')
        self.setButtonText(QWizard.WizardButton.FinishButton,'Concluir')
        self.setButtonText(QWizard.WizardButton.CancelButton,'Fechar')
        self.checks={};self.observations={};self.queries=set();done=load_progress()
        for index,(key,title,description,caption,command) in enumerate(STEPS):
            page=QWizardPage();page.setTitle(title)
            page.setSubTitle(f'Etapa {index+1} de {len(STEPS)} · Você pode fechar e retomar quando quiser.')
            body=QVBoxLayout(page);body.setSpacing(18)
            if key == 'accounts':
                organization = QPushButton(QIcon.fromTheme('network-server'), 'Preparar para trabalho ou escola…')
                organization.clicked.connect(lambda: launch(self, ['/usr/bin/python3',
                    str(Path(__file__).with_name('organization_preparation.py'))]))
                body.addWidget(organization)
            text=QLabel(description);text.setWordWrap(True);body.addWidget(text)
            if key=='region':
                field=QLineEdit();field.setPlaceholderText('Experimente: ação, açúcar, R$ 1.234,56, / e ?')
                field.setAccessibleName('Experimentar acentos e teclas do teclado');body.addWidget(field)
            observed=QLabel('Estado atual ainda não consultado. A verificação não altera configurações.')
            observed.setWordWrap(True);observed.setTextFormat(Qt.TextFormat.PlainText)
            observed.setAccessibleName('Estado atual: '+title);body.addWidget(observed)
            self.observations[key]=observed
            verify=QPushButton(QIcon.fromTheme('view-refresh'),'Conferir estado atual')
            verify.clicked.connect(lambda checked=False,k=key,b=verify:self.observe(k,b))
            body.addWidget(verify,0,Qt.AlignmentFlag.AlignLeft)
            button=QPushButton(caption)
            button.setIcon(QIcon.fromTheme({'accounts':'system-users','migration':'folder-download','network':'network-wireless',
                'region':'preferences-desktop-locale','display':'video-display','devices':'preferences-devices-tree',
                'daily':'applications-utilities','backup':'document-save','updates':'system-software-update',
                'apps':'system-software-install'}[key]))
            button.clicked.connect(lambda checked=False,argv=command:launch(self,argv))
            body.addWidget(button,0,Qt.AlignmentFlag.AlignLeft)
            check=QCheckBox('Já conferi esta etapa');check.setChecked(done.get(key,False))
            self.checks[key]=check;body.addWidget(check)
            note=QLabel('Esta marcação é sua organização pessoal. Abrir uma ferramenta não confirma automaticamente que tudo está funcionando.')
            note.setWordWrap(True);body.addWidget(note);body.addStretch();self.addPage(page)
        self.finished.connect(self.save)

    def observe(self,key,button):
        from desktop_jobs import Query
        from initial_status import observe
        button.setEnabled(False);self.observations[key].setText('Consultando o estado atual…')
        task=Query(lambda:observe(key),QApplication.instance());self.queries.add(task)
        def loaded(value):
            self.observations[key].setText(value['text']);button.setEnabled(True)
        task.result.connect(loaded)
        task.failed.connect(lambda _:loaded({'text':'Não foi possível consultar o estado. Abra a ferramenta para conferir este item.'}))
        task.finished.connect(lambda:self.queries.discard(task));task.finished.connect(task.deleteLater);task.start()

    def save(self,*_):
        try:save_progress({key:check.isChecked() for key,check in self.checks.items()})
        except OSError:
            QMessageBox.warning(self,'Etapas não salvas','Não foi possível salvar as marcações nesta conta. Você pode rever a configuração inicial pelo menu.')


if __name__=='__main__':
    app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-setup')
    wizard=SetupWizard();wizard.show();sys.exit(app.exec())
