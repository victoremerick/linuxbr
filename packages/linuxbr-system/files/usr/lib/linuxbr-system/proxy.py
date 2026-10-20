"""User-scoped KDE proxy settings. No global network or root configuration writes."""
import subprocess
from urllib.parse import urlsplit
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLabel,QLineEdit,QComboBox,QPushButton


def validate_url(value,schemes):
    if any(ord(c)<32 for c in value):raise ValueError('Endereço inválido.')
    try:
        url=urlsplit(value)
        if url.scheme not in schemes or not url.hostname or url.username or url.password or url.fragment:raise ValueError()
        port=url.port
    except ValueError:raise ValueError('Use um endereço completo sem usuário ou senha, como http://proxy.empresa:8080.')
    return value

class Proxy(QWidget):
    def __init__(self):
        super().__init__();body=QVBoxLayout(self);body.setContentsMargins(32,28,32,28)
        title=QLabel('Proxy');title.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(title)
        note=QLabel('Configuração de proxy dos aplicativos KDE. Navegadores e outros programas podem ter configuração própria; esta página não altera o proxy do APT ou de serviços do sistema.');note.setWordWrap(True);body.addWidget(note)
        form=QFormLayout();self.mode=QComboBox();self.mode.addItems(['Sem proxy','Manual','Arquivo de configuração automática (PAC)'])
        self.http=QLineEdit();self.https=QLineEdit();self.pac=QLineEdit();self.exceptions=QLineEdit()
        for field in (self.http,self.https):field.setPlaceholderText('http://proxy.empresa:8080')
        self.pac.setPlaceholderText('https://empresa/proxy.pac');self.exceptions.setPlaceholderText('localhost,127.0.0.1,.empresa.local')
        for label,widget in [('Modo',self.mode),('HTTP',self.http),('HTTPS',self.https),('PAC',self.pac),('Exceções',self.exceptions)]:form.addRow(label,widget)
        body.addLayout(form);button=QPushButton('Salvar proxy');button.clicked.connect(self.save);body.addWidget(button)
        self.status=QLabel();self.status.setWordWrap(True);body.addWidget(self.status);body.addStretch()
        try:
            values={key:subprocess.check_output(['kreadconfig6','--file','kioslaverc','--group','Proxy Settings','--key',key],text=True,timeout=2).strip() for key in ('ProxyType','httpProxy','httpsProxy','Proxy Config Script','NoProxyFor')}
            self.mode.setCurrentIndex({'0':0,'1':1,'2':2}.get(values['ProxyType'],0))
            for field,key in [(self.http,'httpProxy'),(self.https,'httpsProxy'),(self.pac,'Proxy Config Script'),(self.exceptions,'NoProxyFor')]:field.setText(values[key])
        except (OSError,subprocess.SubprocessError):pass
    def save(self):
        try:
            mode=self.mode.currentIndex()
            if mode==1:
                if not self.http.text().strip() and not self.https.text().strip():raise ValueError('Informe ao menos um proxy.')
                for field in (self.http,self.https):
                    if field.text().strip():validate_url(field.text().strip(),('http','https'))
            if mode==2:validate_url(self.pac.text().strip(),('http','https'))
            if any(ord(c)<32 for c in self.exceptions.text()):raise ValueError('Exceções inválidas.')
            for key,value in [('httpProxy',self.http.text().strip()),('httpsProxy',self.https.text().strip()),('Proxy Config Script',self.pac.text().strip()),('NoProxyFor',self.exceptions.text()),('ProxyType',str(mode))]:
                subprocess.run(['kwriteconfig6','--file','kioslaverc','--group','Proxy Settings','--key',key,value],check=True,timeout=3)
            subprocess.run(['dbus-send','--session','--type=signal','/KIO/Scheduler','org.kde.KIO.Scheduler.reparseSlaveConfiguration','string:'],check=False,timeout=3)
            self.status.setText('Proxy salvo. Reabra os aplicativos para garantir que utilizem a nova configuração.')
        except (ValueError,OSError,subprocess.SubprocessError) as error:self.status.setText('Não foi possível salvar: '+str(error))
