"""Fixed Windows-X style actions from the Start button context menu."""
import shutil
import sys
from urllib.parse import urlsplit
from PyQt6.QtCore import QProcess, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLabel,QMessageBox,QPushButton


COMMANDS = {
    'apps':['linuxbr-store','--installed'],
    'power-settings':['linuxbr-system','--page','Energia e bateria'],
    'logs':['linuxbr-system','--page','Administração'],
    'system':['linuxbr-system','--page','Sistema'],
    'devices':['linuxbr-system','--page','Dispositivos'],
    'users':['linuxbr-system','--page','Usuários'],
    'network':['linuxbr-system','--page','Endereços IP e DNS'],
    'disks':['linuxbr-system','--page','Armazenamento'],
    'firewall':['linuxbr-system','--page','Firewall'],
    'audio':['linuxbr-system','--page','Áudio'],
    'tasks':['linuxbr-task-manager'],
    'settings':['linuxbr-system'],
    'terminal':['konsole'],
    'files':['dolphin','linuxbr:/'],
    'search':['krunner'],
    'logout':['ksmserver-logout-greeter'],
}


def action_from_url(raw):
    parsed=urlsplit(raw)
    if parsed.scheme!='linuxbr-action' or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Ação desconhecida.')
    action=parsed.path.strip('/')
    if action not in COMMANDS and action!='run':raise ValueError('Ação desconhecida.')
    return action


def run_dialog():
    from run_dialog import run_dialog as show
    show()


def quick_access():
    dialog=QDialog();dialog.setWindowTitle('Acesso rápido — Linux BR');dialog.resize(390,570)
    body=QVBoxLayout(dialog)
    heading=QLabel('Ferramentas do sistema');heading.setStyleSheet('font-size:20px; font-weight:600')
    body.addWidget(heading)
    choices=[('Programas instalados','apps'),('Opções de energia','power-settings'),
             ('Sistema','system'),('Dispositivos e drivers','devices'),
             ('Conexões de rede','network'),('Armazenamento e unidades','disks'),
             ('Gerenciador de tarefas','tasks'),('Terminal','terminal'),
             ('Configurações','settings'),('Explorador de arquivos','files'),
             ('Executar…','run'),('Sair, reiniciar ou desligar…','logout')]
    def activate(action):
        if action=='run':
            dialog.accept();run_dialog();return
        from run_dialog import start
        try:start(COMMANDS[action])
        except ValueError as error:
            QMessageBox.warning(dialog,'Acesso rápido',str(error));return
        dialog.accept()
    for caption,action in choices:
        button=QPushButton(caption);button.setMinimumHeight(32)
        button.clicked.connect(lambda checked=False,key=action:activate(key));body.addWidget(button)
    dialog.exec()


def main(argv):
    app=QApplication(argv)
    if argv[1:]==['--quick-access']:
        app.setDesktopFileName('linuxbr-quick-access');quick_access();return 0
    app.setDesktopFileName('linuxbr-run')
    try:action=action_from_url(argv[1]) if len(argv)==2 else 'run' if len(argv)==1 else None
    except ValueError:action=None
    if action=='run':run_dialog();return 0
    if action is None:return 2
    command=COMMANDS[action]
    if not shutil.which(command[0]):return 1
    return 0 if QProcess.startDetached(command[0],command[1:])[0] else 1


if __name__=='__main__':sys.exit(main(sys.argv))
