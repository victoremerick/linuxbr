"""Visible command results and background read-only queries for desktop pages."""
import json
from PyQt6.QtCore import QProcess, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QDialogButtonBox,QMessageBox,QPushButton


class Query(QThread):
    result=pyqtSignal(object);failed=pyqtSignal(str)
    def __init__(self,callback,parent=None):super().__init__(parent);self.callback=callback
    def run(self):
        try:self.result.emit(self.callback())
        except Exception as error:self.failed.emit(str(error))


class Command(QDialog):
    completed=pyqtSignal(int)
    def __init__(self,title,argv,parent=None,input_data=None,structured=False,success_message=None):
        super().__init__(parent);self.structured=structured;self.success_message=success_message;self.buffer=b'';self.setWindowTitle(title);self.resize(640,180) if success_message else self.resize(820,560);self.setWindowIcon(QIcon.fromTheme('system-run'))
        self.setAttribute(__import__('PyQt6.QtCore',fromlist=['Qt']).Qt.WidgetAttribute.WA_DeleteOnClose)
        layout=QVBoxLayout(self);self.status=QLabel('Operação em andamento…');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.output=QPlainTextEdit();self.output.setReadOnly(True);self.output.setMaximumBlockCount(4000);layout.addWidget(self.output,1)
        self.details=None
        if success_message:
            self.output.hide();self.details=QPushButton(QIcon.fromTheme('document-preview'),'Ver detalhes técnicos');self.details.setCheckable(True);layout.addWidget(self.details)
            def toggle_details(visible):
                self.output.setVisible(visible);self.details.setText('Ocultar detalhes técnicos' if visible else 'Ver detalhes técnicos');self.resize(820,560) if visible else self.resize(640,180)
            self.details.toggled.connect(toggle_details)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);self.buttons.rejected.connect(self.reject);self.buttons.setEnabled(False);layout.addWidget(self.buttons)
        self.process=QProcess(self);self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels);self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished_command);self.process.errorOccurred.connect(self.error)
        if input_data is not None:
            self.process.started.connect(lambda:(self.process.write(input_data),self.process.closeWriteChannel()))
        self.process.start(argv[0],argv[1:]);self.show()

    def read(self):
        chunk=bytes(self.process.readAllStandardOutput())
        if not self.structured:self.output.insertPlainText(chunk.decode('utf-8',errors='replace'));return
        self.buffer+=chunk
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:value=json.loads(line)
            except ValueError:self.output.insertPlainText(line.decode('utf-8',errors='replace')+'\n');continue
            if value.get('event')=='output':self.output.insertPlainText(value.get('text',''))
            elif value.get('event')=='progress':self.status.setText('Andamento: '+str(value.get('percentage',0))+'%')
    def error(self,error):
        if error==QProcess.ProcessError.FailedToStart:self.output.appendPlainText(self.process.errorString());self.finished_command(127)
    def finished_command(self,code,*_):
        self.read();self.status.setText((self.success_message or 'Operação concluída.') if code==0 else 'Operação não concluída. Confira a mensagem abaixo.')
        if code!=0 and self.details:self.details.setChecked(True)
        self.buttons.setEnabled(True);self.completed.emit(code)
    def reject(self):
        if self.process.state()!=QProcess.ProcessState.NotRunning:QMessageBox.information(self,'Operação em andamento','Aguarde a conclusão antes de fechar esta janela.');return
        super().reject()
    def closeEvent(self,event):
        if self.process.state()!=QProcess.ProcessState.NotRunning:event.ignore();return
        super().closeEvent(event)
