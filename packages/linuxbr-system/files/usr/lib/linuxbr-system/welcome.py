"""Offline introduction and recovery help, shared with the system settings hub."""
import json
import argparse
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QProcess, Qt, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QHBoxLayout,
                            QLabel, QListWidget, QMainWindow, QMessageBox,
                            QPushButton, QTextBrowser, QVBoxLayout, QWidget)
from visual_style import BUTTONS


# Only these fixed commands can be launched from the local help documents.
ACTIONS = {
    'network': ['linuxbr-system', '--page', 'Rede'],
    'display': ['linuxbr-system', '--page', 'Telas'],
    'audio': ['linuxbr-system', '--page', 'Áudio'],
    'devices': ['linuxbr-system', '--page', 'Dispositivos'],
    'storage': ['linuxbr-system', '--page', 'Armazenamento'],
    'settings': ['linuxbr-system'],
    'language': ['linuxbr-system', '--page', 'Hora e idioma'],
    'accessibility': ['linuxbr-system', '--page', 'Acessibilidade'],
    'personalize': ['linuxbr-system', '--page', 'Personalização'],
    'defaults': ['linuxbr-system', '--page', 'Pesquisa e padrões'],
    'power': ['linuxbr-system', '--page', 'Energia e bateria'],
    'files': ['dolphin', 'linuxbr:/'],
    'store': ['linuxbr-store'],
    'updates': ['linuxbr-store','--updates'],
    'install': ['linuxbr-install-package'],
    'windows': ['linuxbr-windows'],
    'webapps': ['linuxbr-webapps'],
    'file-tools': ['linuxbr-file-tools'],
    'run': ['linuxbr-run'],
    'quick-access': ['linuxbr-quick-access'],
    'scanner': ['skanpage'],
    'backup': ['linuxbr-recovery'],
    'recovery': ['linuxbr-recovery','--section','help'],
}

