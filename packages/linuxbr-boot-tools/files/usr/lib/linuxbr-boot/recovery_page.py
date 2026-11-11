"""Recovery entry points shared by installed and live sessions."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from PyQt6.QtCore import QProcess,Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QGridLayout,QLabel,
    QPushButton,QMessageBox,QFileDialog,QDialog,QPlainTextEdit,QDialogButtonBox)


class Recovery(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Linux BR — Recuperação');self.setWindowIcon(QIcon.fromTheme('document-revert'));self.resize(960,700);self.processes=[]
        root=QWidget();self.setCentralWidget(root);body=QVBoxLayout(root)
        title=QLabel('Recuperação e opções avançadas');title.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(title)
        self.live=Path('/run/live/medium').exists();note=QLabel('Use os pontos de restauração para recuperar uma atualização. O backup pessoal é separado dos arquivos de sistema. Confira o destino antes de restaurar. '+('Esta sessão foi iniciada pela mídia live e pode recuperar o sistema instalado.' if self.live else 'Se o sistema não iniciar, use estas ferramentas pela mídia live.'));note.setWordWrap(True);body.addWidget(note)
        grid=QGridLayout();body.addLayout(grid,1)
        actions=[('Continuar com inicialização normal','go-home',lambda:self.boot('normal')),
                 ('Entrar no ambiente de manutenção','tools-wizard',lambda:self.boot('recovery')),
                 ('Configurações de inicialização','system-reboot',lambda:self.launch(['linuxbr-boot-options'])),
                 ('Restaurar ponto do sistema ou atualização','document-revert',lambda:self.launch(['timeshift-launcher'])),
                 ('Recuperar arquivos de uma cópia','folder-import',self.files),
                 ('Recriar menu do carregador','tools-check-spelling',self.repair),
                 ('Terminal de manutenção','utilities-terminal',self.terminal),
                 ('Consultar e exportar eventos do boot','view-list-text',self.logs),
                 ('Discos e partições','drive-harddisk',lambda:self.launch(['partitionmanager'])),
                 ('Escolher dispositivo nas configurações UEFI','preferences-system',self.firmware),
                 ('Reiniciar','system-reboot',lambda:self.power('reboot')),
                 ('Desligar','system-shutdown',lambda:self.power('poweroff')),
                 ('Recuperar atualização','edit-undo',lambda:self.launch(['linuxbr-recover-update']))]
        for i,(text,icon,action) in enumerate(actions):
            button=QPushButton(QIcon.fromTheme(icon),text);button.setMinimumHeight(68);button.clicked.connect(action);grid.addWidget(button,i//2,i%2)
            if self.live and i in (0,1,5):button.setEnabled(False);button.setToolTip('Na mídia live, selecione o sistema no carregador de boot ou restaure um ponto do sistema instalado.')
            if i==9 and not Path('/sys/firmware/efi').exists():button.setEnabled(False);button.setToolTip('Esta sessão foi iniciada em BIOS; a configuração UEFI não está disponível.')
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);body.addWidget(self.status)

    def confirm(self,text):
        return QMessageBox.question(self,'Confirmar',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes

    def launch(self,argv):
        if not shutil.which(argv[0]) or not QProcess.startDetached(argv[0],argv[1:])[0]:self.status.setText('Ferramenta indisponível: '+argv[0]+'. Confira os recursos instalados.')

    def command(self,argv,payload=None,then=None):
        process=QProcess(self);self.processes.append(process);process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        if payload is not None:process.started.connect(lambda:(process.write(json.dumps(payload).encode()),process.closeWriteChannel()))
        def finished(code,*_):
            text=bytes(process.readAllStandardOutput()).decode(errors='replace')
            self.status.setText('Operação concluída.' if code==0 else 'Operação não concluída: '+text[-2500:])
            if code==0 and then:then()
        process.finished.connect(finished);process.errorOccurred.connect(lambda error:self.status.setText('Não foi possível iniciar a operação: '+process.errorString()) if error==QProcess.ProcessError.FailedToStart else None);process.start(argv[0],argv[1:]);self.status.setText('Aguarde a autenticação administrativa e a conclusão…')

    def boot(self,mode):
        if not self.confirm('Salve seu trabalho. Reiniciar em '+('modo normal' if mode=='normal' else 'ambiente de manutenção')+'? A seleção valerá somente para a próxima inicialização.'):return
        self.command(['pkexec','python3','/usr/lib/linuxbr-boot/boot_backend.py'],dict(action='once',mode=mode),lambda:self.launch(['systemctl','reboot']))

    def terminal(self):
        self.launch(['xterm','-T','Linux BR — Terminal de manutenção','-fa','monospace','-fs','12','-e','bash','--rcfile','/usr/share/linuxbr/bashrc','-i'])

    def firmware(self):
        if self.confirm('Reiniciar nas configurações UEFI? Você poderá selecionar outro dispositivo de boot se o firmware oferecer essa opção. Salve seu trabalho antes de continuar.'):
            self.command(['systemctl','reboot','--firmware-setup'])

    def power(self,action):
        if self.confirm('Salve seu trabalho. '+('Reiniciar' if action=='reboot' else 'Desligar')+' este computador?'):self.command(['systemctl',action])

    def files(self):
        for folder in ['/usr/lib/linuxbr-system','/usr/lib/linuxbr-server']:
            target=Path(folder)/'migration.py'
            if target.is_file():self.launch(['python3',str(target),'--restore']);return
        self.status.setText('A ferramenta de cópia e verificação não está instalada. Use o gerenciador de arquivos para conferir uma cópia em outro disco.')

    def repair(self):
        menu=Path('/boot/grub/grub.cfg')
        if not menu.is_file():self.status.setText('O menu do sistema instalado não está acessível. Use a mídia live e restaure um ponto correspondente ao disco correto.');return
        if self.confirm('Recriar o menu GRUB usando os kernels e a configuração deste sistema? Uma cópia do menu atual será guardada. Esta ação não reinstala o carregador em discos nem repara partições.'):
            try:digest=hashlib.sha256(menu.read_bytes()).hexdigest()
            except PermissionError:digest=None
            self.command(['pkexec','python3','/usr/lib/linuxbr-boot/recovery_backend.py'],dict(action='repair-menu',sha256=digest))

    def logs(self):
        dialog=QDialog(self);dialog.setWindowTitle('Eventos da inicialização atual');dialog.resize(980,650);body=QVBoxLayout(dialog);view=QPlainTextEdit();view.setReadOnly(True);view.setMaximumBlockCount(4000);body.addWidget(view)
        process=QProcess(dialog);process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels);process.readyReadStandardOutput.connect(lambda:view.insertPlainText(bytes(process.readAllStandardOutput()).decode(errors='replace')));process.start('journalctl',['-b','-n','1500','--no-pager','-o','short-iso'])
        note=QLabel('A consulta respeita as permissões da sua conta. O arquivo exportado contém nomes, horários e mensagens locais; revise antes de compartilhar.');note.setWordWrap(True);body.addWidget(note)
        save=QPushButton(QIcon.fromTheme('document-save'),'Exportar eventos…')
        def export():
            name,_=QFileDialog.getSaveFileName(dialog,'Salvar eventos',str(Path.home()/'linuxbr-inicializacao.txt'),'Texto (*.txt)')
            if name:
                try:Path(name).write_text(view.toPlainText());self.status.setText('Eventos salvos em '+name)
                except OSError as error:QMessageBox.warning(dialog,'Não foi possível salvar',str(error))
        save.clicked.connect(export);body.addWidget(save);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);body.addWidget(buttons);dialog.exec()
        if process.state()!=QProcess.ProcessState.NotRunning:process.terminate();process.waitForFinished(1500)

    def closeEvent(self,event):
        if any(p.state()!=QProcess.ProcessState.NotRunning for p in self.processes):event.ignore();return
        super().closeEvent(event)


if __name__=='__main__':
    app=QApplication(sys.argv)
    sys.path.insert(0,'/usr/lib/linuxbr-server')
    from desktop_theme import initialize
    initialize();window=Recovery();window.show();sys.exit(app.exec())
