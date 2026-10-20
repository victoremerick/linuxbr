"""Fixed Windows-X style actions from the Start button context menu."""
import os
import shlex
import shutil
import sys
from urllib.parse import urlsplit
from PyQt6.QtCore import QProcess, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLabel,QLineEdit,QDialogButtonBox,QMessageBox


COMMANDS = {
    'apps':['linuxbr-system','--page','Programas'],
    'power-settings':['linuxbr-system','--page','Energia e bateria'],
    'logs':['linuxbr-system','--page','Administração'],
    'system':['linuxbr-system','--page','Sistema'],
    'devices':['linuxbr-system','--page','Dispositivos'],
    'users':['linuxbr-system','--page','Usuários'],
    'network':['linuxbr-system','--page','Endereços IP e DNS'],
    'disks':['linuxbr-system','--page','Armazenamento'],
    'firewall':['linuxbr-system','--page','Firewall'],
    'audio':['linuxbr-system','--page','Áudio'],
    'tasks':['linuxbr-system','--page','Gerenciador de tarefas'],
    'settings':['linuxbr-system'],
    'terminal':['konsole'],
    'files':['dolphin'],
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
    dialog=QDialog();dialog.setWindowTitle('Executar — Linux BR');dialog.resize(450,150)
    body=QVBoxLayout(dialog);body.addWidget(QLabel('Digite o nome de um aplicativo, caminho ou comando:'))
    entry=QLineEdit();entry.setAccessibleName('Abrir');body.addWidget(entry)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);body.addWidget(buttons)
    entry.setFocus()
    if dialog.exec()!=QDialog.DialogCode.Accepted:return
    value=entry.text().strip()
    if os.path.exists(os.path.expanduser(value)):
        ok=QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.expanduser(value)))
    else:
        try:parts=shlex.split(value)
        except ValueError:parts=[]
        ok=bool(parts and (shutil.which(parts[0]) or os.path.isfile(parts[0])) and QProcess.startDetached(parts[0],parts[1:])[0])
    if not ok:QMessageBox.warning(dialog,'Executar','Não foi possível abrir o item informado.')


def main(argv):
    app=QApplication(argv)
    try:action=action_from_url(argv[1]) if len(argv)==2 else 'run' if len(argv)==1 else None
    except ValueError:action=None
    if action=='run':run_dialog();return 0
    if action is None:return 2
    command=COMMANDS[action]
    if not shutil.which(command[0]):return 1
    return 0 if QProcess.startDetached(command[0],command[1:])[0] else 1


if __name__=='__main__':sys.exit(main(sys.argv))