TOPICS = {
    'Primeiros passos': '''
        <h1>Bem-vindo ao Linux BR</h1>
        <p>Seus arquivos, programas e configurações estão a poucos cliques.
        Use o menu Linux BR no canto inferior esquerdo para procurar um programa
        pelo nome. A tecla <b>Windows</b> também abre o menu.</p>
        <h2>Prepare seu computador</h2>
        <ol><li><a href="action:network">Conecte ao Wi-Fi ou à rede por cabo</a>.</li>
        <li><a href="action:language">Confira o teclado, o idioma e o fuso horário</a>.
        O padrão brasileiro usa ABNT2, cedilha, vírgula decimal e datas dia/mês/ano.
        Escolha o fuso da sua região.</li>
        <li><a href="action:display">Ajuste o tamanho do texto e a tela</a> ou
        <a href="action:accessibility">abra os recursos de acessibilidade</a>.</li>
        <li><a href="action:updates">Verifique as atualizações</a>. A janela mostra
        o que será atualizado e pode pedir sua senha.</li>
        <li><a href="action:store">Encontre programas na loja</a> e
        <a href="action:files">abra seus arquivos</a>.</li></ol>
        <h2>Conheça a área de trabalho</h2>
        <p>A barra inferior reúne o menu, os programas abertos, rede, volume,
        bateria, relógio e notificações. Clique com o botão direito em um programa
        aberto para fixá-lo. Use duplo clique para abrir arquivos e pastas.</p>
        <p><a href="action:personalize">Escolher tema claro, escuro e cor de destaque</a>
        · <a href="action:settings">Abrir a Central do Sistema</a></p>
        <p>Este guia funciona sem internet e fica disponível no menu como
        <b>Primeiros passos Linux BR</b>.</p>''',
    'Para quem vem do Windows': '''
        <h1>Você já conhece boa parte do caminho</h1>
        <table cellpadding="9" border="1" cellspacing="0">
        <tr><th>No Windows</th><th>No Linux BR</th></tr>
        <tr><td>Menu Iniciar</td><td>Menu Linux BR na barra inferior</td></tr>
        <tr><td>Explorador de Arquivos</td><td>Dolphin, com a visão Este computador</td></tr>
        <tr><td>Configurações / Painel de Controle</td><td>Central do Sistema</td></tr>
        <tr><td>Microsoft Store</td><td>Loja Linux BR: Linux, aplicativos web e Windows</td></tr>
        <tr><td>Windows Update</td><td>Atualizações na Central ou no Discover</td></tr>
        <tr><td>Word, Excel e PowerPoint</td><td>LibreOffice Writer, Calc e Impress</td></tr>
        <tr><td>Paint, Calculadora e Bloco de Notas</td><td>KolourPaint, KCalc e Kate</td></tr>
        <tr><td>Fotos e Reprodutor de mídia</td><td>Gwenview e VLC</td></tr>
        <tr><td>Gerenciador de Tarefas</td><td>Aplicativo próprio, Ctrl+Shift+Esc ou botão direito na barra</td></tr>
        </table>
        <h2>Arquivos e unidades</h2>
        <p><a href="action:files">Este computador</a> mostra as unidades.
        As letras são uma forma familiar de navegação: o sistema continua usando
        caminhos Linux. Seus documentos ficam na pasta pessoal. Em
        <a href="action:storage">Armazenamento</a> você gerencia discos e unidades de rede.</p>
        <p>Use Ctrl+C, Ctrl+X e Ctrl+V para copiar, recortar e colar; F2 renomeia;
        Delete envia para a lixeira. Ctrl+L permite digitar um caminho.
        Arquivos apagados de dispositivos ou serviços de rede podem não ir para a lixeira.</p>
        <h2>Programas de Windows</h2>
        <p><a href="action:windows">Programas Windows e jogos</a> abre EXE e MSI
        com Wine e oferece Steam/Proton e Bottles. A compatibilidade varia por
        programa; jogos com antitrapaça e aplicativos com drivers próprios podem
        exigir Windows. Um documento DOCX ou XLSX pode ser aberto no
        LibreOffice, mas macros, fontes e formatação complexa podem precisar de ajustes.
        Teste seus documentos de trabalho antes de migrar definitivamente.</p>
        <p>Aplicativos que exigem compatibilidade com Windows devem ser avaliados
        caso a caso. O Linux BR não instala essa compatibilidade automaticamente.</p>''',
    'Programas e arquivos': '''
        <h1>Instale e abra com facilidade</h1>
        <p>A <a href="action:store">loja de programas</a> permite pesquisar, instalar,
        remover e atualizar aplicativos. As fontes disponíveis aparecem na própria loja.
        A lista depende da conexão e dos repositórios configurados.</p>
        <p>Baixou um programa? Use <a href="action:install">Instalar a partir de arquivo</a>
        para revisar um pacote DEB ou Flatpak. Confira a origem e o nome antes de continuar.
        Pacotes RPM são de outra família de sistemas.</p>
        <h2>Aplicativos padrão</h2>
        <p>Chromium abre páginas da internet; Okular abre PDFs; Writer e Calc abrem
        documentos e planilhas. Você pode mudar essas escolhas em
        <a href="action:defaults">Pesquisa e padrões</a>. O menu de contexto
        <b>Abrir com</b> permite escolher outro programa para um arquivo.</p>
        <h2>Encontre seus documentos</h2>
        <p>Abra <a href="action:files">Este computador</a> e use as pastas Documentos,
        Downloads e Imagens. A pesquisa do menu encontra aplicativos; a pesquisa
        do gerenciador de arquivos ajuda a localizar documentos.</p>
        <p>Antes de remover um pendrive, use <b>Remover com segurança</b> no painel
        de dispositivos e aguarde a confirmação.</p>''',
    'Atalhos e uso diário': '''
        <h1>Atalhos familiares</h1>
        <p>A tecla chamada <b>Meta</b> nas configurações é normalmente a tecla Windows.</p>
        <table cellpadding="8" border="1" cellspacing="0">
        <tr><th>Teclas</th><th>Ação no padrão Linux BR</th></tr>
        <tr><td>Windows</td><td>Abrir o menu de programas</td></tr>
        <tr><td>Windows+E</td><td>Abrir os arquivos</td></tr>
        <tr><td>Windows+I</td><td>Abrir a Central do Sistema</td></tr>
        <tr><td>Windows+R</td><td>Executar: aplicativo, caminho ou site</td></tr>
        <tr><td>Windows+X</td><td>Acesso rápido às ferramentas do sistema</td></tr>
        <tr><td>Windows+S</td><td>Pesquisar programas e arquivos</td></tr>
        <tr><td>Windows+V</td><td>Histórico da área de transferência</td></tr>
        <tr><td>Windows+Shift+S</td><td>Capturar uma região da tela</td></tr>
        <tr><td>Windows+D</td><td>Mostrar a área de trabalho</td></tr>
        <tr><td>Windows+L</td><td>Bloquear a sessão</td></tr>
        <tr><td>Alt+Tab</td><td>Alternar entre janelas</td></tr>
        <tr><td>Alt+F4</td><td>Fechar a janela atual</td></tr>
        <tr><td>Alt+Espaço</td><td>Menu da janela: mover, minimizar e fechar</td></tr>
        <tr><td>Windows+↑ / Windows+↓</td><td>Maximizar / restaurar e depois minimizar</td></tr>
        <tr><td>Ctrl+Shift+Esc</td><td>Abrir o Gerenciador de tarefas</td></tr>
        <tr><td>Ctrl+Alt+Del</td><td>Bloquear, trocar usuário, sair, alterar senha e abrir tarefas</td></tr>
        <tr><td>Print</td><td>Abrir a captura de tela</td></tr>
        </table>
        <p>Esses padrões são preparados para contas novas. Você pode conferir ou
        alterar combinações em <b>Central → Entrada e atalhos</b>.
        Aplicativos também têm seus próprios atalhos.</p>
        <h2>Encerrar e economizar energia</h2>
        <p>O menu Linux BR oferece as opções de sessão e desligamento.
        <a href="action:power">Energia e bateria</a> reúne o tempo de tela,
        suspensão e comportamento da tampa do notebook.</p>''',
    'Executar, arquivos e atalhos': '''
        <h1>Continue usando nomes conhecidos</h1>
        <p>Pressione <b>Windows+R</b> ou <a href="action:run">abra Executar</a>.
        Experimente <b>control</b> para a Central, <b>notepad</b> para texto,
        <b>calc</b> para calculadora, <b>mspaint</b> para desenho, <b>cmd</b> para terminal,
        <b>taskmgr</b> para processos e <b>appwiz.cpl</b> para programas instalados.</p>
        <p><b>winver</b> mostra o sistema; <b>ncpa.cpl</b>, a rede; <b>mmsys.cpl</b>, o som;
        <b>devmgmt.msc</b>, dispositivos; <b>diskmgmt.msc</b>, unidades.
        Esses nomes abrem os equivalentes Linux. Comandos de PowerShell ou CMD
        dentro do terminal continuam dependendo do interpretador correspondente.</p>
        <p><b>%USERPROFILE%</b> abre sua pasta pessoal, <b>%TEMP%</b> a pasta temporária,
        <b>shell:downloads</b> os downloads e <b>shell:startup</b> as opções de inicialização.
        Digite uma letra, como <b>D:</b>, para abrir uma unidade. Para um arquivo específico,
        use <b>Procurar</b> ou o caminho Linux. Endereços https:// abrem no navegador.</p>
        <h2>Atalhos e rede</h2>
        <p><a href="action:file-tools">Arquivos e atalhos</a> cria atalhos para arquivos,
        pastas e sites e oferece o assistente de unidade de rede.
        No Dolphin, o botão direito também oferece <b>Copiar caminho</b> e
        <b>Criar atalho</b>. O menu <b>Criar novo</b> inclui documento de texto e RTF.</p>
        <p>Um endereço Windows como <b>\\\\servidor\\compartilhamento</b> pode ser informado
        no assistente de rede. A senha é solicitada pelo sistema quando necessária.
        Use F2 para renomear, Alt+↑ para subir uma pasta, Alt+← para voltar,
        Ctrl+L para editar o endereço e Ctrl+H para mostrar arquivos ocultos.</p>
        <h2>Documentos e periféricos</h2>
        <p>LibreOffice abre documentos, planilhas e apresentações do Office.
        Fontes Carlito e Caladea ajudam a manter medidas usadas em documentos recebidos.
        Macros, fontes ausentes e recursos específicos podem alterar o resultado;
        revise documentos importantes antes de enviá-los.</p>
        <p>Contas novas começam com a interface <b>Em abas</b> no LibreOffice.
        Use <b>Exibir → Interface do usuário</b> para escolher outro formato.
        A recuperação automática é preparada a cada cinco minutos, mas continue
        usando <b>Ctrl+S</b> para salvar o documento original.</p>
        <p><a href="action:scanner">Digitalizar documentos</a> cria PDFs de scanners
        compatíveis. Impressoras e scanners modernos podem usar IPP e AirScan;
        modelos antigos ainda podem exigir suporte específico do fabricante.</p>''',
    'Aplicativos web e contas': '''
        <h1>Seus sites como aplicativos</h1>
        <p>A <a href="action:store">Loja Linux BR</a> reúne programas Linux,
        aplicativos web e opções Windows. Sites do catálogo podem ser instalados
        como janelas próprias do Chromium e aparecem no menu.</p>
        <p>Os dados de login ficam no perfil daquele aplicativo. Com um perfil salvo,
        o aplicativo abre diretamente. Com vários, a caixa central permite marcar
        um ou mais perfis para abrir. O botão <b>+ Novo perfil</b> cria outra sessão
        com nome próprio e abre uma nova janela na página inicial.</p>
        <p>Você pode separar Trabalho e Pessoal no mesmo serviço, como WhatsApp.
        O próprio site ainda pode pedir novo login, limitar sessões ou exigir assinatura.
        Fechar uma janela preserva os dados; sair da conta dentro do site encerra
        aquele login. Bloquear sua sessão protege o acesso de outras pessoas ao computador.</p>
        <p><a href="action:webapps">Gerenciar aplicativos web e perfis</a></p>''',
    'Recuperação e ajuda': '''
        <h1>Resolva os problemas mais comuns</h1>
        <h2>Sem internet</h2><p><a href="action:network">Confira a rede e o Wi-Fi</a>.
        Confirme a senha e se o modo avião está desligado. Se só um site falha,
        teste outro antes de mudar as configurações.</p>
        <h2>Sem som ou microfone</h2><p><a href="action:audio">Abra Áudio</a>, confira
        a saída selecionada, o volume e se o microfone está silenciado.</p>
        <h2>Texto pequeno ou imagem fora da tela</h2>
        <p><a href="action:display">Abra Telas</a> para ajustar a escala e a resolução.
        Ao testar uma mudança, confirme somente se a imagem estiver legível.
        Em caso de tela preta, aguarde a reversão automática.</p>
        <h2>Programa travado ou atualização com erro</h2>
        <p>Salve o trabalho nos outros programas. Procure
        <b>Gerenciador de Tarefas</b> no menu ou pressione <b>Ctrl+Shift+Esc</b>.
        Encerrar um processo pode perder o trabalho não salvo. Ele também fica
        no menu de contexto da barra de tarefas.
        Para atualizações, confira a internet, a data e o espaço livre;
        <a href="action:updates">reabra as atualizações</a> e consulte a mensagem do erro.</p>
        <h2>Dispositivo não reconhecido</h2>
        <p><a href="action:devices">Consulte Dispositivos e drivers</a>.
        Confira o modelo e as opções disponíveis antes de instalar um driver.</p>
        <h2>Cópia de segurança e inicialização</h2>
        <p><b>Unidade do Windows somente para leitura:</b> uma partição NTFS pode
        permanecer protegida quando o Windows está hibernado ou usa Inicialização
        Rápida. Retorne ao Windows, salve o trabalho e faça um desligamento completo;
        confira também a opção de Inicialização Rápida. Não force a gravação nem
        apague o arquivo de hibernação para contornar o aviso.</p>
        <p>Mantenha uma cópia dos documentos em outro disco ou serviço escolhido
        por você. Letras de unidade não substituem uma cópia de segurança.</p>
        <p><a href="action:backup">Configurar backup ou restaurar arquivos</a> ·
        <a href="action:recovery">Abrir recuperação e suporte</a></p>
        <p>Se o sistema não iniciar, use o pendrive Live do Linux BR para inspecionar
        e copiar arquivos para outro dispositivo. Não formate nem reinstale antes
        de confirmar a cópia dos dados. No menu de boot, remover <b>quiet splash</b>
        temporariamente permite consultar mensagens de diagnóstico.</p>
        <p>O botão <b>Salvar informações para suporte</b> exporta a versão do sistema,
        kernel, tipo de sessão e espaço livre da pasta pessoal. Você escolhe onde
        salvar e com quem compartilhar. Nenhum relatório é enviado automaticamente.</p>''',
}


