"""Native protection status, diagnostics and reviewed storage cleanup."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import threading

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QTabWidget, QVBoxLayout, QWidget)
from migration import size_text
from migration_backend import Cancelled
from protection_status import protection_report, repository_addresses, check_repository_tls
from recovery import launch
from storage_cleanup import scan, clean
from troubleshooting import PROBLEMS, diagnose
from visual_style import BUTTONS
from desktopflows08 import SettingsButton


class Job(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(dict)
    def __init__(self, callback):
        super().__init__(); self.callback = callback; self.cancel = threading.Event()
    def run(self):
        try: self.result.emit(self.callback(self.cancel, self.progress.emit))
        except Cancelled: self.cancelled.emit()
        except Exception as error:
            if self.cancel.is_set(): self.cancelled.emit()
            else: self.failed.emit(str(error))


def text_label(text):
    label = QLabel(text); label.setWordWrap(True); label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def date_text(value, missing='Não registrado'):
    if not value: return missing
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is not None: parsed=parsed.astimezone()
        return parsed.strftime('%d/%m/%Y às %H:%M:%S')
    except (ValueError,TypeError):
        return 'Data indisponível'


class MaintenancePage(QWidget):
    def __init__(self, section='protection'):
        super().__init__(); self.jobs = set(); self.cleanup_plan = None; self.cleanup_job = None
        self.cleanup_generation = 0; self.diagnostic_generation = 0; self.diagnostic_job = None
        body = QVBoxLayout(self); title = text_label('Cuidados com o computador')
        title.setStyleSheet('font-size:24px;font-weight:600'); body.addWidget(title)
        self.tabs = QTabWidget(); body.addWidget(self.tabs)
        self.build_protection(); self.build_diagnostics(); self.build_storage()
        self.tabs.setCurrentIndex({'protection': 0, 'diagnostics': 1, 'storage': 2}.get(section, 0))

    def page(self, name):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        widget = QWidget(); layout = QVBoxLayout(widget); scroll.setWidget(widget)
        self.tabs.addTab(scroll, name); return layout

    def button(self, layout, caption, icon, callback):
        button = SettingsButton(caption); button.setIcon(QIcon.fromTheme(icon)); button.clicked.connect(callback)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft); return button

    def start_job(self, callback, done, button=None, on_finished=None, on_cancelled=None, deliver_cancelled=False):
        job = Job(callback); self.jobs.add(job)
        if button: button.setEnabled(False)
        def cancelled():
            if on_cancelled: on_cancelled()
        def result(value):
            if job.cancel.is_set() and not deliver_cancelled: cancelled()
            else: done(value)
        def failed(message):
            if job.cancel.is_set(): cancelled()
            else: QMessageBox.warning(self, 'Não foi possível concluir', message)
        job.result.connect(result); job.failed.connect(failed); job.cancelled.connect(cancelled)
        def finished():
            self.jobs.discard(job)
            if button: button.setEnabled(True)
            job.deleteLater()
        job.finished.connect(finished)
        if on_finished: job.finished.connect(on_finished)
        job.start(); return job

    def build_protection(self):
        body = self.page('Proteção e atualização')
        body.addWidget(text_label('Confira o estado registrado pelas ferramentas de backup e recuperação. '
                                  'As consultas não iniciam cópias nem alteram o sistema.'))
        self.protection_text = QPlainTextEdit(); self.protection_text.setReadOnly(True)
        self.protection_text.setAccessibleName('Condições de proteção e atualização'); body.addWidget(self.protection_text, 1)
        self.protection_text.setPlainText('Clique em Conferir proteção para consultar os planos, destinos e condições atuais.')
        self.check_protection = self.button(body, 'Conferir proteção e condições para atualizar', 'security-high', self.refresh_protection)
        self.button(body, 'Configurar cópias dos meus arquivos', 'preferences-system-backup', lambda: launch(self, ['kcmshell6', 'kcm_kup']))
        self.button(body, 'Abrir pontos de restauração do sistema', 'document-revert', lambda: launch(self, ['timeshift-launcher']))
        self.button(body, 'Conferir e abrir atualizações', 'system-software-update', self.open_updates)
        self.tls_check = self.button(body, 'Verificar certificado do servidor de atualizações', 'security-medium', self.verify_tls)
        body.addWidget(text_label('Datas de backup são registros do Kup; conferir uma restauração continua sendo necessário. '
                                  'O último ponto mostrado é o último sucesso automático registrado pela proteção APT.'))

    def refresh_protection(self):
        self.start_job(lambda *_: protection_report(), self.show_protection, self.check_protection)

    def show_protection(self, data):
        lines = ['CÓPIAS DOS MEUS ARQUIVOS']
        if not data['backups']: lines.append('Nenhum plano de backup encontrado nesta conta.')
        for plan in data['backups']:
            lines += ['', plan['name']]
            if plan.get('error'):
                lines.append(plan['error']); continue
            lines += ['Tipo: ' + ('Com versões' if plan['type'] == 'versions' else 'Sincronização sem histórico de versões'),
                      'Cópias habilitadas no Kup: ' + ('Sim' if plan.get('enabled') else 'Não'),
                      'Último sucesso registrado: ' + date_text(plan['last_complete'],'Ainda não registrado'),
                      'Destino: ' + (plan['destination'] or 'Não disponível; confira o disco externo'),
                      'Disponível agora: ' + ('Sim' if plan['available'] else 'Não')]
            if plan['free'] is not None: lines.append('Espaço livre no destino: ' + size_text(plan['free']))
        snapshot = data['snapshots']
        lines += ['', 'PONTOS DE RESTAURAÇÃO DO SISTEMA',
                  'Destino configurado: ' + ('Sim' if snapshot['configured'] else 'Não'),
                  'Destino montado agora: ' + ('Sim' if snapshot['destination_available'] else 'Não'),
                  'Último sucesso automático: ' + date_text(snapshot['last_success'])]
        if snapshot.get('free') is not None: lines.append('Espaço livre no destino: ' + size_text(snapshot['free']))
        if snapshot['last'].get('status') == 'failed': lines.append('A última proteção automática falhou; confira o Timeshift antes de atualizar.')
        preflight = data['preflight']
        lines += ['', 'CONDIÇÕES PARA ATUALIZAR', 'Consulta: ' + date_text(preflight['checked_at'])]
        if preflight['free'] is not None: lines.append('Espaço livre no sistema (C:): ' + size_text(preflight['free']))
        lines += preflight['warnings'] or ['Nenhum impedimento encontrado nas verificações de espaço, pacotes e energia disponíveis.']
        if preflight['dpkg_audit']: lines += ['', preflight['dpkg_audit']]
        for index in data['indexes']:
            lines += ['', 'Índice APT local: ' + index['index'], 'Válido até: ' + date_text(index['valid_until'],'Não informado')]
            if index['expired']: lines.append('O índice está vencido. O servidor precisa publicar índices assinados atualizados.')
        self.protection_text.setPlainText('\n'.join(lines))

    def open_updates(self):
        def done(data):
            self.show_protection(data)
            messages = data['preflight']['warnings'][:]
            if not data['snapshots']['configured']: messages.append('Nenhum destino Timeshift foi configurado para proteção automática do sistema.')
            if not any(item.get('last_complete') for item in data['backups']): messages.append('Não foi encontrado um backup pessoal concluído nos planos desta conta.')
            if data['backups'] and not any(item.get('enabled') for item in data['backups']): messages.append('Os planos de cópia pessoal estão desativados no Kup.')
            if messages and QMessageBox.question(self, 'Condições antes de atualizar', '\n'.join(messages) + '\n\nAbrir as atualizações para revisar?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            launch(self, ['linuxbr-store', '--updates'])
        self.start_job(lambda *_: protection_report(), done, self.check_protection)

    def verify_tls(self):
        def check(*_):
            addresses = repository_addresses(); records = []
            for address in addresses:
                try:
                    item = check_repository_tls(address)
                    records.append(f"{address}\nCertificado e nome verificados. Validade: {date_text(item['expires_at'])} ({item['days_remaining']} dias).")
                except Exception as error:
                    records.append(address + '\nNão foi possível validar: ' + str(error))
            return '\n\n'.join(records) if records else 'Nenhuma fonte HTTPS Linux BR ativa foi encontrada.'
        self.start_job(check, lambda value: self.protection_text.setPlainText(value), self.tls_check)

    def build_diagnostics(self):
        body = self.page('Resolver um problema')
        body.addWidget(text_label('Escolha a dificuldade e faça consultas locais. As correções e mudanças são ações separadas.'))
        self.problem = QComboBox(); self.problem.addItems(PROBLEMS); body.addWidget(self.problem)
        self.problem.setAccessibleName('Problema que deseja diagnosticar')
        self.diagnostic_text = QPlainTextEdit(); self.diagnostic_text.setReadOnly(True); body.addWidget(self.diagnostic_text, 1)
        self.diagnose_button = self.button(body, 'Verificar agora', 'tools-report-bug', self.run_diagnostics)
        self.action_box = QVBoxLayout(); body.addLayout(self.action_box)
        self.problem.currentTextChanged.connect(self.select_problem); self.select_problem(self.problem.currentText())

    def select_problem(self, problem):
        self.diagnostic_generation += 1
        if self.diagnostic_job: self.diagnostic_job.cancel.set()
        while self.action_box.count():
            item = self.action_box.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.diagnostic_text.setPlainText(PROBLEMS[problem]['help'])
        for caption, argv, icon in PROBLEMS[problem]['actions']:
            self.button(self.action_box, caption, icon, lambda checked=False, command=argv: launch(self, command))

    def run_diagnostics(self):
        problem = self.problem.currentText()
        self.diagnostic_generation += 1; generation = self.diagnostic_generation
        def done(data):
            if generation != self.diagnostic_generation or problem != self.problem.currentText(): return
            lines = [data['help']]
            for result in data['results']:
                lines += ['', result['title'] + ' — ' + {'completed': 'Consulta concluída', 'attention': 'Confira o resultado',
                                                         'unavailable': 'Indisponível'}[result['status']], result['output']]
            self.diagnostic_text.setPlainText('\n'.join(lines))
        def finished():
            if self.diagnostic_job is job: self.diagnostic_job = None
        job = self.start_job(lambda *_: diagnose(problem), done, self.diagnose_button, on_finished=finished)
        self.diagnostic_job = job

    def build_storage(self):
        body = self.page('Armazenamento e limpeza')
        body.addWidget(text_label('Revise o conteúdo antes de limpar. Cache considera apenas arquivos com mais de 24 horas. '
                                  'Documentos, downloads, perfis web, ambientes Wine e backups ficam fora desta limpeza.'))
        self.button(body, 'Analisar o espaço por pastas', 'filelight', lambda: launch(self, ['filelight', str(Path.home())]))
        self.category = QComboBox(); self.category.addItem('Cache antigo da minha conta', 'cache'); self.category.addItem('Lixeira da minha conta', 'trash')
        self.category.setAccessibleName('Categoria de arquivos para conferir e limpar')
        self.category.currentIndexChanged.connect(self.invalidate_cleanup); body.addWidget(self.category)
        self.cleanup_text = QPlainTextEdit(); self.cleanup_text.setReadOnly(True); body.addWidget(self.cleanup_text, 1)
        self.closed_apps = QCheckBox('Fechei os aplicativos que podem estar usando estes arquivos.'); body.addWidget(self.closed_apps)
        self.scan_cleanup = self.button(body, 'Conferir itens para limpeza', 'document-preview', self.preview_cleanup)
        self.apply_cleanup = self.button(body, 'Limpar os itens conferidos…', 'edit-clear', self.run_cleanup); self.apply_cleanup.setEnabled(False)
        self.cancel_cleanup = self.button(body, 'Cancelar limpeza', 'process-stop', self.stop_cleanup); self.cancel_cleanup.setEnabled(False)

    def invalidate_cleanup(self, *_):
        self.cleanup_generation += 1
        self.cleanup_plan = None
        if hasattr(self, 'apply_cleanup'): self.apply_cleanup.setEnabled(False)
        if hasattr(self, 'cleanup_text'): self.cleanup_text.setPlainText('Confira os itens da categoria selecionada antes de limpar.')

    def preview_cleanup(self):
        if self.cleanup_job: return
        category = self.category.currentData(); self.invalidate_cleanup()
        generation = self.cleanup_generation
        self.category.setEnabled(False); self.cancel_cleanup.setEnabled(True)
        self.cleanup_text.setPlainText('Conferindo os itens para limpeza…')
        def done(plan):
            if generation != self.cleanup_generation or category != self.category.currentData(): return
            self.cleanup_plan = plan
            lines = [f"{len(plan['entries'])} itens conferidos · {size_text(plan['bytes'])} em arquivos elegíveis.",
                     'Pasta: ' + plan['root'], f"{plan['skipped']} itens recentes, protegidos ou não elegíveis preservados."]
            lines += ['/'.join(item['parts']) for item in plan['entries'][:1000]]
            if len(plan['entries']) > 1000: lines.append('A prévia exibe os primeiros 1.000 itens.')
            if plan['errors']: lines += ['Erros de leitura:'] + plan['errors'][:20]
            self.cleanup_text.setPlainText('\n'.join(lines)); self.apply_cleanup.setEnabled(bool(plan['entries']))
        def finished():
            if self.cleanup_job is job:
                self.cleanup_job = None; self.category.setEnabled(True); self.cancel_cleanup.setEnabled(False)
        def cancelled():
            if generation == self.cleanup_generation:
                self.cleanup_plan = None; self.apply_cleanup.setEnabled(False)
                self.cleanup_text.setPlainText('Conferência cancelada. Nenhum item foi removido.')
        job = self.start_job(lambda cancel, progress: scan(category, cancel, progress), done,
                             self.scan_cleanup, on_finished=finished, on_cancelled=cancelled)
        self.cleanup_job = job

    def run_cleanup(self):
        if not self.cleanup_plan or self.cleanup_job: return
        if self.cleanup_plan['category'] != self.category.currentData():
            self.invalidate_cleanup(); return
        if not self.closed_apps.isChecked():
            QMessageBox.information(self, 'Feche os aplicativos', 'Feche os aplicativos em uso e marque a confirmação antes de limpar.'); return
        if QMessageBox.question(self, 'Confirmar limpeza',
                'Remover definitivamente os itens conferidos? Itens alterados depois da conferência serão preservados.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        plan = self.cleanup_plan; self.apply_cleanup.setEnabled(False); self.scan_cleanup.setEnabled(False); self.category.setEnabled(False)
        self.cancel_cleanup.setEnabled(True)
        def done(result):
            lines = [('Limpeza cancelada.' if result['cancelled'] else 'Limpeza concluída.'),
                     f"{result['removed']} itens removidos, {result['changed_or_retained']} alterados ou preservados e {len(result['errors'])} erros."]
            if result.get('preserved'):
                lines.append('Itens preservados para conferência:')
                for item in result['preserved'][:100]:
                    lines.append(str(item))
            lines += result.get('limitations', [])
            lines += result['errors'][:20]
            self.cleanup_text.setPlainText('\n'.join(lines))
            self.cleanup_plan = None
        def finished():
            if self.cleanup_job is job:
                self.cleanup_job = None; self.scan_cleanup.setEnabled(True); self.category.setEnabled(True); self.cancel_cleanup.setEnabled(False)
        job = self.start_job(lambda cancel, progress: clean(plan, cancel, progress), done,
                             on_finished=finished, deliver_cancelled=True)
        self.cleanup_job = job

    def stop_cleanup(self):
        if self.cleanup_job: self.cleanup_job.cancel.set()


class MaintenanceWindow(QMainWindow):
    def __init__(self, section):
        super().__init__(); self.page = MaintenancePage(section); self.setCentralWidget(self.page)
        self.setWindowTitle('Cuidados com o computador — Linux BR'); self.setWindowIcon(QIcon.fromTheme('security-high'))
        self.resize(940, 680); self.setStyleSheet(BUTTONS)
    def closeEvent(self, event):
        if self.page.jobs:
            for job in self.page.jobs: job.cancel.set()
            event.ignore()
        else: event.accept()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--section', choices=['protection', 'diagnostics', 'storage'], default='protection')
    args = parser.parse_args(); app = QApplication(sys.argv); app.setDesktopFileName('linuxbr-maintenance')
    window = MaintenanceWindow(args.section); window.show(); return app.exec()


if __name__ == '__main__': sys.exit(main())
