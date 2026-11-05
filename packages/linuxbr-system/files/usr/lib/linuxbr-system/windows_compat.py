"""Library, installation and recovery tools for user-owned Windows programs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from PyQt6.QtCore import QProcess, QTimer, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from visual_style import BUTTONS
from windows_runner import (create_environment, data_root, default_environment,
    environment_path, environments, forget_program, inspect_windows_file,
    programs, read_environment, read_program, register_program, rename_environment,
    set_default_environment, start_job, diagnose_program, program_icon)

BUTTON_ICONS={
    'Novo…':'folder-new','Renomear…':'edit-rename','Usar como padrão':'emblem-favorite',
    'Abrir programa':'media-playback-start','Localizar instalados':'edit-find','Adicionar EXE…':'list-add',
    'Abrir local do arquivo':'folder-open','Remover atalho':'edit-delete',
    'Desinstalar programas…':'edit-delete','Atualizar lista':'view-refresh',
    'Abrir / instalar':'system-run','Editar BAT / CMD':'document-edit',
    'Abrir pasta Downloads':'folder-downloads','Procurar na Loja':'system-software-install',
    'Configurar Wine':'configure','Dependências…':'package-x-generic','Unidade C:':'drive-harddisk',
    'Encerrar programas travados…':'process-stop','Copiar registro':'edit-copy',
    'Abrir pasta de registros':'folder-documents','Diagnóstico da última execução':'dialog-information',
    'Abrir Steam':'steam','Modo para TV e controle':'input-gaming','Instalar / abrir Bottles':'wine',
    'Bluetooth':'preferences-system-bluetooth','Áudio':'audio-volume-high','Telas':'video-display',
    'Informações Vulkan':'hwinfo','Dispositivos e drivers':'preferences-desktop-peripherals',
    'Copiar diagnóstico':'edit-copy','Fechar':'window-close',
}


class WindowsCompatibility(QWidget):
    def __init__(self, filename=None):
        super().__init__()
        self.job=None;self.scan_process=None;self.bottles_process=None
        self.job_context=None;self.monitor_only=False;self.last_job_result=None
        self.job_action=None
        self.setStyleSheet(BUTTONS)
        self.setWindowTitle('Linux BR — Programas Windows e jogos')
        self.setWindowIcon(QIcon.fromTheme('applications-games'))
        self.resize(1060,660)
        self.setAcceptDrops(True)
        body=QVBoxLayout(self);body.setContentsMargins(24,18,24,18);body.setSpacing(10)
        title=QLabel('Programas Windows e jogos')
        title.setStyleSheet('font-size:25px;font-weight:600');body.addWidget(title)
        self.note(body,'Seus programas, instaladores e jogos, organizados por ambiente.')
        row=QHBoxLayout();row.addWidget(QLabel('Ambiente:'))
        self.environments=QComboBox();self.environments.setMinimumWidth(220)
        row.addWidget(self.environments,1)
        self.button(row,'Novo…',self.new_environment)
        self.button(row,'Renomear…',self.rename_environment)
        self.default_button=self.button(row,'Usar como padrão',self.make_default)
        body.addLayout(row)
        self.environment_note=QLabel();self.environment_note.setWordWrap(True)
        body.addWidget(self.environment_note)
        self.tabs=QTabWidget();body.addWidget(self.tabs,1)
        self.library_page();self.installer_page();self.games_page();self.help_page();self.recipes_page()
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.file.textChanged.connect(self.review)
        self.environments.currentIndexChanged.connect(self.environment_changed)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(1000)
        self.refresh_environments()
        self.status.setText('Pronto para abrir programas.' if shutil.which('wine') else
                            'Wine não está instalado nesta sessão. Use a imagem Linux BR com suporte Windows.')
        if filename:self.file.setText(filename);self.tabs.setCurrentIndex(1)
        self.review()
        QShortcut(QKeySequence('Ctrl+O'),self,activated=self.choose_installer)
        QShortcut(QKeySequence('Ctrl+F'),self,activated=self.focus_search)
        QShortcut(QKeySequence('F5'),self,activated=self.refresh_programs)

    @staticmethod
    def note(layout,title,text=None):
        label=QLabel(title if text is None else '<b>'+title+'</b><br>'+text)
        label.setWordWrap(True);layout.addWidget(label);return label

    @staticmethod
    def button(layout,label,callback,icon=None):
        button=QPushButton(label);button.clicked.connect(callback);layout.addWidget(button)
        icon=icon or BUTTON_ICONS.get(label)
        if icon:button.setIcon(QIcon.fromTheme(icon))
        return button

    def page(self,label,scroll=False):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(16,16,16,16)
        layout.setSpacing(12)
        if scroll:
            area=QScrollArea();area.setWidgetResizable(True);area.setWidget(page)
            self.tabs.addTab(area,label)
        else:self.tabs.addTab(page,label)
        return layout

    def library_page(self):
        page=self.page('Meus programas')
        self.search=QLineEdit();self.search.setPlaceholderText('Pesquisar programas deste ambiente')
        self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.filter_programs)
        page.addWidget(self.search)
        self.library=QTreeWidget();self.library.setHeaderLabels(['Programa','Situação','Arquivo'])
        self.library.setRootIsDecorated(False);self.library.setAlternatingRowColors(True)
        self.library.setColumnWidth(0,220);self.library.setColumnWidth(1,145)
        self.library.itemActivated.connect(lambda *_:self.launch_selected())
        self.library.itemSelectionChanged.connect(self.selection_changed)
        self.library.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library.customContextMenuRequested.connect(self.program_menu)
        page.addWidget(self.library,1)
        self.empty=QLabel('Instale um programa e use Localizar instalados para adicioná-lo. '
                          'Você também pode adicionar um EXE portátil.');self.empty.setWordWrap(True)
        page.addWidget(self.empty)
        row=QHBoxLayout()
        self.run_program=self.button(row,'Abrir programa',self.launch_selected)
        self.run_program.setProperty('primary',True)
        self.scan_button=self.button(row,'Localizar instalados',self.scan_programs)
        self.button(row,'Adicionar EXE…',self.add_program)
        self.rename_program_button=self.button(row,'Renomear…',self.rename_program)
        page.addLayout(row)
        row=QHBoxLayout()
        self.folder_button=self.button(row,'Abrir local do arquivo',self.program_folder)
        self.forget_button=self.button(row,'Remover atalho',self.forget_selected)
        self.button(row,'Desinstalar programas…',self.uninstall_programs)
        self.button(row,'Atualizar lista',self.refresh_programs);page.addLayout(row)
        row=QHBoxLayout()
        self.diagnose_button=self.button(row,'Diagnóstico do programa',self.diagnose_selected)
        self.diagnose_button.setIcon(QIcon.fromTheme('dialog-information'))
        self.icon_button=self.button(row,'Atualizar ícone do EXE',self.refresh_program_icon)
        self.icon_button.setIcon(QIcon.fromTheme('preferences-desktop-icons'))
        page.addLayout(row)
        self.note(page,'Os atalhos desta lista também aparecem no menu Iniciar. '
                       'Remover um atalho mantém o programa e seus documentos.')

    def installer_page(self):
        page=self.page('Instalar / configurar',True)
        self.note(page,'Abrir programa ou script','Abra EXE, MSI, BAT ou CMD de uma fonte conhecida. Escolha o ambiente e confirme a abertura. '
                       'Programas de 32 bits também podem usar um ambiente de 64 bits.')
        row=QHBoxLayout();self.file=QLineEdit()
        self.file.setPlaceholderText('Selecione EXE, MSI, BAT ou CMD')
        row.addWidget(self.file,1);self.button(row,'Selecionar arquivo…',self.choose);page.addLayout(row)
        self.detail=QLabel();self.detail.setWordWrap(True);page.addWidget(self.detail)
        row=QHBoxLayout()
        self.open_button=self.button(row,'Abrir / instalar',self.guided_install)
        self.open_button.setProperty('primary',True)
        self.button(row,'Editar BAT / CMD',self.edit_script)
        self.button(row,'Abrir pasta Downloads',self.open_downloads)
        self.button(row,'Procurar na Loja',lambda:self.launch(['linuxbr-store']))
        page.addLayout(row)
        self.note(page,'Ajustes deste ambiente','Alterações de versão do Windows, bibliotecas e unidades '
                       'afetam apenas o ambiente selecionado. Prefira um ambiente separado para programas com exigências diferentes.')
        row=QHBoxLayout()
        self.button(row,'Configurar Wine',lambda:self.start('configure'))
        self.button(row,'Dependências…',self.dependencies)
        self.button(row,'Unidade C:',self.open_folder)
        self.button(row,'Encerrar programas travados…',self.stop_environment)
        page.addLayout(row)
        self.button(page,'Receitas, matriz de compatibilidade e reparação…',lambda:self.tabs.setCurrentIndex(4),'preferences-system-windows')
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(200)
        self.log.setMinimumHeight(140)
        self.log.setPlaceholderText('O andamento aparece aqui. A primeira abertura prepara o ambiente e pode levar alguns minutos.')
        page.addWidget(self.log,1)
        row=QHBoxLayout();self.button(row,'Copiar registro',lambda:QApplication.clipboard().setText(self.log.toPlainText()))
        self.button(row,'Abrir pasta de registros',self.open_logs);page.addLayout(row)
        self.button(page,'Diagnóstico da última execução',self.diagnose_last_job)
        self.note(page,'Wine executa programas com os acessos da sua conta. Use arquivos de origem confiável. '
                       'Fechar esta janela não encerra os aplicativos Windows.')

    def games_page(self):
        page=self.page('Jogos e controles',True)
        self.note(page,'Steam + Proton','Na primeira abertura, a Steam baixa seu cliente e solicita sua conta. '
                       'Na biblioteca, abra Propriedades do jogo → Compatibilidade para escolher Proton. '
                       'A Steam gerencia o download dos jogos e das versões do Proton.')
        row=QHBoxLayout();self.button(row,'Abrir Steam',lambda:self.launch(['steam']))
        self.button(row,'Modo para TV e controle',lambda:self.launch(['steam','-bigpicture']))
        page.addLayout(row)
        self.steam_games=QTreeWidget();self.steam_games.setHeaderLabels(['Biblioteca local da Steam','Situação'])
        self.steam_games.setRootIsDecorated(False);self.steam_games.setMinimumHeight(145);self.steam_games.setMaximumHeight(210)
        page.addWidget(self.steam_games)
        row=QHBoxLayout();self.button(row,'Atualizar jogos instalados',self.refresh_steam_games,'view-refresh')
        self.button(row,'Abrir detalhes na Steam',self.steam_details,'steam')
        self.button(row,'Pasta de compatibilidade do jogo',self.steam_prefix,'folder-open');page.addLayout(row)
        self.note(page,'A lista lê os registros locais da Steam. Não altera Proton, opções de inicialização, '
            'saves ou ambientes. Jogos sem avaliação aparecem como Não testado nesta versão.')
        self.refresh_steam_games()
        self.note(page,'Bottles para outras lojas e jogos','Organize cada aplicativo em um ambiente próprio, '
                       'com suas versões do Wine, bibliotecas e ajustes gráficos. Os ambientes do Bottles '
                       'são separados dos ambientes exibidos acima.')
        self.bottles_button=self.button(page,'Instalar / abrir Bottles',self.bottles)
        self.note(page,'Controles, áudio e tela cheia','A Steam oferece mapeamento pelo Steam Input nas configurações '
                       'de controle de cada jogo. Emparelhe controles Bluetooth nas configurações do Linux BR. '
                       'Use Alt+Tab para trocar de janela e a tecla Windows para abrir o menu.')
        row=QHBoxLayout();self.button(row,'Bluetooth',lambda:self.launch(['systemsettings','kcm_bluetooth']))
        self.button(row,'Áudio',lambda:self.launch(['systemsettings','kcm_pulseaudio']))
        self.button(row,'Telas',lambda:self.launch(['systemsettings','kcm_kscreen']));page.addLayout(row)
        self.note(page,'Desempenho gráfico','A imagem inclui bibliotecas gráficas de 32 e 64 bits. Jogos 3D dependem '
                       'da GPU e de um driver compatível com Vulkan. Para NVIDIA, use o driver recomendado com '
                       'bibliotecas de 32 bits. O desempenho em uma máquina virtual não representa o de um PC com GPU.')
        row=QHBoxLayout()
        self.button(row,'Informações Vulkan',lambda:self.launch(['konsole','--hold','-e','vulkaninfo','--summary']))
        self.button(row,'Dispositivos e drivers',lambda:self.launch(['linuxbr-system','--page','Dispositivos']))
        page.addLayout(row);page.addStretch()

    def refresh_steam_games(self):
        from windows_games import installed_games
        self.steam_games.clear()
        for item in installed_games():
            row=QTreeWidgetItem([item['name'],item['status']]);row.setData(0,Qt.ItemDataRole.UserRole,item)
            row.setToolTip(0,item['library']);self.steam_games.addTopLevelItem(row)
        if not self.steam_games.topLevelItemCount():
            self.steam_games.addTopLevelItem(QTreeWidgetItem(['Nenhum jogo encontrado nas bibliotecas locais.','']))

    def steam_details(self):
        from windows_games import details_uri
        row=self.steam_games.currentItem();item=row.data(0,Qt.ItemDataRole.UserRole) if row else None
        if not item:self.problem('Selecione um jogo instalado na lista.');return
        uri=details_uri(item['id'])
        if shutil.which('steam'):self.launch(['steam',uri])
        elif shutil.which('flatpak'):self.launch(['flatpak','run','com.valvesoftware.Steam',uri])
        else:self.problem('O cliente Steam não está disponível nesta sessão.')

    def steam_prefix(self):
        row=self.steam_games.currentItem();item=row.data(0,Qt.ItemDataRole.UserRole) if row else None
        if not item:self.problem('Selecione um jogo instalado na lista.');return
        path=Path(item['prefix'])
        if path.is_dir():self.open_path(path)
        else:self.problem('Este jogo não possui ambiente Proton local. Pode usar uma edição Linux ou ainda não ter sido iniciado.')

    def help_page(self):
        page=self.page('Ajuda de compatibilidade',True)
        for title,text in [
            ('Qual versão escolher?','Prefira a edição Linux quando existir. Para programas Windows, escolha x64 '
             'em PCs de 64 bits ou x86 para programas antigos. Instaladores ARM, drivers Windows e aplicativos '
             'exclusivos da Microsoft Store não são instalados por esta ferramenta.'),
            ('O programa instalou, mas não aparece','Em Meus programas, use Localizar instalados. Selecione o EXE '
             'principal, e não o atualizador ou desinstalador. Para programas portáteis, mantenha a pasta em um '
             'local definitivo antes de adicionar o atalho. Não mova apenas o EXE, pois ele pode precisar de arquivos ao lado.'),
            ('O programa pede Visual C++, .NET ou uma DLL','Use Dependências no ambiente correto ou o gerenciador '
             'de dependências do Bottles. Instale somente o componente exigido pelo fornecedor. Evite baixar DLLs avulsas '
             'de sites desconhecidos. Algumas versões do .NET e recursos do programa podem continuar incompatíveis.'),
            ('Tela preta, jogo travado ou desempenho baixo','Confira o driver e a versão do Proton escolhida na Steam. '
             'Experimente as opções de janela ou tela cheia do próprio jogo. Para recuperar um aplicativo Wine '
             'travado, use Encerrar programas travados no ambiente correspondente.'),
            ('Jogos com antitrapaça','O suporte depende de cada jogo e de sua editora. Easy Anti-Cheat e BattlEye '
             'precisam de suporte habilitado pelo desenvolvedor. Antitrapaças que exigem componentes no kernel do '
             'Windows não têm compatibilidade garantida. Nenhuma opção desta ferramenta remove essas exigências.'),
            ('Arquivos, atualizações e cópias de segurança','Documentos salvos em pastas pessoais continuam na sua '
             'conta Linux. Arquivos salvos na unidade C: ficam dentro do ambiente. Feche os programas antes de '
             'copiar a pasta do ambiente. Atualize cada aplicativo pelo próprio fornecedor; a Loja não administra '
             'os atualizadores internos dos programas Windows.'),
            ('Quando é necessário usar Windows?','Drivers de periféricos, sistemas corporativos, recursos profissionais '
             'específicos, DRM e serviços bancários podem depender do Windows. Consulte o fornecedor sobre uma edição '
             'Linux ou web. Instalar e abrir um programa não comprova que todas as funções funcionam.')]:
            self.note(page,title,text)
        row=QHBoxLayout()
        self.button(row,'Wine AppDB',lambda:self.open_web('https://appdb.winehq.org/'),'internet-web-browser')
        self.button(row,'Documentação Proton',lambda:self.open_web('https://partner.steamgames.com/doc/steamhardware/proton'),'help-contents')
        self.button(row,'Ajuda Bottles',lambda:self.open_web('https://usebottles.com/docs/'),'help-browser')
        page.addLayout(row);page.addStretch()

    @staticmethod
    def card(layout,title):
        group=QGroupBox(title);group.setStyleSheet('QGroupBox { border: 1px solid palette(mid); border-radius: 8px; margin-top: 8px; padding: 8px; } '
            'QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; font-weight: 600; }')
        body=QVBoxLayout(group);body.setSpacing(10);layout.addWidget(group);return body

    def recipes_page(self):
        from windows_recipes import catalog,STATUS
        from compatibility_records import assessment
        page=self.page('Receitas e compatibilidade',True)
        self.note(page,'Receitas por aplicativo e versão','Cada receita informa o que foi verificado e seus limites. '
            'Testes anteriores não comprovam outras versões nem desempenho em hardware físico.')
        information=self.card(page,'Aplicativo e compatibilidade')
        self.recipe_choices=QComboBox();self.recipe_choices.setAccessibleName('Receita de compatibilidade')
        try:
            values=catalog()
            for item in values['recipes']:self.recipe_choices.addItem(item['name']+' · '+assessment(item)['label'],item)
        except (OSError,ValueError,KeyError) as error:values={'games':[]};self.recipe_choices.addItem('Catálogo indisponível: '+str(error),None)
        information.addWidget(self.recipe_choices)
        self.recipe_detail=QLabel();self.recipe_detail.setWordWrap(True);self.recipe_detail.setTextFormat(Qt.TextFormat.PlainText)
        information.addWidget(self.recipe_detail)
        self.recipe_choices.currentIndexChanged.connect(self.review_recipe)
        settings=self.card(page,'Configuração do ambiente')
        self.recipe_settings=QLabel();self.recipe_settings.setWordWrap(True);self.recipe_settings.setTextFormat(Qt.TextFormat.PlainText);settings.addWidget(self.recipe_settings)
        row=QHBoxLayout()
        self.button(row,'Criar ambiente com esta receita…',lambda:self.apply_recipe(True),'folder-new')
        self.button(row,'Aplicar no ambiente selecionado…',lambda:self.apply_recipe(False),'dialog-ok-apply');settings.addLayout(row)
        dependencies=self.card(page,'Dependências e origem')
        self.recipe_dependencies=QLabel();self.recipe_dependencies.setWordWrap(True);self.recipe_dependencies.setTextFormat(Qt.TextFormat.PlainText);dependencies.addWidget(self.recipe_dependencies)
        row=QHBoxLayout()
        self.button(row,'Fonte oficial da receita',self.recipe_source,'internet-web-browser')
        self.button(row,'Instalar dependência indicada…',self.recipe_dependency,'package-x-generic');dependencies.addLayout(row)
        recovery=self.card(page,'Cópias e reparação')
        self.note(recovery,'Cópia antes de alterar','Feche os programas do ambiente. A receita e a reparação criam uma cópia '
            'antes de alterar a configuração; links para documentos pessoais são preservados como links. '
            'A cópia não inclui arquivos fora do ambiente. Outros ambientes, Steam e Bottles não são alterados.')
        row=QHBoxLayout();self.button(row,'Abrir cópias de ambientes',self.open_environment_backups,'folder-documents')
        self.button(row,'Reparar ambiente selecionado…',self.repair_environment,'tools-wizard');recovery.addLayout(row)
        games=self.card(page,'Jogos e Proton')
        for item in values['games']:
            self.note(games,item['name']+' — '+STATUS[item['status']],item['evidence']+' '+item['limits'])
        self.button(games,'Documentação Steam / Proton',lambda:self.open_web('https://partner.steamgames.com/doc/steamhardware/proton'),'help-contents')
        self.review_recipe();page.addStretch()

    def review_recipe(self):
        item=self.recipe_choices.currentData()
        if not item:
            self.recipe_detail.setText('Não há uma receita disponível.');self.recipe_settings.clear();self.recipe_dependencies.clear();return
        dependencies='; '.join(value['name'] for value in item['dependencies']) or 'Nenhuma dependência adicional indicada.'
        from compatibility_records import details
        self.recipe_detail.setText('Versão do aplicativo: '+item['application_version']+'\n\n'+details(item)+'\n\n'
            +item['evidence']+'\n\nLimites: '+item['limits']+'\n\nAlternativa: '+item['alternative']+
            '\n\nOrigem: '+item['source'])
        self.recipe_settings.setText(item['architecture']+' · '+item['windows_version']+' · '+str(item['dpi'])+' DPI\n'
            'Os ajustes são compartilhados por todos os programas do ambiente selecionado.')
        self.recipe_dependencies.setText(dependencies+'\nA instalação de componentes exige uma ação e uma confirmação próprias.')

    def recipe_source(self):
        item=self.recipe_choices.currentData()
        if item:self.open_web(item['source'])

    def begin_maintenance(self,action,recipe_id=None,filename=None):
        from windows_recipes import start_maintenance
        if self.job:self.problem('Aguarde a operação em andamento antes de iniciar manutenção.');return
        identifier=self.environments.currentData()
        try:
            self.job=start_maintenance(identifier,action,recipe_id,filename)
            self.job_context=(identifier,filename);self.job_action=action;self.last_job_result=None
            self.log.clear();self.status.setText('Criando cópia e preparando a operação somente neste ambiente.');self.tabs.setCurrentIndex(1)
        except (OSError,ValueError) as error:self.problem(str(error))

    def apply_recipe(self,new):
        item=self.recipe_choices.currentData()
        if not item:return
        text=('Criar um ambiente separado para '+item['name']+'?' if new else
            'Aplicar a receita em “'+self.environments.currentText()+'”? Todos os programas deste ambiente compartilharão os ajustes.')
        text+='\n\nSerá feita uma cópia antes de ajustar versão do Windows e escala. Nenhuma dependência será baixada ou instalada nesta etapa.'
        if QMessageBox.question(self,'Aplicar receita',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:
            if new:self.refresh_environments(create_environment(item['name'],item['architecture']))
            self.begin_maintenance('apply',item['id'])
        except (OSError,ValueError) as error:self.problem(str(error))

    def recipe_dependency(self):
        item=self.recipe_choices.currentData()
        if not item:return
        values=item['dependencies']
        if not values:self.problem('Esta receita não indica dependências adicionais.');return
        name,ok=QInputDialog.getItem(self,'Dependência','Componente exigido pelo fornecedor:',[value['name'] for value in values],0,False)
        if not ok:return
        dependency=next(value for value in values if value['name']==name)
        text=(dependency['name']+'\n\n'+dependency['note']+'\n\nFonte oficial: '+dependency['source']+
            '\n\nA instalação altera todos os programas do ambiente selecionado. Será feita uma cópia antes. '
            'O arquivo escolhido não tem origem ou assinatura verificada automaticamente. Continuar com um instalador já obtido desta fonte?')
        if QMessageBox.question(self,'Instalar dependência no ambiente selecionado',text,
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        filename,_=QFileDialog.getOpenFileName(self,'Selecionar '+dependency['filename'],'','Instaladores Windows (*.exe *.msi)')
        if filename:self.begin_maintenance('dependency',item['id'],filename)

    def repair_environment(self):
        text='Reparar o ambiente “'+self.environments.currentText()+'” com a atualização nativa do Wine?\n\n'
        text+='Feche os programas deste ambiente. Será feita uma cópia antes. O reparo preserva os arquivos, '
        text+='mas pode alterar registros e componentes compartilhados por todos os programas deste ambiente. '
        text+='Não reinstala programas nem recupera documentos apagados.'
        if QMessageBox.question(self,'Reparar ambiente',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.begin_maintenance('repair')

    def open_environment_backups(self):
        path=data_root()/'backups'
        if path.is_dir():self.open_path(path)
        else:self.problem('Ainda não há cópias de ambientes nesta conta.')

    def refresh_environments(self,selected=None):
        values=environments()
        if not values:
            selected=create_environment('Meus programas Windows');set_default_environment(selected)
            values=environments()
        selected=selected or default_environment() or self.environments.currentData()
        self.environments.blockSignals(True);self.environments.clear()
        for identifier,name in values:self.environments.addItem(name,identifier)
        index=self.environments.findData(selected)
        self.environments.setCurrentIndex(max(0,index));self.environments.blockSignals(False)
        self.environment_changed()

    def environment_changed(self):
        identifier=self.environments.currentData()
        if not identifier:return
        try:
            item=read_environment(identifier);default=default_environment()==identifier
            text='64 bits — aceita EXE x86 e x64' if item['architecture']=='win64' else '32 bits — programas x86 antigos'
            self.environment_note.setText(text+('  •  Ambiente padrão para novos instaladores' if default else ''))
            self.default_button.setEnabled(not default)
            self.refresh_programs();self.review()
        except (OSError,ValueError) as error:self.problem(str(error))

    def new_environment(self):
        name,ok=QInputDialog.getText(self,'Novo ambiente','Nome do programa ou ambiente:')
        if not ok:return
        kind,ok=QInputDialog.getItem(self,'Arquitetura','Tipo de ambiente:',
            ['64 bits (padrão; aceita programas de 32 e 64 bits)','32 bits (programas antigos)'],0,False)
        if not ok:return
        try:self.refresh_environments(create_environment(name,'win32' if kind.startswith('32') else 'win64'))
        except (OSError,ValueError) as error:self.problem(str(error))

    def rename_environment(self):
        identifier=self.environments.currentData()
        name,ok=QInputDialog.getText(self,'Renomear ambiente','Nome:',text=self.environments.currentText())
        if not ok:return
        try:rename_environment(identifier,name);self.refresh_environments(identifier)
        except (OSError,ValueError) as error:self.problem(str(error))

    def make_default(self):
        try:set_default_environment(self.environments.currentData());self.environment_changed()
        except (OSError,ValueError) as error:self.problem(str(error))

    def choose(self):
        path,_=QFileDialog.getOpenFileName(self,'Abrir programa Windows','',
            'Programas e scripts Windows (*.exe *.EXE *.msi *.MSI *.bat *.BAT *.cmd *.CMD)')
        if path:self.file.setText(path)

    def choose_installer(self):
        self.tabs.setCurrentIndex(1);self.choose()

    def focus_search(self):
        self.tabs.setCurrentIndex(0);self.search.setFocus();self.search.selectAll()

    def dragEnterEvent(self,event):
        urls=event.mimeData().urls()
        if len(urls)==1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in ('.exe','.msi','.bat','.cmd'):
            event.acceptProposedAction()

    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if len(urls)==1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in ('.exe','.msi','.bat','.cmd'):
            self.file.setText(urls[0].toLocalFile());self.tabs.setCurrentIndex(1)
            event.acceptProposedAction()

    def review(self):
        self.open_button.setEnabled(False)
        if not self.file.text().strip():
            self.detail.setText('EXE, MSI, BAT e CMD são abertos com Wine, sem acesso administrativo.');return
        try:
            path,kind=inspect_windows_file(self.file.text());identifier=self.environments.currentData()
            if not identifier:return
            self.detail.setText(f'{path.name} — {kind}. Clique em Abrir / instalar para executar.')
            self.open_button.setEnabled(bool(shutil.which('wine')))
        except (OSError,ValueError) as error:self.detail.setText(str(error))

    def edit_script(self):
        try:
            path,kind=inspect_windows_file(self.file.text())
            if kind not in ('BAT','CMD'):raise ValueError('Selecione um BAT ou CMD para editar.')
            self.launch(['kate','--',str(path)])
        except (OSError,ValueError) as error:self.problem(str(error))

    def guided_install(self):
        try:path,kind=inspect_windows_file(self.file.text())
        except (OSError,ValueError) as error:self.problem(str(error));return
        script=kind in ('BAT','CMD')
        dialog=QDialog(self);dialog.setWindowTitle('Executar script Windows' if script else 'Instalar programa Windows');dialog.resize(540,320)
        layout=QVBoxLayout(dialog)
        label=QLabel(path.name+' — '+kind);label.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(label)
        self.note(layout,'Escolha onde instalar. Um ambiente separado mantém ajustes e bibliotecas deste programa separados dos demais. Os programas continuam tendo os acessos da sua conta.')
        if script:self.note(layout,'Este script pode alterar ou apagar arquivos acessíveis à sua conta. Revise o conteúdo em Editar BAT / CMD antes de executar. Comandos exclusivos do Windows podem não funcionar. A unidade C: deste ambiente pertence ao Wine.')
        target=QComboBox();target.addItem('Novo ambiente para este programa (recomendado)',None)
        for identifier,name in environments():target.addItem(name,identifier)
        layout.addWidget(target)
        name=QLineEdit(path.stem);name.setMaxLength(80);name.setAccessibleName('Nome do novo ambiente');layout.addWidget(name)
        architecture=QComboBox();architecture.addItem('64 bits — x86 e x64','win64')
        if kind!='x64':architecture.addItem('32 bits — programas antigos','win32')
        layout.addWidget(architecture)
        def update():
            name.setEnabled(target.currentData() is None);architecture.setEnabled(target.currentData() is None)
        target.currentIndexChanged.connect(update)
        error_label=QLabel();error_label.setWordWrap(True);layout.addWidget(error_label)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        confirm=buttons.addButton('Executar script' if script else 'Preparar e abrir instalador',QDialogButtonBox.ButtonRole.AcceptRole)
        if script:
            confirm.setAutoDefault(False)
            confirm.setDefault(False)
            cancel=buttons.button(QDialogButtonBox.StandardButton.Cancel)
            cancel.setDefault(True);cancel.setFocus()
        confirm.setProperty('primary',True);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        def install():
            try:
                identifier=target.currentData()
                if identifier and kind=='x64' and read_environment(identifier)['architecture']=='win32':
                    raise ValueError('Este arquivo exige um ambiente de 64 bits.')
                if identifier is None:identifier=create_environment(name.text(),architecture.currentData())
                self.refresh_environments(identifier);self.start('run',str(path),identifier)
                if self.job:dialog.accept()
            except (OSError,ValueError) as error:error_label.setText(str(error))
        buttons.accepted.connect(install);dialog.exec()

    def start(self,action,filename=None,identifier=None):
        try:
            if not shutil.which('wine'):raise ValueError('Wine não está instalado.')
            filename=(filename or self.file.text()) if action=='run' else None
            identifier=identifier or self.environments.currentData()
            self.job=start_job(identifier,action,filename)
            self.job_context=(identifier,filename);self.last_job_result=None;self.job_action=action
            self.log.clear();self.status.setText('Preparando / executando. Você pode fechar esta janela sem encerrar o programa.')
        except (OSError,ValueError) as error:self.problem(str(error))

    def watch_job(self,job,identifier,filename=None,action='run'):
        if not isinstance(job,str) or str(uuid.UUID(job))!=job:raise ValueError('Registro de execução inválido.')
        if action not in ('run','configure','repair','apply','dependency'):raise ValueError('Tipo de acompanhamento inválido.')
        read_environment(identifier)
        root=data_root()/'jobs'
        if root.is_symlink() or any((root/(job+suffix)).is_symlink() for suffix in ('.json','.log')):
            raise ValueError('O registro não pode ser um link simbólico.')
        if filename:
            path=Path(filename).expanduser()
            if not path.is_absolute() or path.suffix.lower() not in ('.exe','.msi','.bat','.cmd'):
                raise ValueError('O acompanhamento exige o caminho Windows local usado na abertura.')
            filename=str(path.resolve())
        if self.job and self.job!=job:raise ValueError('Esta janela já acompanha outra operação.')
        self.refresh_environments(identifier);self.job=job;self.job_context=(identifier,filename)
        self.job_action=action;self.last_job_result=None;self.tabs.setCurrentIndex(1)
        self.status.setText('Acompanhando uma operação já iniciada. Fechar esta janela não encerra o programa.')

    def poll(self):
        if not self.job:return
        root=data_root()/'jobs'
        try:
            with (root/(self.job+'.log')).open('rb') as stream:
                stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-16000))
                value=stream.read().decode('utf-8',errors='replace')
                if value!=self.log.toPlainText():self.log.setPlainText(value)
        except OSError:pass
        try:result=json.loads((root/(self.job+'.json')).read_text(encoding='utf-8'))
        except (OSError,ValueError):return
        self.status.setText(('Manutenção concluída. A cópia anterior está em Receitas e compatibilidade → Abrir cópias de ambientes.'
            if self.job_action in ('repair','apply','dependency') else 'Execução concluída. Use Localizar instalados para adicionar atalhos.')
            if result.get('code')==0 else 'O programa terminou com erro. '+result.get('error','')+
            ' Consulte o registro em Instalar / configurar e a Ajuda de compatibilidade.')
        self.last_job_result=result;self.job=None;self.refresh_programs()
        if self.monitor_only:
            if result.get('code')==0:QApplication.instance().quit()
            else:
                self.monitor_only=False;QApplication.instance().setQuitOnLastWindowClosed(True)
                self.tabs.setCurrentIndex(1);self.show();self.raise_();self.diagnose_last_job()

    def show_diagnosis(self,identifier,filename=None,result=None):
        try:
            log=self.log.toPlainText() if result is not None else ''
            result=result or {}
            text=diagnose_program(identifier,filename,result.get('code'),result.get('error',''),log)
            dialog=QDialog(self);dialog.setWindowTitle('Diagnóstico de compatibilidade');dialog.resize(740,510)
            body=QVBoxLayout(dialog);view=QPlainTextEdit();view.setReadOnly(True);view.setPlainText(text);body.addWidget(view,1)
            row=QHBoxLayout();self.button(row,'Copiar diagnóstico',lambda:QApplication.clipboard().setText(text))
            self.button(row,'Fechar',dialog.accept);body.addLayout(row);dialog.exec()
        except (OSError,ValueError) as failure:self.problem(str(failure))

    def diagnose_selected(self):
        identifier=self.selected_program()
        if not identifier:return
        try:
            item=read_program(identifier);self.show_diagnosis(item['environment'],item['file'])
        except (OSError,ValueError) as error:self.problem(str(error))

    def diagnose_last_job(self):
        if not self.job_context:self.problem('Abra um programa para obter o diagnóstico desta execução.');return
        self.show_diagnosis(*self.job_context,self.last_job_result or {})

    def refresh_program_icon(self):
        identifier=self.selected_program()
        if not identifier:return
        try:
            item=read_program(identifier);register_program(item['environment'],item['file'],item['name'])
            self.refresh_programs()
            self.status.setText('Ícone do EXE atualizado.' if program_icon(identifier)!='wine' else
                'Não foi encontrado um ícone utilizável. Mantido o símbolo do Wine.')
        except (OSError,ValueError) as error:self.problem(str(error))

    def uninstall_programs(self):
        if QMessageBox.question(self,'Desinstalar programas deste ambiente',
            'Abrir o desinstalador do Wine em “'+self.environments.currentText()+'”? '
            'Escolha e confirme o programa na próxima janela. A remoção pode afetar seus dados neste ambiente.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.start('uninstall')

    def selected_program(self):
        item=self.library.currentItem()
        return item.data(0,Qt.ItemDataRole.UserRole) if item else None

    def refresh_programs(self):
        selected=self.selected_program();self.library.clear()
        for item in programs(self.environments.currentData()):
            exists=Path(item['file']).is_file()
            row=QTreeWidgetItem([item['name'],'Disponível' if exists else 'Arquivo não encontrado',item['file']])
            row.setData(0,Qt.ItemDataRole.UserRole,item['id']);row.setToolTip(2,item['file'])
            icon=program_icon(item['id'])
            row.setIcon(0,QIcon(icon) if icon.startswith('/') else QIcon.fromTheme(icon,QIcon.fromTheme('application-x-ms-dos-executable')))
            self.library.addTopLevelItem(row)
            if item['id']==selected:self.library.setCurrentItem(row)
        self.empty.setVisible(self.library.topLevelItemCount()==0)
        self.filter_programs();self.selection_changed()

    def filter_programs(self):
        text=self.search.text().casefold().strip()
        for index in range(self.library.topLevelItemCount()):
            item=self.library.topLevelItem(index)
            item.setHidden(text not in (item.text(0)+' '+item.text(2)).casefold())

    def selection_changed(self):
        selected=bool(self.selected_program())
        for button in (self.run_program,self.rename_program_button,self.folder_button,self.forget_button,self.diagnose_button,self.icon_button):
            button.setEnabled(selected)

    def program_menu(self,position):
        item=self.library.itemAt(position)
        if item is None:return
        self.library.setCurrentItem(item);menu=QMenu(self)
        menu.addAction('Abrir',self.launch_selected)
        menu.addAction('Abrir local do arquivo',self.program_folder)
        menu.addAction('Diagnóstico do programa',self.diagnose_selected)
        menu.addAction('Atualizar ícone do EXE',self.refresh_program_icon)
        menu.addSeparator();menu.addAction('Renomear atalho…',self.rename_program)
        menu.addAction('Remover atalho',self.forget_selected)
        menu.exec(self.library.viewport().mapToGlobal(position))

    def launch_selected(self):
        identifier=self.selected_program()
        if not identifier:return
        try:
            item=read_program(identifier)
            self.start('run',item['file'],item['environment'])
        except (OSError,ValueError) as error:self.problem(str(error))

    def add_program(self):
        filename,_=QFileDialog.getOpenFileName(self,'Adicionar programa ou EXE portátil','',
                                               'Programas Windows (*.exe *.EXE)')
        if not filename:return
        name,ok=QInputDialog.getText(self,'Nome do atalho','Como o programa aparece no menu:',text=Path(filename).stem)
        if not ok:return
        try:
            register_program(self.environments.currentData(),filename,name);self.refresh_programs()
            self.status.setText('Atalho adicionado à lista e ao menu Iniciar.')
        except (OSError,ValueError) as error:self.problem(str(error))

    def rename_program(self):
        identifier=self.selected_program()
        if not identifier:return
        try:
            item=read_program(identifier)
            name,ok=QInputDialog.getText(self,'Renomear atalho','Nome no menu:',text=item['name'])
            if ok:register_program(item['environment'],item['file'],name);self.refresh_programs()
        except (OSError,ValueError) as error:self.problem(str(error))

    def forget_selected(self):
        identifier=self.selected_program()
        if not identifier:return
        if QMessageBox.question(self,'Remover atalho','Remover este atalho da lista e do menu Iniciar? '
            'O programa e seus arquivos serão mantidos.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:forget_program(identifier);self.refresh_programs()
        except (OSError,ValueError) as error:self.problem(str(error))

    def program_folder(self):
        identifier=self.selected_program()
        if not identifier:return
        try:
            path=Path(read_program(identifier)['file']).parent
            if not path.is_dir():raise ValueError('A pasta foi movida ou removida.')
            self.open_path(path)
        except (OSError,ValueError) as error:self.problem(str(error))

    def scan_programs(self):
        if self.scan_process is not None:return
        identifier=self.environments.currentData();process=QProcess(self);self.scan_process=process
        self.scan_button.setEnabled(False);self.status.setText('Localizando executáveis nas pastas de programas deste ambiente…')
        process.finished.connect(lambda code,_status:self.scan_finished(identifier,process,code))
        process.errorOccurred.connect(lambda _error:self.scan_failed(process))
        process.start('/usr/bin/python3',[str(Path(__file__).with_name('windows_tools.py')),'scan',identifier])

    def scan_failed(self,process):
        if self.scan_process is not process:return
        self.scan_process=None;self.scan_button.setEnabled(True)
        self.status.setText('Não foi possível localizar programas: '+process.errorString())
        process.deleteLater()

    def scan_finished(self,identifier,process,code):
        if self.scan_process is not process:return
        self.scan_process=None;self.scan_button.setEnabled(True)
        try:
            if code:raise ValueError(bytes(process.readAllStandardError()).decode('utf-8',errors='replace'))
            values=json.loads(bytes(process.readAllStandardOutput()).decode('utf-8'))
            saved={item['file'] for item in programs(identifier)}
            values=[item for item in values if item['file'] not in saved]
            if not values:self.status.setText('Nenhum novo EXE encontrado. Use Adicionar EXE para escolher outra pasta.');return
            dialog=QDialog(self)
            dialog.setWindowTitle('Adicionar programas — '+read_environment(identifier)['name'])
            dialog.resize(780,480)
            layout=QVBoxLayout(dialog)
            self.note(layout,'Selecione os programas que deseja adicionar. A lista também pode conter componentes auxiliares. '
                             'Use Ctrl ou Shift para selecionar mais de um.')
            listing=QListWidget();listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            for value in values:
                row=QListWidgetItem(value['name']+' — '+value['kind']+'\n'+value['file'])
                row.setData(Qt.ItemDataRole.UserRole,value);listing.addItem(row)
            layout.addWidget(listing,1)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Adicionar selecionados')
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            listing.itemSelectionChanged.connect(lambda:buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(listing.selectedItems())))
            buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            if dialog.exec()!=QDialog.DialogCode.Accepted:self.status.setText('Nenhum atalho adicionado.');return
            added=0;errors=[]
            for row in listing.selectedItems():
                value=row.data(Qt.ItemDataRole.UserRole)
                try:register_program(identifier,value['file'],value['name']);added+=1
                except (OSError,ValueError) as error:errors.append(value['name']+': '+str(error))
            self.refresh_environments(identifier)
            self.status.setText(f'{added} atalho(s) adicionado(s) ao menu Iniciar.')
            if errors:self.problem('\n'.join(errors))
        except (OSError,ValueError,KeyError,TypeError) as error:self.problem(str(error))
        finally:process.deleteLater()

    def dependencies(self):
        if not shutil.which('winetricks'):
            self.problem('Winetricks não está instalado. Use o gerenciador de dependências do Bottles.');return
        if QMessageBox.question(self,'Dependências do ambiente','O Winetricks permite instalar bibliotecas, fontes e componentes '
            'do Windows neste ambiente. Baixe somente os componentes exigidos pelo aplicativo. Continuar?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.start('dependencies')

    def stop_environment(self):
        name=self.environments.currentText()
        if QMessageBox.warning(self,'Encerrar programas deste ambiente',
            f'Encerrar todos os programas Wine em “{name}”? Trabalho não salvo nesses programas será perdido. '
            'Outros ambientes e jogos da Steam não são encerrados por esta ação.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.start('stop')

    def open_folder(self):
        try:
            path=environment_path(self.environments.currentData())
            drive=path/'prefix/drive_c';self.open_path(drive if drive.is_dir() else path)
        except (OSError,ValueError) as error:self.problem(str(error))

    def open_downloads(self):
        from PyQt6.QtCore import QStandardPaths
        path=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        self.open_path(Path(path) if path and Path(path).is_dir() else Path.home())

    def open_logs(self):
        path=data_root()/'jobs';path.mkdir(parents=True,exist_ok=True,mode=0o700);self.open_path(path)

    def open_path(self,path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):self.problem('Não foi possível abrir a pasta.')

    def open_web(self,url):
        if not QDesktopServices.openUrl(QUrl(url)):self.problem('Não foi possível abrir o navegador.')

    def launch(self,command):
        if not shutil.which(command[0]) or not QProcess.startDetached(command[0],command[1:])[0]:
            self.problem('Não foi possível abrir '+command[0]+'. Confira a instalação.')

    def problem(self,message):QMessageBox.warning(self,'Programas Windows e jogos',message)

    def bottles(self):
        if self.bottles_process is not None:return
        if not shutil.which('flatpak'):self.problem('Flatpak não está instalado.');return
        process=QProcess(self);self.bottles_process=process;self.bottles_button.setEnabled(False)
        process.finished.connect(lambda code,_status:self.bottles_checked(process,code))
        process.errorOccurred.connect(lambda _error:self.bottles_failed(process))
        process.start('flatpak',['info','com.usebottles.bottles'])
        QTimer.singleShot(15000,lambda:process.kill() if self.bottles_process is process and
                          process.state()!=QProcess.ProcessState.NotRunning else None)

    def bottles_failed(self,process):
        if self.bottles_process is not process:return
        self.bottles_process=None;self.bottles_button.setEnabled(True)
        self.problem('Não foi possível consultar o Bottles: '+process.errorString());process.deleteLater()

    def bottles_checked(self,process,code):
        if self.bottles_process is not process:return
        self.bottles_process=None;self.bottles_button.setEnabled(True);process.deleteLater()
        if code==0:self.launch(['flatpak','run','com.usebottles.bottles']);return
        if QMessageBox.question(self,'Instalar Bottles','Instalar Bottles do Flathub para sua conta? '
            'O download inclui componentes adicionais, pode ocupar vários GB e precisa de internet. '
            'O andamento será mostrado em uma janela de terminal.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            self.launch(['konsole','--hold','-e','/usr/bin/python3',str(Path(__file__).with_name('windows_tools.py')),'bottles'])

    def closeEvent(self,event):
        for process in (self.scan_process,self.bottles_process):
            if process is not None:
                process.blockSignals(True);process.kill()
        super().closeEvent(event)


if __name__=='__main__':
    if os.geteuid()==0:raise SystemExit('Abra a ferramenta na sessão do usuário, sem sudo.')
    parser=argparse.ArgumentParser(description='Programas Windows e jogos do Linux BR')
    parser.add_argument('filename',nargs='?');parser.add_argument('--launch',metavar='ATALHO')
    parser.add_argument('--program',metavar='ATALHO',help='Selecionar um programa no ambiente correspondente')
    parser.add_argument('--watch-job',metavar='REGISTRO',help='Acompanhar uma operação já iniciada, sem executar novamente')
    parser.add_argument('--environment',metavar='AMBIENTE',help='Ambiente da operação acompanhada')
    parser.add_argument('--watch-action',choices=['run','configure','repair','apply','dependency'])
    parser.add_argument('--page',choices=['library','install','games','help','recipes'],default='library')
    args=parser.parse_args()
    if args.watch_job and (args.launch or args.program):parser.error('O acompanhamento não pode ser combinado com abertura ou seleção de atalho.')
    if args.watch_job and not args.environment:parser.error('--watch-job exige --environment.')
    if (args.environment or args.watch_action) and not args.watch_job:parser.error('Use --environment e --watch-action com --watch-job.')
    app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-windows')
    if args.launch:
        try:
            item=read_program(args.launch)
            if not shutil.which('wine'):raise ValueError('Wine não está instalado.')
            window=WindowsCompatibility();window.refresh_environments(item['environment'])
            window.monitor_only=True;app.setQuitOnLastWindowClosed(False)
            window.start('run',item['file'],item['environment'])
            if not window.job:raise ValueError('Não foi possível iniciar a execução.')
        except (OSError,ValueError,TypeError) as error:
            QMessageBox.warning(None,'Não foi possível abrir o programa',str(error));raise SystemExit(1)
        raise SystemExit(app.exec())
    try:window=WindowsCompatibility(args.filename)
    except (OSError,ValueError) as error:
        QMessageBox.warning(None,'Programas Windows e jogos',str(error));raise SystemExit(1)
    if args.watch_job:
        try:window.watch_job(args.watch_job,args.environment,args.filename,args.watch_action or ('run' if args.filename else 'configure'))
        except (OSError,ValueError,TypeError) as error:
            QMessageBox.warning(None,'Registro indisponível',str(error));raise SystemExit(1)
    elif not args.filename:window.tabs.setCurrentIndex(['library','install','games','help','recipes'].index(args.page))
    if args.program:
        try:
            item=read_program(args.program);window.refresh_environments(item['environment'])
            for index in range(window.library.topLevelItemCount()):
                row=window.library.topLevelItem(index)
                if row.data(0,Qt.ItemDataRole.UserRole)==args.program:window.library.setCurrentItem(row);break
        except (OSError,ValueError,TypeError) as error:
            QMessageBox.warning(None,'Programa indisponível',str(error));raise SystemExit(1)
    window.show();sys.exit(app.exec())
