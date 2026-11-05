"""User confirmation and management for Chromium app windows."""
import argparse
import json
import sys
from urllib.parse import urlsplit
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication,QDialog,QDialogButtonBox,QVBoxLayout,QLabel,
    QLineEdit,QMainWindow,QWidget,QFrame,QListWidget,QListWidgetItem,QHBoxLayout,QPushButton,QMessageBox,QInputDialog,
    QCheckBox,QComboBox,QFormLayout,QScrollArea,QGridLayout)
import webapps_backend as backend
from visual_style import BUTTONS


def profile_label(item, state, include_app=False):
    name=backend.display_name(item) if include_app else item['session']
    badges=['Em execução' if state.get('running') else 'Fechado']
    if state.get('preferred'):badges.append('Padrão')
    return name+' — '+' · '.join(badges)


class ProfilePreferences(QDialog):
    def __init__(self, identifier, parent=None):
        super().__init__(parent)
        self.identifier=identifier
        item=backend.read_record(identifier);options=backend.profile_options(identifier)
        self.setWindowTitle('Preferências — '+backend.display_name(item));self.resize(630,560)
        self.setStyleSheet(BUTTONS);self.setWindowIcon(QIcon(str(backend.icon_path(item))))
        outer=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);outer.addWidget(scroll)
        content=QWidget();layout=QVBoxLayout(content);scroll.setWidget(content)
        title=QLabel(backend.display_name(item));title.setTextFormat(Qt.TextFormat.PlainText)
        title.setStyleSheet('font-size:22px;font-weight:600');layout.addWidget(title)
        note=QLabel('Downloads e permissões são configurados no Chromium deste perfil. As alterações nas janelas do navegador são aplicadas por ele e não são desfeitas ao cancelar este diálogo.');note.setWordWrap(True);layout.addWidget(note)
        for label,section in [('Pasta e confirmação de &downloads','downloads'),
                              ('Permissões deste &site:\nnotificações, câmera e microfone','site')]:
            button=QPushButton(QIcon.fromTheme('configure'),label)
            button.clicked.connect(lambda checked=False,key=section:self.open_native(key));layout.addWidget(button)
        self.startup=QCheckBox('Abrir este perfil ao &entrar na sessão');self.startup.setChecked(options['session_start']);layout.addWidget(self.startup)
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows);layout.addLayout(form)
        self.links=QComboBox();self.links.addItem('Manter links no próprio perfil','profile')
        self.links.addItem('Links de outros sites no navegador padrão','default-browser')
        self.links.setCurrentIndex(self.links.findData(options['external_links']))
        label=QLabel('&Links externos:');label.setBuddy(self.links);form.addRow(label,self.links)
        explanation=QLabel('A opção de navegador padrão trata cliques simples em links HTTP/HTTPS de outros sites após recarregar a página. Redirecionamentos de login e cliques com teclas modificadoras continuam sob controle do Chromium. Se o navegador padrão apontar para outro aplicativo web, a opção será recusada para evitar retornos entre janelas.');explanation.setWordWrap(True);layout.addWidget(explanation)
        path=QLabel('Diretório deste perfil: '+str(backend.record_path(identifier)/'profile'))
        path.setTextFormat(Qt.TextFormat.PlainText);path.setWordWrap(True);path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse|Qt.TextInteractionFlag.TextSelectableByKeyboard);layout.addWidget(path)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setAccessibleName('Resultado das preferências');layout.addWidget(self.error)
        layout.addStretch()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('&Salvar preferências')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('&Cancelar')
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        self.startup.setFocus()

    def open_native(self, section):
        try:backend.open_profile_settings(self.identifier,section);self.error.setText('Preferências abertas no Chromium deste perfil.')
        except (OSError,ValueError) as exc:self.error.setText(str(exc))

    def save(self):
        try:
            backend.save_profile_options(self.identifier,self.links.currentData(),self.startup.isChecked())
            self.accept()
        except (OSError,ValueError) as exc:self.error.setText(str(exc))


