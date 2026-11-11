"""Interactive import of selected personal folders."""
import os
from pathlib import Path
import sys
import threading

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QInputDialog, QLineEdit, QListWidget, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView)
from migration_backend import Cancelled, prepare, save_report, transfer
from visual_style import BUTTONS
from keyboard_controls import SettingsButton


def size_text(value):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB': return f'{value:.1f} {unit}'
        value /= 1024


class Worker(QThread):
    progress = pyqtSignal(dict)
    result = pyqtSignal(object)
    failure = pyqtSignal(str)

    def __init__(self, function):
        super().__init__(); self.function = function; self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.function(self.cancel, self.progress.emit))
        except Cancelled:
            self.failure.emit('Conferência cancelada. Nenhum arquivo foi copiado.')
        except Exception as error:
            self.failure.emit(str(error))


class MigrationWindow(QMainWindow):
    def __init__(self,restore=False):
        super().__init__(); self.setWindowTitle('Recuperar meus arquivos — Linux BR' if restore else 'Trazer meus arquivos — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('folder-import')); self.resize(900, 650)
        self.setStyleSheet(BUTTONS); self.worker = None; self.plan = None
        root = QWidget(); self.setCentralWidget(root); body = QVBoxLayout(root)
        title = QLabel('Recuperar arquivos de uma cópia de segurança' if restore else 'Trazer meus arquivos do Windows'); title.setStyleSheet('font-size:24px;font-weight:600')
        body.addWidget(title)
        note = QLabel('Escolha pastas em um disco ou cópia de segurança. Os arquivos serão copiados e conferidos por SHA-256. '
                      'A origem é preservada; links e arquivos especiais são ignorados.')
        note.setWordWrap(True); body.addWidget(note)
        self.sources = QListWidget(); self.sources.setAccessibleName('Pastas de origem'); body.addWidget(self.sources)
        buttons = QHBoxLayout(); body.addLayout(buttons)
        self.add = SettingsButton('Adicionar pasta…'); self.add.setIcon(QIcon.fromTheme('folder-new'))
        self.add.clicked.connect(self.add_source); buttons.addWidget(self.add)
        self.remove = SettingsButton('Remover da seleção'); self.remove.setIcon(QIcon.fromTheme('list-remove'))
        self.remove.clicked.connect(self.remove_source); buttons.addWidget(self.remove); buttons.addStretch()
        row = QHBoxLayout(); body.addLayout(row)
        row.addWidget(QLabel('Destino:')); self.destination = QLineEdit(str(Path.home())); row.addWidget(self.destination, 1)
        self.destination.setAccessibleName('Pasta de destino da importação')
        self.pick = SettingsButton('Escolher…'); self.pick.setIcon(QIcon.fromTheme('folder-open'))
        self.pick.clicked.connect(self.choose_destination); row.addWidget(self.pick)
        self.destination.textChanged.connect(self.invalidate)
        row = QHBoxLayout(); body.addLayout(row); row.addWidget(QLabel('Se o nome já existir:'))
        self.policy = QComboBox(); self.policy.addItem('Manter ambos com nomes diferentes', 'keep')
        self.policy.setAccessibleName('O que fazer quando um nome já existe no destino')
        self.policy.addItem('Ignorar o arquivo da origem', 'skip'); self.policy.addItem('Substituir o arquivo do destino', 'replace')
        self.policy.currentIndexChanged.connect(self.invalidate)
        row.addWidget(self.policy, 1)
        self.preview = QTableWidget(0, 3); self.preview.setHorizontalHeaderLabels(['Pasta no destino', 'Arquivos', 'Tamanho'])
        self.preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.preview.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.preview.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        body.addWidget(self.preview)
        self.status = QLabel('Adicione as pastas e confira a importação antes de começar.')
        self.status.setTextFormat(Qt.TextFormat.PlainText); self.status.setWordWrap(True); body.addWidget(self.status)
        self.progress = QProgressBar(); self.progress.setRange(0, 1000); body.addWidget(self.progress)
        row = QHBoxLayout(); body.addLayout(row)
        self.scan = SettingsButton('Conferir importação'); self.scan.setIcon(QIcon.fromTheme('document-preview'))
        self.scan.clicked.connect(self.scan_sources); row.addWidget(self.scan)
        self.start = SettingsButton('Copiar e verificar'); self.start.setIcon(QIcon.fromTheme('edit-copy'))
        self.start.setEnabled(False); self.start.clicked.connect(self.start_copy); row.addWidget(self.start)
        self.stop = SettingsButton('Cancelar operação'); self.stop.setIcon(QIcon.fromTheme('process-stop'))
        self.stop.setEnabled(False); self.stop.clicked.connect(self.cancel); row.addWidget(self.stop)
        self.bookmarks = SettingsButton('Preparar favoritos do navegador…')
        self.bookmarks.setIcon(QIcon.fromTheme('bookmarks'))
        self.bookmarks.clicked.connect(self.prepare_bookmarks)
        self.alternatives = SettingsButton('Encontrar alternativas para programas…')
        self.alternatives.setIcon(QIcon.fromTheme('system-software-install'))
        self.alternatives.clicked.connect(self.suggest_programs)
        if not restore:
            extras = QHBoxLayout()
            extras.addWidget(self.bookmarks)
            extras.addWidget(self.alternatives)
            extras.addStretch()
            body.addLayout(extras)
        else:
            self.bookmarks.hide()
            self.alternatives.hide()
        for control in (self.add, self.remove, self.pick, self.scan, self.start, self.stop,
                        self.bookmarks, self.alternatives):
            control.setAutoDefault(False)

    def invalidate(self, *_):
        self.plan = None; self.start.setEnabled(False)

    def add_source(self):
        folder = QFileDialog.getExistingDirectory(self, 'Escolher pasta de origem', str(Path.home()))
        if folder and not self.sources.findItems(folder, Qt.MatchFlag.MatchExactly):
            self.sources.addItem(folder); self.invalidate()

    def remove_source(self):
        self.sources.takeItem(self.sources.currentRow()); self.invalidate()

    def choose_destination(self):
        folder = QFileDialog.getExistingDirectory(self, 'Escolher destino da cópia', self.destination.text())
        if folder: self.destination.setText(folder)

    def prepare_bookmarks(self):
        from migration_bookmarks import browser_file, load_bookmarks

        source, _ = QFileDialog.getOpenFileName(self, 'Escolher favoritos exportados', '', 'HTML (*.html *.htm)')
        if not source:
            return
        try:
            links = load_bookmarks(source)
            if QMessageBox.question(self, 'Preparar favoritos',
                    f'Foram encontrados {len(links)} endereços web. Salvar uma cópia para importar pelo navegador?'
                    ) != QMessageBox.StandardButton.Yes:
                return
            target, _ = QFileDialog.getSaveFileName(self, 'Salvar favoritos para importação',
                str(Path.home() / 'linuxbr-favoritos.html'), 'HTML (*.html)')
            if not target:
                return
            with Path(target).open('x', encoding='utf-8') as output:
                output.write(browser_file(links))
            QMessageBox.information(self, 'Favoritos preparados',
                'Abra o gerenciador de favoritos do navegador e escolha Importar de um arquivo HTML.')
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Favoritos não preparados', str(error))

    def suggest_programs(self):
        from PyQt6.QtCore import QProcess

        alternatives = {'word': 'LibreOffice', 'excel': 'LibreOffice', 'powerpoint': 'LibreOffice',
                        'photoshop': 'GIMP', 'winrar': 'Ark', '7-zip': 'Ark',
                        'notepad++': 'Kate', 'outlook': 'Thunderbird', 'paint': 'KolourPaint'}
        text, accepted = QInputDialog.getMultiLineText(self, 'Programas que você usa',
            'Informe um nome por linha para consultar alternativas na Loja.')
        if not accepted:
            return
        names = list(dict.fromkeys(line.strip()[:100] for line in text.splitlines()[:30] if line.strip()))
        if not names:
            return
        suggestions = {f'{name} → {alternatives.get(name.casefold(), name)}':
                       alternatives.get(name.casefold(), name) for name in names}
        selected, accepted = QInputDialog.getItem(self, 'Consultar na Loja',
            'Escolha um programa ou uma alternativa para pesquisar.', list(suggestions), editable=False)
        if accepted:
            started, _ = QProcess.startDetached('linuxbr-store', ['--search', suggestions[selected]])
            if not started:
                QMessageBox.information(self, 'Loja Linux BR',
                                        'Abra a Loja e pesquise por ' + suggestions[selected] + '.')

    def busy(self, active):
        for item in (self.add, self.remove, self.pick, self.destination, self.sources,
                     self.policy, self.scan, self.bookmarks, self.alternatives):
            item.setEnabled(not active)
        self.stop.setEnabled(active); self.start.setEnabled(not active and bool(self.plan and self.plan['enough_space']))

    def run_job(self, function, completed):
        self.busy(True); self.worker = Worker(function)
        self.worker.progress.connect(self.show_progress); self.worker.result.connect(completed)
        self.worker.failure.connect(self.show_error); self.worker.finished.connect(self.finished)
        self.worker.start()

    def scan_sources(self):
        sources = [self.sources.item(i).text() for i in range(self.sources.count())]
        target = self.destination.text(); self.invalidate(); self.status.setText('Conferindo pastas e espaço…')
        policy = self.policy.currentData()
        self.progress.setRange(0, 0)
        self.run_job(lambda cancel, progress: prepare(sources, target, cancel, progress, policy=policy), self.scanned)

    def scanned(self, plan):
        self.plan = plan; self.preview.setRowCount(len(plan['sources']))
        for row, item in enumerate(plan['sources']):
            for column, value in enumerate((item['label'], str(item['files']), size_text(item['bytes']))):
                self.preview.setItem(row, column, QTableWidgetItem(value))
        message = f"{len(plan['files'])} arquivos · {size_text(plan['bytes'])} · {size_text(plan['available'])} livres · {plan['conflicts']} nomes já existentes."
        if plan['resume_bytes']:
            message += f" {size_text(plan['resume_bytes'])} já conferidos no destino."
        if plan['skipped']: message += f" {len(plan['skipped'])} links ou arquivos especiais serão ignorados."
        if plan['errors']: message += f" {len(plan['errors'])} erros de leitura; o resultado será parcial."
        if not plan['enough_space']: message += ' Escolha um destino com mais espaço.'
        self.status.setText(message)

    def start_copy(self):
        if not self.plan: return
        if self.policy.currentData() == 'replace' and QMessageBox.question(self, 'Substituir arquivos?',
                'Arquivos com o mesmo nome serão substituídos no destino. A versão anterior será mantida em arquivo oculto, identificado no relatório. A origem será preservada. Continuar?') != QMessageBox.StandardButton.Yes:
            return
        plan = self.plan; policy = self.policy.currentData()
        self.progress.setRange(0, 1000); self.progress.setValue(0)
        self.run_job(lambda cancel, progress: transfer(plan, policy, cancel, progress), self.copied)

    def copied(self, report):
        try:
            saved = save_report(report, self.plan['destination'])
            ending = '\nRelatório salvo em: ' + saved
        except OSError as error:
            ending = '\nNão foi possível salvar o relatório: ' + str(error)
        states = {'completed': 'Importação concluída e conferida.', 'partial': 'Importação parcial; confira os erros no relatório.',
                  'cancelled': 'Importação cancelada. Os arquivos já concluídos foram mantidos.'}
        self.status.setText(states.get(report['status'], report['status']) +
                            f" {len(report['copied'])} copiados, {len(report.get('already_verified', []))} já conferidos, "
                            f"{len(report['skipped'])} ignorados e {len(report['errors'])} erros." + ending)
        self.plan = None

    def show_progress(self, info):
        if info['phase'] == 'scan':
            self.status.setText(f"Conferindo: {info['files']} arquivos · {size_text(info['bytes'])}")
        else:
            self.progress.setValue(min(1000, int(1000 * info['processed'] / max(1, info['total']))))
            self.status.setText('Copiando e verificando: ' + info['path'])

    def show_error(self, message):
        self.status.setText(message)

    def finished(self):
        self.worker.deleteLater(); self.worker = None; self.progress.setRange(0, 1000); self.busy(False)

    def cancel(self):
        if self.worker:
            self.worker.cancel.set(); self.stop.setEnabled(False)
            self.status.setText('Cancelando; aguardando a limpeza do arquivo temporário…')

    def closeEvent(self, event):
        if self.worker is not None:
            self.cancel(); event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv); app.setDesktopFileName('linuxbr-migration')
    window = MigrationWindow(restore='--restore' in sys.argv); window.show(); return app.exec()


if __name__ == '__main__': sys.exit(main())