def preferences_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'linuxbr/welcome.json'


def is_live_session():
    return Path('/run/live/medium').is_dir() and bool(shutil.which('calamares-install-linuxbr'))


def load_preferences(path=None):
    try:
        value = json.loads((path or preferences_path()).read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def should_autostart(preferences):
    return preferences.get('show_on_login') is True or preferences.get('seen') is not True


def save_preferences(show_on_login, path=None):
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'seen': True, 'show_on_login': bool(show_on_login)}) + '\n')
    temporary.replace(path)


def support_report():
    try:
        release = platform.freedesktop_os_release().get('PRETTY_NAME', 'Indisponível')
    except OSError:
        release = 'Indisponível'
    disk = shutil.disk_usage(Path.home())
    return '\n'.join([
        'Linux BR — informações para suporte',
        'Gerado em: ' + datetime.now().astimezone().isoformat(timespec='seconds'),
        'Sistema: ' + release, 'Kernel: ' + platform.release(),
        'Arquitetura: ' + platform.machine(),
        'Sessão: ' + os.environ.get('XDG_SESSION_TYPE', 'Indisponível'),
        f'Espaço livre da pasta pessoal: {disk.free / 1024**3:.1f} GiB de {disk.total / 1024**3:.1f} GiB',
        '', 'Descreva o problema e os passos para reproduzir abaixo:', '',
    ])


