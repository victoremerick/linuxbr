"""Review and schedule authenticated boot settings."""
import json
import sys
from PyQt6.QtCore import QProcess,Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QSpinBox,QPushButton,QMessageBox
from grub_modes import MODES


class BootOptions(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.record=None;self.process=None;self.jobs=set();self.setWindowTitle('Configurações de inicialização');self.resize(880,580)
        layout=QVBoxLayout(self);title=QLabel('Inicialização do sistema');title.setStyleSheet('font-size:26px;font-weight:600');layout.addWidget(title)
        note=QLabel('Escolha um modo para a próxima inicialização ou defina explicitamente um padrão. O modo de segurança bloqueia rede, serviços opcionais e programas automáticos. A opção com rede mantém compartilhamento e acesso remoto bloqueados.');note.setWordWrap(True);layout.addWidget(note)
        self.current=QLabel('Autentique para consultar as opções do carregador instalado. Nenhuma alteração será feita durante a consulta.');self.current.setWordWrap(True);self.current.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.current)
        form=QFormLayout();self.mode=QComboBox()
        for key,(label,_) in MODES.items():self.mode.addItem(label,key)
        form.addRow('Modo:',self.mode);self.timeout=QSpinBox();self.timeout.setRange(3,120);self.timeout.setValue(5);self.timeout.setSuffix(' segundos');form.addRow('Tempo do menu:',self.timeout);layout.addLayout(form)
        self.note=QLabel('F8 abre as opções avançadas durante o menu do carregador. Se o firmware interceptar a tecla, escolha a entrada visível “Opções avançadas”. Vídeo básico e diagnóstico não aplicam as restrições do modo de segurança.');self.note.setWordWrap(True);layout.addWidget(self.note)
        self.buttons=[]
        for label,icon,action in [('Consultar opções','view-refresh',None),('Usar somente na próxima inicialização','system-reboot','once'),('Salvar como padrão','document-save','persistent'),('Cancelar seleção temporária','edit-undo','cancel'),('Restaurar configuração anterior','document-revert','restore')]:
            button=QPushButton(QIcon.fromTheme(icon),label);button.clicked.connect(lambda _,a=action:self.request(a));layout.addWidget(button);self.buttons.append(button)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status);layout.addStretch();self.ready()

    def ready(self):
        busy=self.process is not None
        for index,button in enumerate(self.buttons):button.setEnabled(not busy and (index==0 or bool(self.record and self.record['available'] and not self.record['live'])))

    def request(self,action):
        if self.process is not None:return
        request=dict(action=action,mode=self.mode.currentData(),timeout=self.timeout.value(),expected_sha256=self.record['config_sha256'] if self.record else '')
        if action:
            message={'once':'Usar este modo somente na próxima inicialização? O computador não reiniciará agora.',
                     'persistent':'Definir este modo como padrão permanente? Para sair de um modo restrito, escolha Inicialização normal nas opções avançadas.',
                     'cancel':'Cancelar a próxima inicialização especial do Linux BR?',
                     'restore':'Restaurar a configuração de menu anterior?'}[action]
            if QMessageBox.question(self,'Confirmar configuração',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        process=QProcess(self);self.process=process;self.jobs.add(process);self.buffer=b'';self.errors=b''
        process.readyReadStandardOutput.connect(lambda:self.capture(process,False));process.readyReadStandardError.connect(lambda:self.capture(process,True))
        process.finished.connect(lambda code,*_:self.finished(process,code))
        process.errorOccurred.connect(lambda error:self.finished(process,127) if error==QProcess.ProcessError.FailedToStart else None)
        args=['/usr/bin/python3','/usr/lib/linuxbr-boot/boot_backend.py']
        if action is None:args.append('--status')
        else:process.started.connect(lambda:(process.write(json.dumps(request).encode()),process.closeWriteChannel()))
        self.status.setText('Aguardando autorização e conclusão da operação…');self.ready();process.start('pkexec',args)

    def capture(self,process,error):
        if error:self.errors=(self.errors+bytes(process.readAllStandardError()))[-16384:]
        else:self.buffer=(self.buffer+bytes(process.readAllStandardOutput()))[-65536:]

    def finished(self,process,code):
        if self.process is not process:return
        self.capture(process,False);self.capture(process,True)
        if code==0:
            try:
                self.record=json.loads(self.buffer)
                mode=self.record['default'];self.current.setText('Padrão: '+(MODES[mode][0] if mode in MODES else 'Definido pela configuração existente')+'\nPróximo boot: '+(self.record['next'] or 'Padrão configurado'))
                if self.record['timeout'] is not None:self.timeout.setValue(self.record['timeout'])
                self.status.setText('Configuração consultada e verificada.' if self.record['available'] else 'Este carregador ainda não possui as entradas avançadas. Instale ou repare o pacote de inicialização.')
            except (ValueError,KeyError,TypeError):self.status.setText('Não foi possível interpretar o estado do carregador.')
        else:self.status.setText(self.errors.decode('utf-8','replace').strip() or 'Operação cancelada ou não autorizada.')
        self.jobs.discard(process);self.process=None;process.deleteLater();self.ready()

    def closeEvent(self,event):
        if self.jobs:event.ignore()
        else:super().closeEvent(event)


if __name__=='__main__':
    app=QApplication(sys.argv)
    sys.path.insert(0,'/usr/lib/linuxbr-server')
    from desktop_theme import initialize
    initialize();window=BootOptions();window.show();sys.exit(app.exec())
