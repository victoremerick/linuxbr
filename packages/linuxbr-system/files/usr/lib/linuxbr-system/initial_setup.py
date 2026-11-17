"""Configuração inicial obrigatória em uma sessão gráfica dedicada."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QIODevice, QProcess, QSaveFile, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)
from desktop_jobs import Query
from desktop_theme import initialize
from initial_setup_access import ScreenKeyboard


SOCKET_PATH = '/run/linuxbr-initial-setup/control.sock'
LIMIT = 256 * 1024
STEPS = ('keyboard', 'network', 'timezone', 'account', 'apps', 'finish')
KEYBOARDS = {
    'br': ('Português (Brasil) ABNT2', 'br', 'abnt2'),
    'pt': ('Português (Portugal)', 'pt', ''),
    'us': ('Inglês (Estados Unidos)', 'us', ''),
    'us-intl': ('Inglês (Estados Unidos, internacional)', 'us', 'intl'),
    'es': ('Espanhol (América Latina)', 'latam', ''),
}
TITLES = (
    'Configure o teclado', 'Conecte-se a uma rede', 'Confirme o fuso horário',
    'Escolha sua conta', 'Selecione aplicativos', 'Confira suas escolhas',
)
CHECK_LABELS = {'keyboard': 'Teclado', 'touchpad': 'Touchpad', 'audio': 'Áudio', 'video': 'Vídeo'}


def request(operation, **data):
    args = json.dumps(dict(operation=operation, **data), ensure_ascii=False).encode() + b'\n'
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(4 if operation == 'progress' else 930)
            connection.connect(SOCKET_PATH)
            connection.sendall(args)
            with connection.makefile('rb') as stream:
                response = json.loads(stream.readline(LIMIT))
        if not isinstance(response, dict) or type(response.get('ok')) is not bool:
            raise ValueError('Resposta inválida.')
    except (OSError, ValueError):
        raise ValueError('O serviço de configuração não respondeu. Tente novamente ou reinicie para retomar.') from None
    if not response.get('ok'):
        raise ValueError(response['error'])
    return response['value']


def heading(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def field(limit=128, secret=False):
    editor = QLineEdit()
    editor.setMaxLength(limit)
    if secret:
        editor.setEchoMode(QLineEdit.EchoMode.Password)
        editor.setInputMethodHints(Qt.InputMethodHint.ImhSensitiveData | Qt.InputMethodHint.ImhNoPredictiveText)
    return editor


def button(text, callback):
    control = QPushButton(text)
    control.setMinimumHeight(44)
    control.clicked.connect(callback)
    return control


class Wizard(QWidget):
    def __init__(self, service=request):
        super().__init__()
        self.service = service
        self.job = None
        self.progress_job = None
        self.state = {}
        self.live_checks = {}
        self.step = 0
        self.first_incomplete = 0
        self.zones = []
        self.checked = []
        self.programs = []
        self.app_selection = None
        self.return_to_apps = False
        self.online = False
        self.setWindowTitle('Configuração inicial do Linux BR')
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QWidget#setup { background: #122638; color: #142433; }
            QWidget#panel { background: #f7f9fc; border-radius: 16px; color: #142433; }
            QScrollArea, QWidget#stepPage { background: #f7f9fc; color: #142433; }
            QLabel { color: #142433; }
            QLabel#step { color: #3b5267; }
            QLabel#title { font-size: 30px; font-weight: 600; }
            QLabel#error { color: #9b251e; }
            QLineEdit, QComboBox { min-height: 35px; padding-left: 8px; }
            QPushButton#primary { background: #07599e; color: white; padding: 0 22px; border-radius: 6px; }
            QPushButton#primary:disabled { background: #50687c; }
            QPushButton:focus, QComboBox:focus, QLineEdit:focus { border: 2px solid #2676be; }
        """)
        self.setObjectName('setup')
        outer = QHBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        card = QWidget()
        card.setObjectName('panel')
        card.setMaximumWidth(830)
        card.setMaximumHeight(640)
        body = QVBoxLayout(card)
        body.setContentsMargins(30, 18, 30, 18)
        body.setSpacing(10)
        outer.addStretch()
        outer.addWidget(card, 9, Qt.AlignmentFlag.AlignVCenter)
        outer.addStretch()

        self.progress = heading('Conectando ao serviço de configuração…')
        self.progress.setObjectName('step')
        body.addWidget(self.progress)
        self.title = heading('Configuração inicial')
        self.title.setObjectName('title')
        body.addWidget(self.title)
        self.pages = QStackedWidget()
        self.pages.setMinimumHeight(190)
        body.addWidget(self.pages, 1)
        self.make_keyboard()
        self.make_network()
        self.make_timezone()
        self.make_account()
        self.make_apps()
        self.make_summary()
        accessibility = QHBoxLayout()
        self.reader = QPushButton(QIcon.fromTheme('preferences-desktop-accessibility'), 'Leitor de tela')
        self.reader.setCheckable(True)
        self.reader.toggled.connect(self.toggle_reader)
        accessibility.addWidget(self.reader)
        self.virtual_keyboard = QPushButton(QIcon.fromTheme('input-keyboard'), 'Teclado na tela')
        self.virtual_keyboard.setCheckable(True)
        accessibility.addWidget(self.virtual_keyboard)
        accessibility.addStretch()
        self.import_profile = button('Importar predefinições…', self.load_profile)
        self.export_profile = button('Exportar predefinições…', self.save_profile)
        accessibility.addWidget(self.import_profile)
        accessibility.addWidget(self.export_profile)
        self.import_profile.hide()
        self.export_profile.hide()
        body.addLayout(accessibility)
        self.screen_keyboard = ScreenKeyboard(self.pages)
        self.screen_keyboard.hide()
        self.virtual_keyboard.toggled.connect(self.screen_keyboard.setVisible)
        body.addWidget(self.screen_keyboard)
        self.speech = QProcess(self)
        self.speech.errorOccurred.connect(self.reader_failed)
        self.speech.finished.connect(self.reader_stopped)
        self.error = heading('')
        self.error.setObjectName('error')
        self.error.setAccessibleName('Estado da configuração')
        body.addWidget(self.error)
        self.indicator = QProgressBar()
        self.indicator.setRange(0, 0)
        self.indicator.setAccessibleName('Operação em andamento')
        self.indicator.hide()
        body.addWidget(self.indicator)
        self.update_progress = QTimer(self)
        self.update_progress.setInterval(650)
        self.update_progress.timeout.connect(self.poll_apps)

        controls = QHBoxLayout()
        self.restart = button('Reiniciar…', self.confirm_restart)
        controls.addWidget(self.restart)
        controls.addStretch()
        self.back = button('Voltar', self.previous)
        controls.addWidget(self.back)
        self.next = button('Avançar', self.advance)
        self.next.setObjectName('primary')
        controls.addWidget(self.next)
        body.addLayout(controls)
        QShortcut(QKeySequence('Alt+Left'), self, activated=self.previous)
        self.load()

    def closeEvent(self, event):
        event.ignore()

    def toggle_reader(self, active):
        if active:
            self.speech.start('/usr/bin/orca', ['--replace'])
        elif self.speech.state() != QProcess.ProcessState.NotRunning:
            self.speech.terminate()

    def reader_failed(self, _):
        if self.reader.isChecked():
            self.reader.setChecked(False)
            self.error.setText('Não foi possível iniciar o leitor de tela.')

    def reader_stopped(self, *_):
        self.reader_failed(None)

    def load_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Importar predefinições', '/media',
                                             'Predefinições do Linux BR (*.json)')
        if not path:
            return
        try:
            with Path(path).open('rb') as file:
                document = file.read(65537)
            if len(document) > 65536:
                raise ValueError()
            profile = json.loads(document.decode('utf-8-sig'))
        except (OSError, ValueError):
            self.error.setText('Não foi possível ler as predefinições. Selecione um arquivo JSON de até 64 KiB.')
            return
        self.run('profile', self.profile_loaded, value=profile)

    def profile_loaded(self, value):
        self.resume(value)
        self.error.setText('Predefinições carregadas. Confirme as escolhas durante o assistente.')

    def save_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar predefinições',
                                             '/media/linuxbr-predefinicoes.json',
                                             'Predefinições do Linux BR (*.json)')
        if not path:
            return
        if not path.lower().endswith('.json'):
            path += '.json'
        value = dict(schema=1, language='pt_BR', edition='desktop', keyboard=self.state['keyboard'],
                     timezone=self.state['timezone'], apps=self.state['apps'])
        file = QSaveFile(path)
        payload = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
        if not file.open(QIODevice.OpenModeFlag.WriteOnly) or file.write(payload) != len(payload) or not file.commit():
            file.cancelWriting()
            self.error.setText('Não foi possível salvar o arquivo. Escolha outro destino com permissão de gravação.')
            return
        self.error.setText('Predefinições salvas no destino escolhido.')

    def page(self):
        scroll = QScrollArea()
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget = QWidget()
        widget.setObjectName('stepPage')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 8, 0)
        layout.setSpacing(12)
        scroll.setWidget(widget)
        self.pages.addWidget(scroll)
        return layout

    def make_keyboard(self):
        page = self.page()
        page.addWidget(heading('A escolha será usada agora e na tela de login. Digite no campo de teste para conferir.'))
        form = QFormLayout()
        self.layout_choice = QComboBox()
        for key, label in KEYBOARDS.items():
            self.layout_choice.addItem(label[0], key)
        self.layout_choice.currentIndexChanged.connect(self.preview_keyboard)
        self.keyboard_test = field()
        form.addRow('&Layout do teclado', self.layout_choice)
        form.addRow('&Teste do teclado', self.keyboard_test)
        page.addLayout(form)
        page.addStretch()

    def make_network(self):
        page = self.page()
        page.addWidget(heading('Conecte um cabo Ethernet ou escolha uma rede Wi-Fi. A conta local e a configuração de fuso funcionam sem internet.'))
        row = QHBoxLayout()
        self.networks = QComboBox()
        self.networks.setAccessibleName('Rede Wi-Fi')
        row.addWidget(self.networks, 1)
        self.scan = button('Atualizar redes', self.reload_network)
        row.addWidget(self.scan)
        page.addLayout(row)
        form = QFormLayout()
        self.wifi_password = field(secret=True)
        form.addRow('&Senha do Wi-Fi', self.wifi_password)
        page.addLayout(form)
        self.networks.currentIndexChanged.connect(self.update_wifi)
        self.connect_wifi = button('Conectar Wi-Fi', self.connect_selected)
        page.addWidget(self.connect_wifi)
        self.network_status = heading('')
        page.addWidget(self.network_status)
        page.addStretch()

    def make_timezone(self):
        page = self.page()
        self.time_status = heading('Você pode escolher o fuso por cidade ou região.')
        page.addWidget(self.time_status)
        form = QFormLayout()
        self.timezone = QComboBox()
        self.timezone.setEditable(True)
        self.timezone.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.timezone.setMaxVisibleItems(12)
        form.addRow('&Fuso horário', self.timezone)
        page.addLayout(form)
        page.addStretch()

    def make_account(self):
        page = self.page()
        self.account_type = QComboBox()
        self.account_type.addItem('Criar conta local', 'local')
        self.account_type.addItem('Entrar com Active Directory', 'ad')
        self.account_type.addItem('Entrar com LDAP protegido por TLS', 'ldap')
        selector = QFormLayout()
        selector.addRow('&Tipo de conta', self.account_type)
        page.addLayout(selector)
        self.account_forms = QStackedWidget()
        self.account_type.currentIndexChanged.connect(self.account_forms.setCurrentIndex)
        page.addWidget(self.account_forms)

        local = QWidget()
        local_form = QFormLayout(local)
        self.display_name = field()
        self.username = field(32)
        self.local_password = field(secret=True)
        self.local_confirmation = field(secret=True)
        local_form.addRow('Nome &completo', self.display_name)
        local_form.addRow('&Usuário', self.username)
        local_form.addRow('&Senha', self.local_password)
        local_form.addRow('C&onfirme a senha', self.local_confirmation)
        self.account_forms.addWidget(local)

        enterprise = QWidget()
        enterprise_form = QFormLayout(enterprise)
        self.domain = field(253)
        self.ad_admin = field(253)
        self.ad_admin_password = field(secret=True)
        self.ad_user = field(253)
        self.ad_user_password = field(secret=True)
        enterprise_form.addRow(heading('Active Directory. Use as credenciais autorizadas para ingressar no domínio e a conta que usará para entrar.'))
        enterprise_form.addRow('&Domínio DNS', self.domain)
        enterprise_form.addRow('Conta de &ingresso', self.ad_admin)
        enterprise_form.addRow('Senha de in&gresso', self.ad_admin_password)
        enterprise_form.addRow('Conta de &trabalho', self.ad_user)
        enterprise_form.addRow('Senha da conta de &trabalho', self.ad_user_password)
        self.account_forms.addWidget(enterprise)
        directory = QWidget()
        ldap = QFormLayout(directory)
        self.ldap_host = field(253)
        self.ldap_base = field(384)
        self.ldap_user = field(64)
        self.ldap_password = field(secret=True)
        ldap.addRow(heading('Informe o servidor LDAPS e a base de um diretório POSIX que permite consultar os usuários. O certificado deve ser confiável pelo sistema.'))
        ldap.addRow('&Servidor LDAPS', self.ldap_host)
        ldap.addRow('&Base da busca', self.ldap_base)
        ldap.addRow('&Conta de trabalho', self.ldap_user)
        ldap.addRow('&Senha da conta de trabalho', self.ldap_password)
        self.account_forms.addWidget(directory)
        self.account_status = heading('')
        page.addWidget(self.account_status)
        page.addStretch()

    def make_apps(self):
        page = self.page()
        self.apps_status = heading('')
        page.addWidget(self.apps_status)
        self.app_category = QComboBox()
        self.app_category.setAccessibleName('Categoria de aplicativos')
        self.app_category.currentIndexChanged.connect(self.filter_apps)
        page.addWidget(self.app_category)
        self.apps = QVBoxLayout()
        page.addLayout(self.apps)
        controls = QHBoxLayout()
        controls.addWidget(button('Atualizar catálogo', self.reload_catalog))
        controls.addWidget(button('Rever conexão', self.review_network))
        controls.addStretch()
        page.addLayout(controls)
        self.without_apps = button('Continuar sem instalar mais aplicativos', lambda: self.save_step(items=[]))
        page.addWidget(self.without_apps, alignment=Qt.AlignmentFlag.AlignLeft)
        page.addStretch()

    def make_summary(self):
        page = self.page()
        self.summary = heading('')
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        page.addWidget(self.summary)
        page.addStretch()

    def load(self):
        self.run('state', self.resume)

    def resume(self, value):
        self.state = value['state']
        self.live_checks = value.get('live_checks', {})
        self.first_incomplete = value['next']
        self.show_step(self.first_incomplete)

    def focus_step(self):
        widgets = (self.layout_choice, self.scan, self.timezone, self.account_type, self.app_category, self.next)
        widgets[self.step].setFocus()

    def show_step(self, step):
        self.step = step
        self.pages.setCurrentIndex(step)
        self.error.clear()
        self.title.setText(TITLES[step])
        self.progress.setText(f'Configuração inicial do Linux BR  •  {step + 1} de {len(STEPS)}')
        self.next.setText('Concluir' if step == len(STEPS) - 1 else 'Avançar')
        self.import_profile.setVisible(step == 0 and self.first_incomplete == 0)
        self.export_profile.setVisible(step == 5)
        self.update_controls()
        self.focus_step()
        if step == 0:
            preferred = self.state.get('keyboard') or self.state.get('profile', {}).get('keyboard', 'br')
            self.layout_choice.setCurrentIndex(max(0, self.layout_choice.findData(preferred)))
            self.preview_keyboard()
        elif step == 1:
            self.reload_network()
        elif step == 2:
            self.run('timezones', self.load_timezones)
        elif step == 3:
            selected = self.state.get('account')
            draft = self.state.get('draft')
            ldap = self.state.get('ldap_draft')
            if selected:
                self.account_type.setCurrentIndex(self.account_type.findData(selected['mode']))
                self.account_status.setText(f"Conta verificada e pronta para entrar  {selected['login']}.")
            elif draft:
                self.username.setText(draft['username'])
                self.display_name.setText(draft['display'])
                self.account_status.setText('Informe novamente a senha para concluir a criação da conta iniciada.')
            elif ldap:
                self.account_type.setCurrentIndex(self.account_type.findData('ldap'))
                self.ldap_host.setText(ldap['host'])
                self.ldap_base.setText(ldap['base'])
                self.ldap_user.setText(ldap['username'])
                self.account_status.setText('Informe novamente a senha para concluir a configuração do diretório.')
            self.account_type.setEnabled(not (selected or draft or ldap))
            self.account_forms.setEnabled(not selected)
        elif step == 4:
            self.reload_catalog()
        elif step == 5:
            zone = self.state['timezone'].replace('_', ' ')
            layout = KEYBOARDS[self.state['keyboard']][0]
            labels = {row['id']: row['name'] for row in self.programs}
            apps = ', '.join(labels.get(item, item) for item in self.state['apps']) or 'Nenhuma seleção'
            checks = '  •  '.join(
                f'{CHECK_LABELS[key]} {("verificado" if result else "registrado com falha") if result is not None else "a conferir"}'
                for key, result in self.live_checks.items()
            )
            review = f'\n\nVerificações durante a instalação\n{checks}' if checks else ''
            self.summary.setText(f"Teclado  {layout}\n\nFuso horário  {zone}\n\n"
                                 f"Conta  {self.state['account']['login']}\n\nAplicativos  {apps}{review}\n\n"
                                 "Selecione Concluir e entre com a conta escolhida na tela de login.")

    def update_controls(self):
        idle = self.job is None
        self.back.setEnabled(idle and self.step > 0)
        self.next.setEnabled(idle and bool(self.state))
        self.restart.setEnabled(idle)
        self.import_profile.setEnabled(idle)
        self.export_profile.setEnabled(idle)
        self.pages.setEnabled(idle)
        self.indicator.setVisible(not idle)

    def run(self, operation, callback, **args):
        if self.job:
            return
        self.error.clear()
        job = Query(lambda: self.service(operation, **args), self)
        self.job = job
        self.update_controls()
        if operation == 'apps' and args.get('items'):
            self.update_progress.start()
        job.result.connect(lambda value: self.finished(job, callback, value))
        job.failed.connect(lambda error: self.failed(job, operation, error))
        job.finished.connect(job.deleteLater)
        job.start()

    def finished(self, job, callback, value):
        if self.job is job:
            self.job = None
            self.clear_progress()
            self.update_controls()
            callback(value)

    def failed(self, job, operation, error):
        if self.job is job:
            self.job = None
            self.clear_progress()
            self.update_controls()
            if operation == 'state':
                self.next.setEnabled(True)
                self.next.setText('Tentar novamente')
            elif operation == 'account':
                self.run('state', lambda value: self.account_retry(value, error))
                return
            self.error.setText(error or 'Não foi possível concluir a operação. Tente novamente.')

    def account_retry(self, value, error):
        self.state = value['state']
        self.first_incomplete = value['next']
        self.show_step(3)
        self.error.setText(error or 'Não foi possível criar a conta.')

    def clear_progress(self):
        self.update_progress.stop()
        self.indicator.setRange(0, 0)
        self.indicator.setFormat('%p%')

    def poll_apps(self):
        if self.progress_job:
            return
        job = Query(lambda: self.service('progress'), self)
        self.progress_job = job
        job.result.connect(self.app_progress)
        job.finished.connect(lambda: setattr(self, 'progress_job', None))
        job.finished.connect(job.deleteLater)
        job.start()

    def app_progress(self, status):
        if not status or not self.update_progress.isActive():
            return
        names = {row['id']: row['name'] for row in self.programs}
        name = names.get(status['app'], status['app'])
        self.indicator.setRange(0, status['total'])
        self.indicator.setValue(status['done'])
        self.indicator.setFormat(f"Instalando {name}  {status['done'] + 1} de {status['total']}")

    def preview_keyboard(self):
        selection = self.layout_choice.currentData()
        _, layout, variant = KEYBOARDS[selection]
        self.screen_keyboard.set_layout(selection)
        try:
            subprocess.run(['/usr/bin/setxkbmap', '-layout', layout, '-variant', variant],
                           capture_output=True, timeout=4, check=True)
        except (OSError, subprocess.SubprocessError):
            self.error.setText('Não foi possível aplicar o teclado nesta tela.')

    def reload_network(self):
        self.run('networks', self.load_networks)

    def load_networks(self, result):
        self.online = result['internet']
        self.networks.clear()
        self.networks.addItem('Selecione uma rede Wi-Fi', None)
        for network in result['wifi']:
            security = 'Wi-Fi protegido' if network['key'] else 'Wi-Fi aberto'
            self.networks.addItem(f"{network['name']}  •  {security}  •  {network['strength']}%", network)
        self.network_status.setText(result['status'])
        self.update_wifi()

    def update_wifi(self):
        selection = self.networks.currentData()
        self.connect_wifi.setEnabled(bool(selection))
        self.wifi_password.setEnabled(bool(selection and selection['key']))
        self.wifi_password.clear()

    def connect_selected(self):
        selection = self.networks.currentData()
        if selection:
            password = self.wifi_password.text()
            self.wifi_password.clear()
            self.run('wifi', self.load_networks, device=selection['device'], access_point=selection['path'], password=password)

    def load_timezones(self, result):
        self.zones = result['zones']
        self.timezone.clear()
        self.timezone.addItems(self.zones)
        preferred = self.state.get('timezone') or self.state.get('profile', {}).get('timezone') or result['suggested']
        if preferred:
            self.timezone.setCurrentIndex(self.timezone.findText(preferred))
        else:
            self.timezone.setCurrentIndex(-1)
        self.time_status.setText(f"Fuso sugerido pela internet  {result['suggested']}. Confirme ou escolha outro."
                                 if result['suggested'] else 'Digite uma região ou cidade e selecione o fuso correspondente.')

    def load_apps(self, result):
        self.programs = result['apps']
        self.apps_status.setText('Escolha os aplicativos encontrados na Loja para instalar pela fonte APT.'
                                 if self.programs else 'O catálogo de instalação está indisponível nesta conexão. Você poderá usar a Loja depois.')
        self.app_category.clear()
        self.app_category.addItem('Todas as categorias', '')
        for category in sorted({row['category'] for row in self.programs}):
            self.app_category.addItem(category, category)
        if self.checked:
            self.app_selection = {row['id'] for control, row in self.checked if control.isChecked()}
        for control, _ in self.checked:
            self.apps.removeWidget(control)
            control.deleteLater()
        self.checked.clear()
        preselected = self.app_selection
        if preselected is None:
            preselected = self.state.get('requested_apps', self.state.get('profile', {}).get('apps', []))
        for row in self.programs:
            control = QCheckBox(f"{row['name']}  •  Debian / APT")
            control.setChecked(row['id'] in preselected)
            self.apps.addWidget(control)
            self.checked.append((control, row))
        self.app_category.setEnabled(bool(self.programs))

    def filter_apps(self):
        category = self.app_category.currentData()
        for control, row in self.checked:
            control.setVisible(not category or category == row['category'])

    def reload_catalog(self):
        self.run('catalog', self.load_apps)

    def review_network(self):
        self.return_to_apps = True
        self.show_step(1)

    def previous(self):
        if self.job is None and self.step:
            if self.step == 1:
                self.return_to_apps = False
            self.show_step(self.step - 1)

    def advance(self):
        if not self.state:
            self.load()
            return
        if self.step == 0:
            self.save_step(layout=self.layout_choice.currentData())
        elif self.step == 1:
            self.save_step()
        elif self.step == 2:
            self.save_step(zone=self.timezone.currentText())
        elif self.step == 3:
            if self.state.get('account'):
                self.show_step(4)
            elif self.account_type.currentData() == 'local':
                if self.local_password.text() != self.local_confirmation.text():
                    self.error.setText('As duas senhas precisam ser iguais.')
                    self.local_confirmation.setFocus()
                    return
                password = self.local_password.text()
                self.local_password.clear()
                self.local_confirmation.clear()
                self.save_step(mode='local', display=self.display_name.text(), username=self.username.text(), password=password)
            elif self.account_type.currentData() == 'ad':
                password = self.ad_admin_password.text()
                user_password = self.ad_user_password.text()
                self.ad_admin_password.clear()
                self.ad_user_password.clear()
                self.save_step(mode='ad', domain=self.domain.text(), admin=self.ad_admin.text(), password=password,
                               login=self.ad_user.text(), user_password=user_password)
            else:
                password = self.ldap_password.text()
                self.ldap_password.clear()
                self.save_step(mode='ldap', host=self.ldap_host.text(), base=self.ldap_base.text(),
                               login=self.ldap_user.text(), user_password=password)
        elif self.step == 4:
            self.save_step(items=[row['id'] for control, row in self.checked if control.isChecked()])
        else:
            self.run('finish', lambda _: self.title.setText('Abrindo a tela de login…'))

    def save_step(self, **data):
        def success(value):
            self.state = value['state']
            self.first_incomplete = value['next']
            next_step = 4 if self.step == 1 and self.return_to_apps else self.step + 1
            if self.step == 1:
                self.return_to_apps = False
            self.show_step(min(next_step, self.first_incomplete))
        self.run(STEPS[self.step], success, **data)

    def confirm_restart(self):
        if QMessageBox.question(self, 'Reiniciar o computador', 'O assistente retomará na primeira etapa incompleta. Reiniciar agora?') == QMessageBox.StandardButton.Yes:
            self.run('restart', lambda _: self.title.setText('Reiniciando…'))


def main():
    os.environ.setdefault('QT_LINUX_ACCESSIBILITY_ALWAYS_ON', '1')
    app = QApplication(sys.argv)
    app.setApplicationDisplayName('Configuração inicial do Linux BR')
    initialize()
    try:
        subprocess.run(['/usr/bin/xset', 's', 'off', '-dpms'], timeout=5, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass
    window = Wizard()
    window.setGeometry(app.primaryScreen().geometry())
    window.showFullScreen()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