class HelpPage(QWidget):
    def __init__(self, launch, topic='Primeiros passos'):
        super().__init__()
        self.launch = launch
        body = QVBoxLayout(self)
        body.setContentsMargins(24, 16, 24, 16)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setAccessibleName('Guia de uso do Linux BR')
        self.browser.document().setDefaultStyleSheet('h1 {font-size:24px} h2 {font-size:18px} p,li,td {line-height:1.5}')
        self.browser.anchorClicked.connect(self.follow_link)
        body.addWidget(self.browser, 1)
        footer = QHBoxLayout()
        report = QPushButton('Salvar informações para suporte')
        report.setIcon(QIcon.fromTheme('document-save'))
        report.clicked.connect(self.export_report)
        footer.addWidget(report)
        footer.addStretch()
        body.addLayout(footer)
        self.set_topic(topic)

    def set_topic(self, title):
        self.browser.setHtml(TOPICS[title])
        self.browser.moveCursor(self.browser.textCursor().MoveOperation.Start)

    def follow_link(self, url):
        if url.scheme() == 'action' and url.path() in ACTIONS:
            self.launch(list(ACTIONS[url.path()]))

    def export_report(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Salvar informações para suporte',
                                                str(Path.home() / 'linuxbr-suporte.txt'), 'Texto (*.txt)')
        if not filename:
            return
        try:
            Path(filename).write_text(support_report(), encoding='utf-8')
        except OSError as error:
            QMessageBox.warning(self, 'Não foi possível salvar', str(error))
        else:
            QMessageBox.information(self, 'Informações salvas', 'O arquivo foi salvo. Compartilhe-o com a pessoa que está ajudando você, se desejar.')


