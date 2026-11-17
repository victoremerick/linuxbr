"""Guide the user through a live check of accessible focus events."""
import json
import os
from pathlib import Path
import sys

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

from file_tools import plain_label
from keyboard_focus import KeyboardFocus, preference, set_preference
from visual_style import BUTTONS


STEP_TEXT = (
    ('Menu Iniciar', 'Abra o Iniciar com Super. Percorra a pesquisa e os itens com Tab e as setas. '
                    'Feche o menu com Esc e confira os resultados abaixo.'),
    ('Barra de tarefas', 'Passe o foco aos ícones de aplicativos ou da bandeja no painel. '
                         'Experimente navegar com Tab ou as setas quando o painel estiver em foco.'),
    ('Campos de texto', 'Use Alt+N para ir ao campo Nome. Use Tab e Shift+Tab para mudar de controle. '
                        'O segundo campo foi deixado sem rótulo para demonstrar o alerta.'),
    ('Diálogos', 'Entre em Abrir diálogo de teste e pressione Espaço. '
                 'Alterne com Tab, confirme com Enter ou feche com Esc.'),
)
EVENT = 'object:state-changed:focused'


def is_plasma_shell(process, name):
    try:
        command = (Path('/proc') / str(int(process)) / 'comm').read_text(encoding='utf-8').strip()
    except (OSError, ValueError):
        command = ''
    return command == 'plasmashell' or name.casefold() == 'plasmashell'


def result_text(name, description):
    if not name and not description:
        return 'Revisar nome e descrição'
    if not name:
        return 'Revisar nome'
    return 'Nome e descrição disponíveis' if description else 'Nome disponível'


def demo_context(source):
    for _ in range(8):
        if source is None:
            break
        name = source.get_name()
        if name in ('Campos de teste', 'Diálogo de teste'):
            return 'fields' if name == 'Campos de teste' else 'dialog'
        source = source.get_parent()
    return ''


def observe(parent):
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GLib

    def focused(event, *_):
        if not event.detail1 or event.source is None:
            return
        source = event.source
        try:
            if source.get_role() == Atspi.Role.PASSWORD_TEXT:
                return
            application = source.get_application()
            if application is None:
                return
            pid = application.get_process_id()
            scope = demo_context(source) if pid == parent else (
                'plasma' if is_plasma_shell(pid, application.get_name() or '') else '')
            if not scope:
                return
            control = [(entry or '').strip()[:250] for entry in
                       (source.get_localized_role_name(), source.get_name(), source.get_description())]
            print(json.dumps({'scope': scope, 'control': control}), flush=True)
        except GLib.Error:
            pass  # The focused object may disappear while we query its metadata.

    Atspi.init()
    Atspi.set_timeout(650, 1200)
    listener = Atspi.EventListener.new(focused, None)
    if not listener.register(EVENT):
        return 1
    print('{"ready": true}', flush=True)
    GLib.MainLoop().run()
    return 0


