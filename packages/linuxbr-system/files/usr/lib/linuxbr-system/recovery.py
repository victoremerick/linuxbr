"""Backup, updates and recovery entry points using native desktop services."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QInputDialog, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget)
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
                 'Recuperar atualização…':'edit-undo',
                 'Revisar resultado da atualização gerenciada…':'document-preview',
                 'Gerar diagnóstico…':'document-export',
                 'Consultar pedido de diagnóstico da TI…':'network-server',
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
        if Path('/etc/linuxbr/update-waves.json').is_file():
            self.wave_button = self.button(body, 'Revisar resultado da atualização gerenciada…',
                                           callback=self.review_wave)
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

    def review_wave(self):
        from desktop_jobs import Command

        helper = '/usr/lib/linuxbr-system/wave_review.py'
        process = QProcess(self)
        self.wave_button.setEnabled(False)
        self.wave_button.setText('Conferindo revisão gerenciada…')

        def complete(code, *_):
            self.wave_button.setEnabled(True)
            self.wave_button.setText('Revisar resultado da atualização gerenciada…')
            try:
                if code:
                    error = bytes(process.readAllStandardError()).decode('utf-8', 'replace').strip()
                    raise ValueError(error or 'Não foi possível consultar o resultado.')
                data = json.loads(bytes(process.readAllStandardOutput()))
                names = {'completed': 'Concluída', 'failed': 'Falhou', 'restored': 'Restaurada'}
                choices = {f"{item['revision']} · {names[item['state']]}": item for item in data['outcomes']}
                if not choices:
                    QMessageBox.information(self, 'Revisar atualização gerenciada', data['summary'])
                    return
                selected, accepted = QInputDialog.getItem(self, 'Informar resultado à TI',
                    data['summary'] + '\nConfirme somente após verificar o funcionamento do computador.',
                    list(choices), editable=False)
                if accepted:
                    result = choices[selected]
                    Command('Informar resultado à organização', ['/usr/bin/pkexec', helper, 'submit',
                            result['revision'], result['state']], self,
                            success_message='Resultado registrado no painel da organização.')
            except (ValueError, KeyError, TypeError) as error:
                box = QMessageBox(self)
                box.setWindowTitle('Revisar atualização gerenciada')
                box.setTextFormat(Qt.TextFormat.PlainText)
                box.setText(str(error)[:600])
                box.exec()
            finally:
                process.deleteLater()

        process.finished.connect(complete)
        process.errorOccurred.connect(lambda error: complete(1)
                                      if error == QProcess.ProcessError.FailedToStart else None)
        process.start('/usr/bin/pkexec', [helper, 'preview'])

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
        point = info['last_success']
        comment = point.get('point_comment')
        if isinstance(comment, str) and comment:
            body.addWidget(plain('Último ponto de atualização gerenciada. Confira este comentário '
                                 'no Timeshift: ' + comment))
        holds = info['held_revisions']
        if holds is None:
            body.addWidget(plain('A lista de revisões suspensas precisa de revisão administrativa.'))
        elif holds:
            body.addWidget(plain('Revisões suspensas neste computador\n' + ', '.join(holds)))
        self.button(body,'Configurar e gerenciar pontos de restauração…',['timeshift-launcher'])
        self.button(body,'Recuperar atualização…',['linuxbr-recover-update'])
        body.addWidget(plain('Para usar o assistente, escolha outra partição ext4 como destino '
                            'dos pontos RSYNC no Timeshift.'))
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
        self.diagnostic_button = self.button(body,'Gerar diagnóstico…',callback=self.export_report)
        self.remote_diagnostic_button = self.button(body, 'Consultar pedido de diagnóstico da TI…',
                                                    callback=self.check_remote_diagnostic)
        body.addWidget(plain('Revise as informações do sistema, da rede, das atualizações e da sessão '
                            'gráfica antes de salvar. Um pedido da TI só é enviado depois da sua revisão e confirmação.'))
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

    def export_report(self, request_id=None):
        process = QProcess(self)
        self.diagnostic_button.setEnabled(False)
        self.remote_diagnostic_button.setEnabled(False)
        process.finished.connect(lambda *_: self.preview_report(process, request_id))
        process.errorOccurred.connect(lambda error: self.preview_report(process, request_id)
            if error == QProcess.ProcessError.FailedToStart else None)
        process.start('/usr/bin/python3', [str(Path(__file__).with_name('support_diagnostics.py'))])

    def remote_diagnostic(self, action, callback, payload=None):
        process = QProcess(self)
        self.remote_diagnostic_button.setEnabled(False)
        self.diagnostic_button.setEnabled(False)
        if payload is not None:
            def submit():
                process.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
                process.closeWriteChannel()
            process.started.connect(submit)

        def done(code, *_):
            self.remote_diagnostic_button.setEnabled(True)
            self.diagnostic_button.setEnabled(True)
            try:
                data = json.loads(bytes(process.readAllStandardOutput())) if code == 0 else None
            except (ValueError, UnicodeError):
                data = None
            process.deleteLater()
            if not isinstance(data, dict):
                QMessageBox.warning(self, 'Diagnóstico da organização',
                                    'A operação não foi concluída. Confira o cadastro e a conexão ou tente novamente.')
                return
            callback(data)

        process.finished.connect(done)
        process.errorOccurred.connect(lambda error: done(1)
            if error == QProcess.ProcessError.FailedToStart else None)
        process.start('/usr/bin/pkexec', ['/usr/lib/linuxbr-system/support_remote.py', action])

    def check_remote_diagnostic(self):
        def reviewed(data):
            identifier = data.get('request_id')
            if not identifier:
                QMessageBox.information(self, 'Diagnóstico da organização', 'Nenhum pedido pendente.')
                return
            self.export_report(identifier)
        self.remote_diagnostic('pending', reviewed)

    def preview_report(self, process, request_id=None):
        from support_diagnostics import CATEGORIES, render, summary
        if self.diagnostic_button.isEnabled():
            return
        self.diagnostic_button.setEnabled(True)
        self.remote_diagnostic_button.setEnabled(True)
        try:
            sections = json.loads(bytes(process.readAllStandardOutput()))
            if not isinstance(sections, dict) or sections.keys() != CATEGORIES.keys():
                raise ValueError('Diagnóstico incompleto.')
        except (ValueError, UnicodeError):
            QMessageBox.warning(self, 'Diagnóstico', 'Não foi possível coletar o diagnóstico.')
            return
        finally:
            process.deleteLater()

        dialog = QDialog(self)
        dialog.setWindowTitle('Revisar diagnóstico solicitado pela TI' if request_id
                              else 'Revisar diagnóstico para suporte')
        dialog.resize(650, 500)
        layout = QVBoxLayout(dialog)
        preview = QPlainTextEdit(readOnly=True)
        choices = {}
        for key, label in CATEGORIES.items():
            box = QCheckBox(label)
            box.setChecked(True)
            choices[key] = box
            layout.addWidget(box)
        layout.addWidget(preview)
        technical = QCheckBox('Mostrar os dados em JSON')
        layout.addWidget(technical)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        if request_id:
            send = buttons.button(QDialogButtonBox.StandardButton.Save)
            send.setText('Enviar à organização')
            send.setAutoDefault(False)
            later = buttons.button(QDialogButtonBox.StandardButton.Cancel)
            later.setText('Decidir depois')
            later.setDefault(True)
            decline = buttons.addButton('Recusar pedido', QDialogButtonBox.ButtonRole.ActionRole)
            decline.setAutoDefault(False)
            decline.clicked.connect(lambda: dialog.done(2))
            layout.insertWidget(0, plain('A organização receberá somente as categorias marcadas abaixo. '
                                         'Você pode recusar o pedido ou decidir depois.'))
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        def selected():
            return [key for key, box in choices.items() if box.isChecked()]

        def refresh():
            categories = selected()
            display = render if technical.isChecked() else summary
            preview.setPlainText(display(sections, categories))
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(bool(categories))

        for box in choices.values():
            box.toggled.connect(refresh)
        technical.toggled.connect(refresh)
        refresh()
        outcome = dialog.exec()
        if request_id and outcome == 2:
            self.remote_diagnostic('decline', lambda _: QMessageBox.information(
                self, 'Diagnóstico da organização', 'Pedido recusado. As categorias do diagnóstico ficaram neste computador.'),
                {'request_id': request_id})
            return
        if outcome != QDialog.DialogCode.Accepted:
            return
        report = render(sections, selected())
        if request_id:
            def sent(data):
                if data.get('sent') is True:
                    QMessageBox.information(self, 'Diagnóstico da organização', 'Diagnóstico enviado.')
            self.remote_diagnostic('send', sent, {
                'request_id': request_id, 'report': json.loads(report)})
            return
        filename, _ = QFileDialog.getSaveFileName(self, 'Salvar diagnóstico',
            str(Path.home() / 'linuxbr-suporte.json'), 'JSON (*.json)')
        if not filename:
            return
        try:
            Path(filename).write_text(report, encoding='utf-8')
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
