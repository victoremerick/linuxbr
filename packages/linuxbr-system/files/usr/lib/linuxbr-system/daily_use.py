"""Practical desktop tasks using the installed system tools."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTabWidget,QPushButton,QScrollArea
from recovery import launch

TASKS=[
 ('Pendrives e discos','Abra Este computador para localizar as unidades pela letra e pelo nome. Use Remover com segurança antes de desconectar. Se um disco do Windows estiver somente para leitura, encerre o Windows completamente e confira a Inicialização rápida antes de tentar novamente.',[
  ('Abrir Este computador',['dolphin','linuxbr:/']),('Ver armazenamento',['linuxbr-system','--page','Armazenamento'])]),
 ('Pastas de rede','Para acessar um compartilhamento Windows, use o endereço do computador e o nome da pasta. Informe a conta do servidor quando solicitado. Mapear uma unidade permite encontrá-la por uma letra. A conexão depende da rede e das permissões do servidor.',[
  ('Mapear unidade de rede',['linuxbr-file-tools','--map-network']),('Procurar na rede',['dolphin','network:/'])]),
 ('Impressoras','Ligue a impressora e conecte-a à mesma rede ou por USB. Adicione o equipamento na janela de impressoras e imprima uma página de teste. Impressoras de rede compatíveis com IPP podem dispensar instaladores do fabricante.',[
  ('Adicionar ou gerenciar impressoras',['kcmshell6','kcm_printer_manager']),('Digitalizar documento',['skanpage'])]),
 ('Som e Bluetooth','Selecione a saída de som e o microfone usados por cada aplicativo. Para um headset Bluetooth, faça o pareamento e confira o perfil de áudio. O modo de chamadas pode reduzir a qualidade de reprodução.',[
  ('Saídas, entradas e volumes',['linuxbr-system','--page','Áudio']),('Parear dispositivo Bluetooth',['kcmshell6','kcm_bluetooth'])]),
 ('Aplicativos padrão','Clique com o botão direito em um arquivo e escolha Abrir com para experimentar outro aplicativo. Para tornar a escolha permanente, use as propriedades do tipo de arquivo. Os padrões do navegador e do e-mail ficam em Aplicativos padrão.',[
  ('Escolher aplicativos padrão',['kcmshell6','kcm_componentchooser']),('Configurar tipos de arquivo',['kcmshell6','kcm_filetypes'])]),
 ('Leitura e teclado','Ajuste a escala da tela antes de aumentar fontes individuais. As configurações de acessibilidade oferecem recursos para teclado, visão e interação. Confira o resultado nos aplicativos que você usa.',[
  ('Acessibilidade',['kcmshell6','kcm_access']),('Escala da tela',['linuxbr-system','--page','Telas']),('Tamanho das fontes',['kcmshell6','kcm_fonts'])]),
]

class DailyUse(QWidget):
    def __init__(self):
        super().__init__();body=QVBoxLayout(self)
        title=QLabel('Uso diário');title.setStyleSheet('font-size:26px;font-weight:600');body.addWidget(title)
        tabs=QTabWidget();body.addWidget(tabs)
        for name,description,actions in TASKS:
            scroll=QScrollArea();scroll.setWidgetResizable(True);page=QWidget();layout=QVBoxLayout(page)
            note=QLabel(description);note.setWordWrap(True);note.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(note)
            for caption,argv in actions:
                button=QPushButton(caption);button.clicked.connect(lambda checked=False,command=argv:launch(self,command));layout.addWidget(button)
            layout.addStretch();scroll.setWidget(page);tabs.addTab(scroll,name)
