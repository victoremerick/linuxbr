"""User confirmation and management for Chromium app windows."""
import argparse
import json
import sys
from urllib.parse import urlsplit
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication,QDialog,QDialogButtonBox,QVBoxLayout,QLabel,
    QLineEdit,QMainWindow,QWidget,QListWidget,QListWidgetItem,QHBoxLayout,QPushButton,QMessageBox,QInputDialog)
import webapps_backend as backend
from visual_style import BUTTONS

class InstallDialog(QDialog):
    def __init__(self, data=None, parent=None, new_session=False):
        super().__init__(parent)
        self.setStyleSheet(BUTTONS)
        self.setWindowIcon(QIcon.fromTheme('applications-internet'))
        self.setWindowTitle('Instalar aplicativo web — Linux BR');self.resize(570,390)
        layout=QVBoxLayout(self)
        title=QLabel('Um site, uma janela própria');title.setStyleSheet('font-size:23px;font-weight:600');layout.addWidget(title)
        description=QLabel('O aplicativo aparecerá no menu do Linux BR e usará o Chromium atualizado pelo sistema.');description.setWordWrap(True);layout.addWidget(description)
        layout.addWidget(QLabel('Nome do aplicativo'))
        self.name=QLineEdit();self.name.setMaxLength(70);layout.addWidget(self.name)
        layout.addWidget(QLabel('Endereço inicial HTTPS'))
        self.url=QLineEdit();self.url.setPlaceholderText('https://servico.com/');layout.addWidget(self.url)
        layout.addWidget(QLabel('Nome da sessão / conta'))
        self.session=QLineEdit('Principal');self.session.setMaxLength(70);self.session.setPlaceholderText('Ex.: Pessoal, Trabalho, Loja');layout.addWidget(self.session)
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
        buttons.rejected.connect(self.reject);buttons.accepted.connect(self.install);layout.addWidget(buttons)
        self.identifier=None

    def install(self):
        try:
            new_session = self.new_session or bool(backend.sessions(self.url.text(), True))
            self.identifier=backend.install({'name':self.name.text(),'url':self.url.text(),
                                            'session':self.session.text(),'new_session':new_session})
        except (ValueError,OSError) as exc:
            self.error.setText(str(exc));return
        self.accept()

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Linux BR — Aplicativos web');self.resize(850,590)
        self.setStyleSheet(BUTTONS)
        self.setWindowIcon(QIcon.fromTheme('applications-internet'))
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        title=QLabel('Aplicativos web');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        info=QLabel('Instale sites como aplicativos com janela própria. No Chromium, use o botão “Aplicativos web Linux BR” para sugestões e preferências.');info.setWordWrap(True);layout.addWidget(info)
        self.list=QListWidget();layout.addWidget(self.list)
        self.list.itemDoubleClicked.connect(lambda _item:self.open_app())
        row=QHBoxLayout();layout.addLayout(row)
        for label,action in [('Adicionar site',self.add),('Abrir sessão',self.open_app),('Nova sessão',self.new_session),('Renomear',self.rename)]:
            button=QPushButton(label);button.clicked.connect(action);row.addWidget(button)
        more=QHBoxLayout();layout.addLayout(more)
        for label,action in [('Remover do menu',self.remove),('Restaurar sessão',self.restore),('Atualizar lista',self.refresh)]:
            button=QPushButton(label);button.clicked.connect(action);more.addWidget(button)
        note=QLabel('Pessoal, Trabalho ou outras contas: cada sessão mantém cookies e login separados e pode abrir junto das demais. O nome é escolhido por você; o Linux BR não lê a conta do site. Remover do menu preserva os dados para restauração.');note.setWordWrap(True);layout.addWidget(note)
        self.refresh()

    def refresh(self):
        self.items=backend.installed();self.list.clear()
        from webapp_icons import request_refresh
        self.list.setIconSize(QSize(32,32))
        for item in self.items:
            backend.prepare_icon(item)
            entry=QListWidgetItem(QIcon(str(backend.icon_path(item))),f'{backend.display_name(item)} — {urlsplit(item["url"]).hostname}')
            self.list.addItem(entry); request_refresh(item['url'])
        if not hasattr(self,'icon_timer'):
            self.icon_timer=QTimer(self);self.icon_timer.setInterval(2000)
            self.icon_timer.timeout.connect(self.refresh_icons);self.icon_timer.start()
        if self.items:self.list.setCurrentRow(0)

    def refresh_icons(self):
        for index,item in enumerate(self.items):
            entry=self.list.item(index)
            if entry:entry.setIcon(QIcon(str(backend.icon_path(item))))

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
        self.setStyleSheet(BUTTONS);self.resize(520,360)
        layout=QVBoxLayout(self)
        title=QLabel(choices[0]['name']);title.setStyleSheet('font-size:24px;font-weight:600');layout.addWidget(title)
        layout.addWidget(QLabel('Selecione um ou mais perfis para abrir:'))
        self.list=QListWidget();layout.addWidget(self.list)
        for entry in choices:
            item=QListWidgetItem(QIcon(str(backend.icon_path(entry))),entry['session'])
            item.setData(Qt.ItemDataRole.UserRole,entry['id'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked);self.list.addItem(item)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        row=QHBoxLayout();layout.addLayout(row)
        self.new_button=QPushButton('+ Novo perfil');self.new_button.clicked.connect(self.new_profile);row.addWidget(self.new_button)
        cancel=QPushButton('Cancelar');cancel.clicked.connect(self.reject);row.addWidget(cancel)
        self.open_button=QPushButton('Abrir selecionados');self.open_button.setProperty('primary',True)
        self.open_button.clicked.connect(self.open_selected);row.addWidget(self.open_button)
        self.open_button.setEnabled(False);self.list.itemChanged.connect(self.update_selection)

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

    def showEvent(self,event):
        super().showEvent(event)
        screen=QApplication.primaryScreen()
        if screen:
            frame=self.frameGeometry();frame.moveCenter(screen.availableGeometry().center());self.move(frame.topLeft())

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
    parser=argparse.ArgumentParser();parser.add_argument('--offer');parser.add_argument('--launch');parser.add_argument('--open-site');parser.add_argument('--open-app');parser.add_argument('--new-profile');args=parser.parse_args()
    for item in backend.installed():
        entry=backend.apps_dir()/f'linuxbr-webapp-{item["id"]}.desktop'
        if 'NoDisplay=true' not in entry.read_text():backend.save_record(item['id'],item)
    if args.launch:
        backend.launch(args.launch);return
    app=QApplication(sys.argv);app.setApplicationName('Linux BR — Aplicativos web')
    app.setDesktopFileName('linuxbr-webapps')
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