class Welcome(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Primeiros passos Linux BR')
        self.setWindowIcon(QIcon.fromTheme('linuxbr'))
        self.setStyleSheet(BUTTONS)
        self.resize(1000, 650)
        self.setMinimumSize(720, 480)
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        header = QLabel('Linux BR  ·  Seu computador, em português')
        header.setStyleSheet('font-size:20px;font-weight:600;padding:12px')
        layout.addWidget(header)
        prepare=QPushButton('Preparar meu computador…')
        prepare.clicked.connect(lambda:self.launch(['linuxbr-setup']))
        layout.addWidget(prepare,0,Qt.AlignmentFlag.AlignLeft)
        self.live_install = None
        if is_live_session():
            live = QHBoxLayout()
            note = QLabel('Você está experimentando o Linux BR em uma sessão Live.')
            note.setWordWrap(True)
            live.addWidget(note, 1)
            self.live_install = QPushButton('Instalar Linux BR')
            self.live_install.setProperty('primary', True)
            self.live_install.clicked.connect(lambda: self.launch(['calamares-install-linuxbr']))
            live.addWidget(self.live_install)
            layout.addLayout(live)
        content = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setAccessibleName('Assuntos do guia')
        self.nav.addItems(list(TOPICS))
        self.nav.setMinimumWidth(195)
        self.nav.setMaximumWidth(250)
        self.page = HelpPage(self.launch)
        self.nav.currentTextChanged.connect(self.page.set_topic)
        content.addWidget(self.nav); content.addWidget(self.page, 1)
        layout.addLayout(content, 1)
        footer = QHBoxLayout()
        self.show_on_login = QCheckBox('Mostrar esta janela ao entrar')
        self.show_on_login.setChecked(load_preferences().get('show_on_login') is True)
        footer.addWidget(self.show_on_login); footer.addStretch()
        close = QPushButton('Começar a usar'); close.clicked.connect(self.close)
        footer.addWidget(close); layout.addLayout(footer)
        self.nav.setCurrentRow(0)

    def launch(self, command):
        if not shutil.which(command[0]) or not QProcess.startDetached(command[0], command[1:])[0]:
            QMessageBox.warning(self, 'Não foi possível abrir', 'A ferramenta solicitada não está disponível. Abra a Central do Sistema pelo menu e confira a instalação dos programas.')

    def closeEvent(self, event):
        try:
            save_preferences(self.show_on_login.isChecked())
        except OSError as error:
            QMessageBox.warning(self, 'Preferência não salva', str(error))
        event.accept()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--autostart',action='store_true')
    parser.add_argument('--topic',choices=list(TOPICS));args=parser.parse_args()
    if args.autostart and not should_autostart(load_preferences()):
        return 0
    application = QApplication(sys.argv)
    application.setDesktopFileName('linuxbr-welcome')
    window = Welcome(); window.show()
    if args.topic:window.nav.setCurrentRow(list(TOPICS).index(args.topic))
    return application.exec()


if __name__ == '__main__':
    sys.exit(main())