class InstallDialog(QDialog):
    def __init__(self, data=None, parent=None, new_session=False):
        super().__init__(parent)
        self.source_offer={key:data[key] for key in ('signed_source','signed_app') if data and key in data}
        if data and data.get('catalog_subscription'):
            self.source_offer=dict(signed_source=data['catalog_subscription']['source'],signed_app=data['catalog_subscription']['app'])
        self.setStyleSheet(BUTTONS)
        self.setWindowIcon(QIcon.fromTheme('applications-internet'))
        self.setWindowTitle('Instalar aplicativo web — Linux BR');self.resize(570,390)
        outer=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);outer.addWidget(scroll)
        content=QWidget();layout=QVBoxLayout(content);scroll.setWidget(content)
        title=QLabel('Um site, uma janela própria');title.setStyleSheet('font-size:23px;font-weight:600');layout.addWidget(title)
        description=QLabel('O aplicativo aparecerá no menu do Linux BR e usará o Chromium atualizado pelo sistema.');description.setWordWrap(True);layout.addWidget(description)
        layout.addWidget(QLabel('Nome do aplicativo'))
        self.name=QLineEdit();self.name.setMaxLength(70);layout.addWidget(self.name)
        self.name.setAccessibleName('Nome do aplicativo')
        layout.addWidget(QLabel('Endereço inicial HTTPS'))
        self.url=QLineEdit();self.url.setPlaceholderText('https://servico.com/');layout.addWidget(self.url)
        self.url.setAccessibleName('Endereço inicial HTTPS')
        layout.addWidget(QLabel('Nome da sessão / conta'))
        self.session=QLineEdit('Principal');self.session.setMaxLength(70);self.session.setPlaceholderText('Ex.: Pessoal, Trabalho, Loja');layout.addWidget(self.session)
        self.session.setAccessibleName('Nome da sessão ou conta')
        self.new_session = new_session
        self.note=QLabel('Cada sessão guarda seu próprio login neste computador. Você pode abrir contas diferentes ao mesmo tempo. Entre na conta desejada na primeira abertura. O site pode pedir autenticação novamente.');self.note.setWordWrap(True);layout.addWidget(self.note)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        if data:
            item=backend.normalize_offer(data)
            self.name.setText(item['name']);self.url.setText(item['url'])
            self.url.setReadOnly(True)
            if backend.sessions(item['url'], True) or new_session:
                self.new_session=True;self.session.clear()
                self.setWindowTitle('Nova sessão — ' + item['name'])
            if item['availability']=='unknown':
                self.error.setText('Não foi confirmada a existência de uma versão Linux para este site.')
            elif item['availability']=='native':
                self.error.setText('Este serviço já oferece aplicativo Linux. Você também pode usar a versão web.')
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        self.install_button=buttons.addButton('Instalar aplicativo',QDialogButtonBox.ButtonRole.AcceptRole)
        if self.new_session:self.install_button.setText('Criar e abrir perfil')
        self.install_button.setProperty('primary',True)
        buttons.rejected.connect(self.reject);buttons.accepted.connect(self.install);outer.addWidget(buttons)
        self.identifier=None

    def install(self):
        try:
            new_session = self.new_session or bool(backend.sessions(self.url.text(), True))
            self.identifier=backend.install({**self.source_offer,'name':self.name.text(),'url':self.url.text(),
                                            'session':self.session.text(),'new_session':new_session})
        except (ValueError,OSError) as exc:
            self.error.setText(str(exc));return
        self.accept()

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Linux BR — Aplicativos web');self.resize(950,640)
        self.setStyleSheet(BUTTONS)
        self.setWindowIcon(QIcon.fromTheme('applications-internet'))
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        title=QLabel('Aplicativos web');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        info=QLabel('Instale sites como aplicativos com janela própria. No Chromium, use o botão “Aplicativos web Linux BR” para sugestões e preferências.');info.setWordWrap(True);layout.addWidget(info)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar aplicativo, perfil ou endereço');layout.addWidget(self.search)
        self.search.setAccessibleName('Buscar aplicativo, perfil ou endereço')
        QShortcut(QKeySequence.StandardKey.Find,self,activated=self.search.setFocus)
        self.search.textChanged.connect(self.filter_profiles)
        self.summary=QLabel();layout.addWidget(self.summary)
        self.list=QListWidget();layout.addWidget(self.list)
        self.list.setAccessibleName('Aplicativos web e perfis instalados')
        self.list.itemDoubleClicked.connect(lambda _item:self.open_app())
        row=QGridLayout();layout.addLayout(row)
        actions=[('Adicionar site','list-add',self.add),('Abrir perfil','document-open',self.open_app),('Novo perfil','user-group-new',self.new_session),('Renomear','edit-rename',self.rename),('Preferências','configure',self.preferences),('Atualizar lista','view-refresh',self.refresh)]
        for index,(label,icon,action) in enumerate(actions):
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(action);row.addWidget(button,index//3,index%3)
        more=QGridLayout();layout.addLayout(more)
        for index,(label,icon,action) in enumerate([('Remover do menu','list-remove',self.remove),('Restaurar perfil','edit-undo',self.restore),('Usar como padrão','emblem-favorite',self.prefer),('Retirar padrão','edit-clear',self.unprefer),('Apagar dados…','edit-delete',self.delete)]):
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(action);more.addWidget(button,index//3,index%3)
        note=QLabel('Pessoal, Trabalho ou outras contas: cada sessão mantém cookies e login separados e pode abrir junto das demais. O nome é escolhido por você; o Linux BR não lê a conta do site. Remover do menu preserva os dados para restauração.');note.setWordWrap(True);layout.addWidget(note)
        self.refresh()

    def preferences(self):
        index=self.list.currentRow()
        if index<0:return
        try:ProfilePreferences(self.items[index]['id'],self).exec();self.refresh_icons()
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível abrir',str(exc))

    def refresh(self):
        selected=self.items[self.list.currentRow()]['id'] if hasattr(self,'items') and self.list.currentRow()>=0 else None
        self.items=backend.installed();self.list.clear()
        from webapp_icons import request_refresh
        self.list.setIconSize(QSize(32,32))
        for item in self.items:
            backend.prepare_icon(item)
            entry=QListWidgetItem(QIcon(str(backend.icon_path(item))),backend.display_name(item))
            self.list.addItem(entry); request_refresh(item['url'])
        if not hasattr(self,'icon_timer'):
            self.icon_timer=QTimer(self);self.icon_timer.setInterval(2000)
            self.icon_timer.timeout.connect(self.refresh_icons);self.icon_timer.start()
        if self.items:
            self.list.setCurrentRow(next((i for i,item in enumerate(self.items) if item['id']==selected),0))
        self.refresh_icons();self.filter_profiles()

    def prefer(self):
        index=self.list.currentRow()
        if index<0:return
        try:
            backend.set_preferred_profile(self.items[index]['id'])
            self.refresh_icons()
            QMessageBox.information(self,'Perfil padrão','Este perfil ficará selecionado na escolha de contas. Com vários perfis, você ainda poderá escolher um ou mais antes de abrir.')
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível salvar',str(exc))

    def unprefer(self):
        index=self.list.currentRow()
        if index<0:return
        try:backend.clear_preferred_profile(self.items[index]['id']);self.refresh_icons()
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível salvar',str(exc))

    def delete(self):
        choices=backend.installed(True)
        if not choices:return
        labels=[backend.display_name(item)+' — '+urlsplit(item['url']).hostname for item in choices]
        label,ok=QInputDialog.getItem(self,'Apagar dados de um perfil','Escolha o perfil, inclusive os removidos do menu:',labels,0,False)
        if not ok:return
        item=choices[labels.index(label)]
        if QMessageBox.warning(self,'Apagar dados definitivamente',
            'Apagar '+backend.display_name(item)+'? Cookies, contas salvas e dados locais serão excluídos deste computador. Esta ação não pode ser desfeita.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:backend.delete_profile(item['id']);self.refresh()
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível apagar',str(exc))

    def refresh_icons(self):
        states=backend.profile_states(self.items)
        for index,item in enumerate(self.items):
            entry=self.list.item(index)
            if entry:
                entry.setIcon(QIcon(str(backend.icon_path(item))))
                entry.setText(profile_label(item,states.get(item['id'],{}),True)+' — '+urlsplit(item['url']).hostname)
                entry.setToolTip('O estado indica o processo Chromium deste perfil. O Linux BR não lê contas, cookies ou páginas abertas.')
        active=sum(state['running'] for state in states.values())
        self.summary.setText(f'{len(self.items)} perfis · {active} em execução')

    def filter_profiles(self):
        if not hasattr(self,'items'):return
        query=self.search.text().casefold().strip()
        visible=[]
        for index,item in enumerate(self.items):
            match=query in (backend.display_name(item)+' '+item['url']).casefold()
            self.list.item(index).setHidden(not match)
            if match:visible.append(index)
        if self.list.currentRow() not in visible:
            self.list.setCurrentRow(visible[0] if visible else -1)

    def add(self):
        if InstallDialog(parent=self).exec():self.refresh()

    def new_session(self):
        index=self.list.currentRow()
        if index>=0:
            create_profile(self.items[index],self);self.refresh()

    def rename(self):
        index=self.list.currentRow()
        if index<0:return
        item=self.items[index]
        name,ok=QInputDialog.getText(self,'Renomear sessão','Nome da sessão / conta:',text=item['session'])
        if ok:
            try:backend.rename_session(item['id'],name);self.refresh()
            except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível renomear',str(exc))

    def restore(self):
        visible={item['id'] for item in backend.installed()}
        hidden=[item for item in backend.installed(True) if item['id'] not in visible]
        if not hidden:
            QMessageBox.information(self,'Restaurar sessão','Não há sessões removidas do menu.');return
        labels=[backend.display_name(item)+' — '+urlsplit(item['url']).hostname for item in hidden]
        choice,ok=QInputDialog.getItem(self,'Restaurar sessão','Escolha a sessão que deseja recuperar:',labels,0,False)
        if ok:
            try:backend.restore(hidden[labels.index(choice)]['id']);self.refresh()
            except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível restaurar',str(exc))

    def open_app(self):
        index=self.list.currentRow()
        if index<0:return
        try:backend.launch(self.items[index]['id'])
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível abrir',str(exc))

    def remove(self):
        index=self.list.currentRow()
        if index<0:return
        item=self.items[index]
        if QMessageBox.question(self,'Remover sessão',f'Remover {backend.display_name(item)} do menu?\nO login e os dados serão preservados. Use Restaurar sessão para recuperar este perfil.')==QMessageBox.StandardButton.Yes:
            try:backend.remove(item['id']);self.refresh()
            except (OSError,ValueError) as exc:QMessageBox.warning(self,'Não foi possível remover',str(exc))

def create_profile(item, parent=None):
    dialog=InstallDialog(item,parent,new_session=True)
    if dialog.exec():
        backend.launch(dialog.identifier)
        return dialog.identifier

class ProfilePicker(QDialog):
    def __init__(self, choices, parent=None):
        super().__init__(parent)
        self.choices=choices
        self.setWindowIcon(QIcon(str(backend.icon_path(choices[0]))))
        self.setWindowTitle('Escolher perfis — '+choices[0]['name'])
        self.setObjectName('profilePicker')
        self.setWindowFlags(Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setWindowState(self.windowState()|Qt.WindowState.WindowFullScreen)
        self.setStyleSheet(BUTTONS+'QDialog#profilePicker { background: #10191f; } QFrame#profileCard { background: palette(window); border: 1px solid palette(mid); }')
        outer=QVBoxLayout(self);outer.setContentsMargins(24,24,24,24)
        self.card=QFrame();self.card.setObjectName('profileCard');self.card.setMaximumSize(720,620)
        self.card.setMinimumSize(380,400)
        outer.addWidget(self.card,0,Qt.AlignmentFlag.AlignCenter)
        layout=QVBoxLayout(self.card);layout.setContentsMargins(20,20,20,20)
        title=QLabel(choices[0]['name']);title.setTextFormat(Qt.TextFormat.PlainText);title.setStyleSheet('font-size:24px;font-weight:600');layout.addWidget(title)
        layout.addWidget(QLabel('Selecione um ou mais perfis para abrir:'))
        note=QLabel('O perfil padrão fica marcado. Cada perfil mantém suas próprias contas e dados.');note.setWordWrap(True);layout.addWidget(note)
        self.list=QListWidget();layout.addWidget(self.list)
        self.list.setAccessibleName('Perfis disponíveis; use Espaço para marcar um ou mais')
        for entry in choices:
            item=QListWidgetItem(QIcon(str(backend.icon_path(entry))),entry['session'])
            item.setData(Qt.ItemDataRole.UserRole,entry['id'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if entry['id']==backend.preferred_profile(entry['url']) else Qt.CheckState.Unchecked);self.list.addItem(item)
        manage=QGridLayout();layout.addLayout(manage)
        self.rename_button=QPushButton(QIcon.fromTheme('edit-rename'),'Renomear perfil');self.rename_button.clicked.connect(self.rename_profile);manage.addWidget(self.rename_button,0,0)
        self.default_button=QPushButton(QIcon.fromTheme('emblem-favorite'),'Usar como padrão');self.default_button.clicked.connect(self.toggle_default);manage.addWidget(self.default_button,0,1)
        preferences=QPushButton(QIcon.fromTheme('configure'),'Preferências');preferences.clicked.connect(self.preferences);manage.addWidget(preferences,1,0,1,2)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        row=QHBoxLayout();layout.addLayout(row)
        self.new_button=QPushButton('+ Novo perfil');self.new_button.clicked.connect(self.new_profile);row.addWidget(self.new_button)
        cancel=QPushButton('Cancelar');cancel.clicked.connect(self.reject);row.addWidget(cancel)
        self.open_button=QPushButton('Abrir selecionados');self.open_button.setProperty('primary',True)
        self.open_button.setDefault(True)
        self.open_button.clicked.connect(self.open_selected);row.addWidget(self.open_button)
        self.list.itemActivated.connect(lambda _item:self.open_selected() if self.open_button.isEnabled() else None)
        self.list.itemChanged.connect(self.update_selection);self.update_selection()
        self.list.currentRowChanged.connect(self.refresh_status)
        self.list.setCurrentRow(0)
        self.status_timer=QTimer(self);self.status_timer.setInterval(2000)
        self.status_timer.timeout.connect(self.refresh_status);self.status_timer.start()
        self.refresh_status()
        self.list.setFocus()

    def preferences(self):
        index=self.list.currentRow()
        if index<0:return
        try:ProfilePreferences(self.choices[index]['id'],self).exec();self.error.clear()
        except (OSError,ValueError) as exc:self.error.setText(str(exc))

    def refresh_status(self):
        states=backend.profile_states(self.choices)
        for index,entry in enumerate(self.choices):
            self.list.item(index).setText(profile_label(entry,states.get(entry['id'],{})))
            self.list.item(index).setIcon(QIcon(str(backend.icon_path(entry))))
        index=self.list.currentRow()
        self.rename_button.setEnabled(index>=0);self.default_button.setEnabled(index>=0)
        preferred=index>=0 and states.get(self.choices[index]['id'],{}).get('preferred',False)
        self.default_button.setText('Retirar padrão' if preferred else 'Usar como padrão')

    def rename_profile(self):
        index=self.list.currentRow()
        if index<0:return
        entry=self.choices[index]
        name,ok=QInputDialog.getText(self,'Renomear perfil','Nome do perfil / conta:',text=entry['session'])
        if not ok:return
        try:
            backend.rename_session(entry['id'],name)
            self.choices[index]=backend.read_record(entry['id']);self.refresh_status();self.error.clear()
        except (OSError,ValueError) as exc:self.error.setText(str(exc))

    def toggle_default(self):
        index=self.list.currentRow()
        if index<0:return
        entry=self.choices[index]
        try:
            if backend.preferred_profile(entry['url'])==entry['id']:
                backend.clear_preferred_profile(entry['id'])
            else:backend.set_preferred_profile(entry['id'])
            self.refresh_status();self.error.clear()
        except (OSError,ValueError) as exc:self.error.setText(str(exc))

    def update_selection(self):
        self.open_button.setEnabled(any(self.list.item(i).checkState()==Qt.CheckState.Checked for i in range(self.list.count())))

    def open_selected(self):
        try:
            for i in range(self.list.count()):
                item=self.list.item(i)
                if item.checkState()==Qt.CheckState.Checked:
                    backend.launch(item.data(Qt.ItemDataRole.UserRole))
                    item.setCheckState(Qt.CheckState.Unchecked)
        except (OSError,ValueError) as exc:self.error.setText(str(exc));return
        self.accept()

    def new_profile(self):
        if create_profile(self.choices[0],self):self.accept()


def open_site(url, parent=None):
    choices=backend.sessions(url)
    if not choices:
        dialog=InstallDialog({'url':url},parent)
        if dialog.exec():backend.launch(dialog.identifier)
        return
    if len(choices)==1:
        backend.launch(choices[0]['id']);return
    ProfilePicker(choices,parent).exec()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--offer');parser.add_argument('--launch');parser.add_argument('--open-site');parser.add_argument('--open-app');parser.add_argument('--new-profile');parser.add_argument('--preferences');args=parser.parse_args()
    for item in backend.installed():
        entry=backend.apps_dir()/f'linuxbr-webapp-{item["id"]}.desktop'
        if 'NoDisplay=true' not in entry.read_text():backend.save_record(item['id'],item)
    if args.launch:
        backend.launch(args.launch);return
    app=QApplication(sys.argv);app.setApplicationName('Linux BR — Aplicativos web')
    app.setDesktopFileName('linuxbr-webapps')
    if args.preferences:
        try:ProfilePreferences(args.preferences).exec()
        except (OSError,ValueError) as exc:QMessageBox.warning(None,'Não foi possível abrir',str(exc))
        return
    if args.new_profile or args.open_app:
        try:
            item=backend.read_record(args.new_profile or args.open_app)
            if args.new_profile:create_profile(item)
            else:open_site(item['url'])
        except (OSError,ValueError) as exc:QMessageBox.warning(None,'Não foi possível abrir',str(exc))
        return
    if args.open_site:
        try:open_site(args.open_site)
        except (OSError,ValueError) as exc:QMessageBox.warning(None,'Não foi possível abrir',str(exc))
        return
    if args.offer:
        try:dialog=InstallDialog(json.loads(args.offer))
        except (ValueError,KeyError,TypeError) as exc:QMessageBox.warning(None,'Endereço inválido',str(exc));return
        if dialog.exec():
            if dialog.new_session:backend.launch(dialog.identifier)
            else:QMessageBox.information(None,'Aplicativo instalado','Pronto! Procure o aplicativo no menu do Linux BR ou em Aplicativos web.')
        return
    window=Window();window.show();app.exec()

if __name__=='__main__':main()