class Guide(QDialog):
    def __init__(self):
        super().__init__()
        self.process = None
        self.results = [dict() for _ in STEP_TEXT]
        self.setWindowTitle('Teste do leitor de tela')
        self.setWindowIcon(QIcon.fromTheme('preferences-desktop-accessibility'))
        self.resize(790, 610)
        layout = QVBoxLayout(self)
        layout.addWidget(plain_label('Teste o que o leitor de tela pode anunciar. O diagnóstico consulta apenas o '
                                     'nome e a descrição dos controles durante o teste.'))
        bar = QHBoxLayout()
        self.start = QPushButton('Iniciar diagnóstico')
        self.start.clicked.connect(self.toggle)
        bar.addWidget(self.start)
        reader = QPushButton('Iniciar Orca')
        reader.clicked.connect(self.launch_orca)
        bar.addWidget(reader)
        bar.addStretch()
        layout.addLayout(bar)
        highlight = QCheckBox('Realçar também o foco dos controles nas Configurações do Linux BR')
        highlight.setChecked(preference().is_file())
        highlight.toggled.connect(self.prefer_highlight)
        layout.addWidget(highlight)
        self.step = QComboBox()
        self.step.setAccessibleName('Etapa do teste')
        self.step.addItems([name for name, _ in STEP_TEXT])
        self.step.currentIndexChanged.connect(self.switch)
        layout.addWidget(self.step)
        self.instructions = plain_label('')
        layout.addWidget(self.instructions)
        self.practice = QGroupBox('Campos de teste')
        practice = QFormLayout(self.practice)
        line = QLineEdit()
        line.setAccessibleName('Nome de teste')
        label = QLabel('&Nome de teste')
        label.setBuddy(line)
        practice.addRow(label, line)
        unlabeled = QWidget()
        unlabeled_layout = QHBoxLayout(unlabeled)
        unlabeled_layout.setContentsMargins(0, 0, 0, 0)
        unlabeled_layout.addWidget(QLineEdit())
        practice.addRow('', unlabeled)
        layout.addWidget(self.practice)
        self.dialog = QPushButton('Abrir diálogo de teste')
        self.dialog.clicked.connect(self.test_dialog)
        layout.addWidget(self.dialog)
        self.table = QTableWidget(0, 4)
        self.table.setAccessibleName('Controles observados na etapa atual')
        self.table.setHorizontalHeaderLabels(['Controle', 'Nome', 'Descrição', 'Resultado'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.status = plain_label('')
        layout.addWidget(self.status)
        close = QPushButton('Fechar')
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.switch(0)
        self.finished.connect(self.stop)

    def switch(self, index):
        self.instructions.setText(STEP_TEXT[index][1])
        self.practice.setVisible(index == 2)
        self.dialog.setVisible(index == 3)
        self.table.setRowCount(0)
        for row, values in enumerate(self.results[index]):
            self.append(row, values)
        self.summary()

    def summary(self):
        observed = self.results[self.step.currentIndex()]
        self.status.setText(f'{len(observed)} controle(s) observado(s). {sum(not values[1] for values in observed)} sem nome.'
                            if observed else 'Aguardando controles nesta etapa.' if self.process is not None
                            else 'Inicie o diagnóstico para observar os controles acessíveis.')

    def append(self, row, values):
        self.table.insertRow(row)
        for column, value in enumerate((*values, result_text(*values[1:]))):
            self.table.setItem(row, column, QTableWidgetItem(value or '—'))

    def toggle(self):
        if self.process is not None:
            self.stop()
            self.status.setText('Diagnóstico encerrado. Os resultados ficam nesta janela até fechar.')
            return
        process = self.process = QProcess(self)
        process.readyReadStandardOutput.connect(self.receive)
        process.finished.connect(self.exited)
        process.errorOccurred.connect(self.process_error)
        process.start('/usr/bin/python3', [str(Path(__file__).resolve()), '--observe', str(os.getpid())])
        self.start.setText('Encerrar diagnóstico')
        self.status.setText('Conectando ao serviço de acessibilidade…')

    def stop(self, *_):
        process, self.process = self.process, None
        if process is not None:
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()
        self.start.setText('Iniciar diagnóstico')

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.exited()

    def exited(self, *_):
        process = self.sender()
        if process is self.process:
            self.process = None
            self.start.setText('Iniciar diagnóstico')
            self.status.setText('O diagnóstico não conseguiu usar o serviço de acessibilidade.')
            process.deleteLater()

    def receive(self):
        process = self.sender()
        while process is self.process and process.canReadLine():
            try:
                data = json.loads(bytes(process.readLine()))
            except ValueError:
                continue
            if data.get('ready'):
                self.summary()
                continue
            step = self.step.currentIndex()
            if data.get('scope') != ('plasma', 'plasma', 'fields', 'dialog')[step]:
                continue
            row = tuple(data['control'])
            observed = self.results[step]
            if row not in observed and len(observed) < 150:
                self.append(self.table.rowCount(), row)
                observed[row] = True
                self.summary()

    def prefer_highlight(self, checked):
        try:
            set_preference(checked)
        except OSError:
            self.status.setText('Não foi possível salvar a preferência de realce do foco.')

    def launch_orca(self):
        if not QProcess.startDetached('/usr/bin/orca', [])[0]:
            self.status.setText('Não foi possível iniciar o Orca.')

    def test_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Diálogo de teste')
        layout = QVBoxLayout(dialog)
        layout.addWidget(plain_label('Escolha Confirmar ou Cancelar para praticar a navegação.'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Confirmar')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()


def main():
    app = QApplication(sys.argv)
    app.setDesktopFileName('linuxbr-screen-reader-test')
    app.setStyleSheet(BUTTONS)
    indicator = KeyboardFocus(app, enabled=True)
    Guide().exec()
    return 0


if __name__ == '__main__':
    sys.exit(observe(int(sys.argv[2])) if len(sys.argv) == 3 and sys.argv[1] == '--observe' else main())
