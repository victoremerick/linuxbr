"""Review the organization profile before preparing account preferences."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys

from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QHeaderView, QHBoxLayout, QLabel, QMainWindow,
                            QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from keyboard_controls import SettingsButton
from organization_policy import MACHINE_RULES, apply_preferences, validate
from visual_style import BUTTONS


RULE_NAMES = {'work-folder': 'Pasta de trabalho', 'store-search': 'Aplicativos sugeridos',
              'store-snap': 'Snap Store na Loja', 'store-brew': 'Homebrew na Loja'}
MACHINE_HELPER = '/usr/lib/linuxbr-system/organization_machine_policy.py'


def rule_value(value):
    if type(value) is bool:
        return 'Permitido' if value else 'Bloqueado'
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(term, str) for term in value):
        return ', '.join(value)
    return json.dumps(value, ensure_ascii=False)


class Preparation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Preparar para trabalho ou escola — Linux BR')
        self.setWindowIcon(QIcon.fromTheme('network-server'))
        self.resize(850, 560)
        self.setStyleSheet(BUTTONS)
        self.profile = None
        self.machine = {}
        self.process = None
        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        title = QLabel('Preparar para trabalho ou escola')
        title.setStyleSheet('font-size:24px;font-weight:600')
        layout.addWidget(title)
        note = QLabel('Entre com sua conta da organização. A TI cadastra o serviço deste equipamento. '
                      'Consulte o perfil para conferir os controles da máquina e preparar sua conta.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.status = QLabel('Perfil ainda não consultado.')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Etapa', 'Configuração', 'Estado'])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setAccessibleName('Etapas do perfil da organização')
        layout.addWidget(self.table, 1)
        self.fetch = SettingsButton('Consultar perfil da organização')
        self.fetch.setIcon(QIcon.fromTheme('view-refresh'))
        self.fetch.clicked.connect(self.refresh)
        layout.addWidget(self.fetch)
        controls = QHBoxLayout()
        self.configure_machine = SettingsButton('Aplicar controles da Loja…')
        self.configure_machine.setIcon(QIcon.fromTheme('security-high'))
        self.configure_machine.clicked.connect(self.preview_machine)
        controls.addWidget(self.configure_machine)
        self.restore_machine = SettingsButton('Reverter controles da Loja…')
        self.restore_machine.setIcon(QIcon.fromTheme('edit-undo'))
        self.restore_machine.clicked.connect(self.revert_machine)
        controls.addWidget(self.restore_machine)
        layout.addLayout(controls)
        self.apply = SettingsButton('Preparar minha conta')
        self.apply.setIcon(QIcon.fromTheme('dialog-ok-apply'))
        self.apply.clicked.connect(self.prepare)
        layout.addWidget(self.apply)
        self.apps = SettingsButton('Consultar aplicativos sugeridos')
        self.apps.setIcon(QIcon.fromTheme('system-software-install'))
        self.apps.clicked.connect(self.open_apps)
        layout.addWidget(self.apps)
        self.update_actions()
        self.state = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'linuxbr/organization.json'
        try:
            previous = json.loads(self.state.read_text(encoding='utf-8'))
            if isinstance(previous.get('revision'), str):
                self.status.setText('Última revisão preparada nesta conta · ' + previous['revision']
                                    + '\nConsulte o serviço para conferir o perfil atual.')
        except (OSError, ValueError, AttributeError):
            pass

    def refresh(self):
        if self.process:
            return
        self.profile = None
        self.machine = {}
        self.table.setRowCount(0)
        self.run_helper('/usr/lib/linuxbr-system/organization_policy.py', [],
                        'Consultando a organização…', self.loaded)

    def update_actions(self):
        idle = self.process is None
        rules = (self.profile or {}).get('rules', [])
        self.fetch.setEnabled(idle)
        self.apply.setEnabled(idle and self.profile is not None)
        self.configure_machine.setEnabled(idle and self.profile is not None)
        self.restore_machine.setEnabled(idle)
        self.apps.setEnabled(idle and any(rule['id'] == 'store-search' for rule in rules))

    def run_helper(self, helper, arguments, message, finished):
        if self.process:
            return
        process = self.process = QProcess(self)
        self.update_actions()
        self.status.setText(message)

        def complete(code):
            if self.process is not process:
                return
            self.process = None
            try:
                if code:
                    error = bytes(process.readAllStandardError()).decode('utf-8', 'replace').strip()
                    raise ValueError(error[:600] or 'A operação não foi concluída. Confira a autorização local.')
                finished(json.loads(bytes(process.readAllStandardOutput())))
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.status.setText(str(error) or 'A resposta do serviço é inválida.')
            finally:
                self.update_actions()
                process.deleteLater()

        process.finished.connect(lambda code, *_: complete(code))
        process.errorOccurred.connect(lambda error: complete(1)
                                      if error == QProcess.ProcessError.FailedToStart else None)
        process.start('/usr/bin/pkexec', [helper, *arguments])

    def loaded(self, profile):
        validate(profile, profile, profile['nonce'], datetime.now(timezone.utc))
        self.profile = profile
        self.status.setText('Organização · ' + profile['organization'] + '\nRevisão · ' + profile['revision'])
        self.table.setRowCount(len(profile['rules']))
        for row, rule in enumerate(profile['rules']):
            state = 'Controle obrigatório pendente' if rule['required'] else 'Aguardando'
            for column, value in enumerate((RULE_NAMES.get(rule['id'], rule['id']),
                                            rule_value(rule['value']), state)):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        self.table.resizeRowsToContents()

    def preview_machine(self):
        self.run_helper(MACHINE_HELPER, ['preview'], 'Conferindo os controles da Loja…', self.review_machine)

    def review_machine(self, preview):
        from organization_machine_policy import fingerprint
        if self.profile is None or fingerprint(self.profile) != preview['rules_sha256']:
            self.status.setText('O perfil mudou no servidor. Consulte a organização novamente antes de aplicar.')
            return
        if not preview['can_apply']:
            pending = [RULE_NAMES.get(name, name) for name in preview['unsupported'] + preview['conflicts']]
            if preview['profile_conflict']:
                pending.append('identidade ou revisão divergente')
            self.status.setText('Controles pendentes · ' + ', '.join(pending))
            return
        changes = [f"{RULE_NAMES.get(row['id'], row['id'])} · {rule_value(row['to'])}"
                   for row in preview['changes']]
        body = '\n'.join([f"Organização · {preview['organization']}", f"Revisão · {preview['revision']}",
                          *changes, '', 'Aplicar esta revisão às fontes da Loja deste computador?'])
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle('Aplicar controles da Loja')
        confirmation.setTextFormat(Qt.TextFormat.PlainText)
        confirmation.setText(body)
        confirmation.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirmation.exec() == QMessageBox.StandardButton.Yes:
            self.run_helper(MACHINE_HELPER, ['apply', preview['revision'], preview['rules_sha256']],
                            'Aplicando controles da Loja…', self.machine_done)
        else:
            self.status.setText('Aplicação dos controles cancelada.')

    def machine_done(self, state):
        self.machine = state
        conflicts = state['conflicts']
        if conflicts:
            self.status.setText('Há alterações locais pendentes de revisão · ' + ', '.join(conflicts))
        elif state['revision']:
            self.status.setText('Controles da Loja conferidos · ' + state['revision'])
        else:
            self.status.setText('Controles da organização revertidos na Loja.')
        for row, rule in enumerate((self.profile or {}).get('rules', [])):
            if rule['required'] and rule['id'] in MACHINE_RULES:
                managed = self.completed_machine().get(rule['id']) is rule['value']
                self.table.setItem(row, 2, QTableWidgetItem('Gerenciado pela organização' if managed
                                                         else 'Controle obrigatório pendente'))

    def completed_machine(self):
        if not self.profile or not self.machine or self.machine['conflicts']:
            return {}
        from organization_machine_policy import fingerprint
        from store_optional import POLICY, read_flags
        if (self.machine['revision'], self.machine['organization'], self.machine['rules_sha256']) != (
                self.profile['revision'], self.profile['organization'], fingerprint(self.profile)):
            return {}
        try:
            info = POLICY.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                return {}
            flags = read_flags(POLICY)
            return {name: value for name, value in self.machine['managed'].items()
                    if flags.get(name.removeprefix('store-')) is value}
        except (OSError, ValueError):
            return {}

    def revert_machine(self):
        if QMessageBox.question(self, 'Reverter controles da Loja',
                'Restaurar as permissões de fontes da Loja anteriores aos controles desta organização?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            self.run_helper(MACHINE_HELPER, ['restore'], 'Revertendo controles da Loja…', self.machine_done)

    def prepare(self):
        if not self.profile:
            return
        try:
            results = apply_preferences(self.profile, Path.home(), self.state,
                                        completed_machine=self.completed_machine())
            for row, result in enumerate(results):
                self.table.setItem(row, 2, QTableWidgetItem(result['state']))
            self.status.setText('Preferências preparadas nesta conta. Confira os aplicativos sugeridos e as etapas pendentes.')
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Preparação pendente', str(error))

    def open_apps(self):
        from PyQt6.QtWidgets import QInputDialog
        from recovery import launch
        terms = [term for rule in (self.profile or {}).get('rules', [])
                 if rule['id'] == 'store-search' for term in rule['value']]
        if terms:
            selected, accepted = QInputDialog.getItem(self, 'Aplicativos da organização',
                'Escolha uma sugestão para conferir na Loja.', terms, editable=False)
            if accepted:
                launch(self, ['linuxbr-store', '--search', selected])

    def closeEvent(self, event):
        if self.process:
            event.ignore()
            return
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Preparation()
    window.show()
    sys.exit(app.exec())
