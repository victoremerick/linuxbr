"""Backup, updates and recovery entry points using native desktop services."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QFileDialog, QFrame, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget)
from visual_style import BUTTONS


def plain(text):
    label = QLabel(text); label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def launch(parent, argv):
    if shutil.which(argv[0]) and QProcess.startDetached(argv[0], argv[1:])[0]:
        return
    box = QMessageBox(parent); box.setWindowTitle('Ferramenta indisponível')
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText('Não foi possível abrir esta ferramenta. Confira a instalação pela Loja Linux BR.')
    box.setIcon(QMessageBox.Icon.Warning); box.exec()


class RecoveryPage(QWidget):
    def __init__(self, section='backup'):
        super().__init__()
        body = QVBoxLayout(self); body.setContentsMargins(28,24,28,24); body.setSpacing(16)
        title = plain('Backup e recuperação'); title.setStyleSheet('font-size:26px;font-weight:600')
        body.addWidget(title)
        body.addWidget(plain('Proteja seus arquivos, mantenha o computador atualizado e encontre ajuda.'))
        advanced=QPushButton(QIcon.fromTheme('tools-wizard'),'Abrir opções avançadas de recuperação…')
        advanced.clicked.connect(lambda:launch(self,['linuxbr-recovery-options']));body.addWidget(advanced)
        self.tabs = QTabWidget(); body.addWidget(self.tabs,1)
        self.update_process = None
        self.backup_page(); self.updates_page(); self.help_page(); self.system_page()
        self.tabs.setCurrentIndex({'backup':0,'updates':1,'help':2,'system':3}.get(section,0))

    def page(self, title):
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(20,20,20,20)
        scroll.setWidget(page);layout.setSpacing(14);self.tabs.addTab(scroll,title)
        return layout

    def button(self, body, title, argv=None, callback=None):
        button = QPushButton(title)
        icons = {'Configurar cópias de segurança…':'preferences-system-backup',
                 'Conferir último backup, destino e espaço':'security-high',
                 'Conferir condições antes de atualizar':'system-software-update',
                 'Explorar e restaurar uma cópia com versões…':'document-revert',
                 'Abrir arquivos de uma cópia simples…':'document-open-folder',
                 'Ver discos e espaço disponível':'drive-harddisk',
                 'Ver atualizações do sistema e dos aplicativos':'system-software-update',
                 'Gerenciar programas instalados':'view-list-details',
                 'Abrir Loja Linux BR':'system-software-install',
                 'Conferir rede e conexão':'network-wireless',
                 'Abrir Este computador':'computer',
                 'Consultar discos e partições':'partitionmanager',
                 'Abrir guia de recuperação':'help-browser',
                 'Salvar informações para suporte…':'document-save',
                 'Abrir instalador do Linux BR':'system-software-install',
                 'Configurar e gerenciar pontos de restauração…':'preferences-system-backup',
                 'Atualizar informações':'view-refresh',
                 'Pontos de restauração do sistema':'preferences-system-backup',
                 'Ler novidades desta versão':'help-about'}
        button.setIcon(QIcon.fromTheme(icons.get(title,'help-hint')))
        button.clicked.connect(callback if callback else lambda:launch(self,argv))
        body.addWidget(button,0,Qt.AlignmentFlag.AlignLeft)
        return button

    def backup_page(self):
        body = self.page('Meus arquivos')
        body.addWidget(plain('1. Conecte um disco externo com espaço suficiente.\n'
                            '2. Escolha as pastas e o destino em Configurar cópias de segurança.\n'
                            '3. Prefira cópia com versões para recuperar arquivos alterados ou apagados.'))
        self.button(body,'Configurar cópias de segurança…',['kcmshell6','kcm_kup'])
        body.addWidget(plain('O plano de backup permite escolher o intervalo e acompanhar a execução. '
                            'A sincronização simples acompanha as exclusões da origem e não guarda versões antigas.'))
        self.button(body,'Explorar e restaurar uma cópia com versões…',callback=self.restore_versions)
        self.button(body,'Abrir arquivos de uma cópia simples…',callback=self.browse_copy)
        body.addWidget(plain('Ao restaurar, escolha primeiro outra pasta para conferir os arquivos. '
                            'Cópias dos dados pessoais podem incluir contas salvas, perfis web e programas Wine. '
                            'Feche esses aplicativos antes de copiar seus perfis e guarde o disco em local protegido.'))
        self.backup_status = plain(''); body.addWidget(self.backup_status)
        self.button(body,'Conferir último backup, destino e espaço',['linuxbr-maintenance','--section','protection'])
        self.button(body,'Ver discos e espaço disponível',['linuxbr-system','--page','Armazenamento'])
        body.addStretch()

    def updates_page(self):
        body = self.page('Atualizações')
        self.update_status = plain('Consultando a versão e as fontes locais de atualização…')
        body.addWidget(self.update_status)
        self.button(body,'Atualizar informações',callback=self.refresh_update_status)
        self.button(body,'Conferir condições antes de atualizar',['linuxbr-maintenance','--section','protection'])
        self.button(body,'Ler novidades desta versão',['xdg-open','/usr/share/doc/linuxbr-system/README.md'])
        self.button(body,'Pontos de restauração do sistema',callback=lambda:self.tabs.setCurrentIndex(3))
        body.addWidget(plain('O Discover mostra as atualizações disponíveis, suas fontes e as confirmações necessárias. '
                            'Use energia estável e mantenha uma cópia recente dos documentos.'))
        self.button(body,'Ver atualizações do sistema e dos aplicativos',['linuxbr-store','--updates'])
        self.button(body,'Gerenciar programas instalados',['linuxbr-store','--installed'])
        self.button(body,'Abrir Loja Linux BR',['linuxbr-store'])
        body.addWidget(plain('Atualizações de firmware aparecem no Discover quando o equipamento é compatível. '
                            'Siga as instruções do fabricante e mantenha a alimentação conectada.'))
        body.addWidget(plain('As atualizações vêm das fontes configuradas no computador. '
                            'Esta tela não troca a versão principal do sistema nem adiciona repositórios automaticamente.'))
        self.button(body,'Conferir rede e conexão',['linuxbr-system','--page','Rede'])
        body.addStretch()
        QTimer.singleShot(0,self.refresh_update_status)

    def refresh_update_status(self):
        if self.update_process is not None:
            return
        process=QProcess(self);self.update_process=process
        def done(*_):
            if self.update_process is not process:
                return
            self.update_process=None
            try:
                data=json.loads(bytes(process.readAllStandardOutput()).decode())
                source='Fonte Linux BR configurada' if data['sources'] else 'Fonte Linux BR ainda não configurada'
                text='Versão instalada: '+(data['installed'] or 'indisponível')+'\n'
                text+='Versão candidata nos índices locais: '+(data['candidate'] or 'indisponível')+'\n'+source
                if data['reboot_recommended']:text+='\nReinicialização recomendada para concluir atualizações.'
                text+='\nUse o Discover para buscar atualizações e conferir a origem antes de instalar.'
                self.update_status.setText(text)
            except (ValueError,KeyError,UnicodeError):
                self.update_status.setText('Não foi possível consultar as informações locais. Abra o Discover para conferir as atualizações.')
            except RuntimeError:
                return
            process.deleteLater()
        process.finished.connect(done);process.errorOccurred.connect(done)
        process.start('/usr/bin/python3',['/usr/lib/linuxbr-system/update_status.py'])

    def stop_update_query(self):
        process=self.update_process
        self.update_process=None
        if process is not None:
            try:
                process.kill();process.waitForFinished(1000);process.deleteLater()
            except RuntimeError:
                pass

    def closeEvent(self,event):
        self.stop_update_query()
        super().closeEvent(event)

    def system_page(self):
        from snapshot_service import status
        body=self.page('Pontos do sistema')
        body.addWidget(plain('Pontos de restauração recuperam arquivos e configurações do sistema. '
                            'O backup de documentos continua separado na aba Meus arquivos.'))
        body.addWidget(plain('Abra o Timeshift, escolha o modo RSYNC e um destino com espaço suficiente, '
                            'preferencialmente em outro disco. Mantenha as pastas pessoais excluídas. '
                            'A criação do primeiro ponto pode demorar.'))
        info=status()
        text='Destino configurado no Timeshift.' if info['configured'] else 'Primeira configuração pendente; nenhum ponto automático será criado até escolher o destino.'
        if info['live']:text+=' Sessão Live: selecione o disco e o ponto do sistema instalado para restaurar.'
        elif info['configured']:
            text+=' A proteção automática está '+('ativada.' if info['automatic'] else 'desativada pela administração.')
        last=info['last'].get('status')
        text+='\n'+{'created':'Última proteção automática: ponto criado.',
                      'failed':'A última criação falhou; a atualização foi interrompida.',
                      'not-configured':'A última atualização não tinha destino de restauração configurado.',
                      'disabled':'A proteção automática estava desativada na última atualização.'}.get(last,'')
        body.addWidget(plain(text))
        self.button(body,'Configurar e gerenciar pontos de restauração…',['timeshift-launcher'])
        body.addWidget(plain('Depois da configuração, atualizações APT importantes criam um ponto antes de alterar '
                            'os pacotes. Se a criação falhar, a atualização é interrompida. '
                            'Para restaurar um sistema que não inicia, use o Live no mesmo modo UEFI ou BIOS '
                            'da instalação e abra esta ferramenta. Confira o disco de destino antes de confirmar.'))
        body.addWidget(plain('Sem configuração, as atualizações continuam disponíveis e a falta de proteção é informada. '
                            'Pontos não são criados antes de instalações manuais com dpkg, atualizações Flatpak ou firmware.'))
        body.addStretch()

    def help_page(self):
        body = self.page('Ajuda e recuperação')
        body.addWidget(plain('Se o sistema não iniciar, use o pendrive Live do Linux BR. '
                            'Abra Este computador para localizar os documentos e copiá-los para outro disco '
                            'antes de reinstalar. Uma cópia de arquivos não é uma imagem completa do sistema.'))
        self.button(body,'Abrir Este computador',['dolphin','linuxbr:/'])
        self.button(body,'Consultar discos e partições',['partitionmanager'])
        self.button(body,'Abrir guia de recuperação',['linuxbr-welcome','--topic','Recuperação e ajuda'])
        self.button(body,'Salvar informações para suporte…',callback=self.export_report)
        body.addWidget(plain('O relatório contém versão, kernel, tipo de sessão e espaço disponível. '
                            'Você escolhe onde salvar e com quem compartilhar; nada é enviado automaticamente.'))
        if Path('/run/live/medium').is_dir():
            body.addWidget(plain('Você está em uma sessão Live. Alterações podem ser perdidas ao desligar.'))
            self.button(body,'Abrir instalador do Linux BR',['calamares-install-linuxbr'])
        body.addStretch()

    def restore_versions(self):
        folder = QFileDialog.getExistingDirectory(self,'Escolher pasta da cópia com versões',str(Path.home()))
        if folder: launch(self,['kup-filedigger',folder])

    def browse_copy(self):
        folder = QFileDialog.getExistingDirectory(self,'Escolher pasta da cópia simples',str(Path.home()))
        if folder: launch(self,['dolphin',folder])

    def export_report(self):
        from welcome import support_report
        filename,_ = QFileDialog.getSaveFileName(self,'Salvar informações para suporte',
            str(Path.home()/'linuxbr-suporte.txt'),'Texto (*.txt)')
        if not filename:return
        try:
            Path(filename).write_text(support_report(),encoding='utf-8')
        except OSError as error:
            box=QMessageBox(self);box.setTextFormat(Qt.TextFormat.PlainText)
            box.setWindowTitle('Não foi possível salvar');box.setText(str(error));box.exec()

    def showEvent(self,event):
        super().showEvent(event)
        config = Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'kuprc'
        self.backup_status.setText('Há uma configuração de backup nesta conta. Abra o plano para verificar o último resultado.'
            if config.is_file() else 'Configure um plano para começar. Nenhuma cópia é iniciada sem sua escolha.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--section',choices=['backup','updates','help','system'],default='backup')
    args=parser.parse_args()
    app=QApplication(sys.argv);app.setDesktopFileName('linuxbr-recovery')
    window=QMainWindow();window.setWindowTitle('Backup e recuperação — Linux BR')
    window.setWindowIcon(QIcon.fromTheme('preferences-system-backup'));window.setStyleSheet(BUTTONS)
    window.resize(920,680);window.setCentralWidget(RecoveryPage(args.section));window.show()
    return app.exec()


if __name__=='__main__':sys.exit(main())
