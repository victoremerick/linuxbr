"""Opções gráficas do atalho e reabertura seletiva de programas Wine."""
from datetime import datetime, timezone
import fcntl
import json
import ntpath
import os
from pathlib import Path
import select
import signal
import subprocess
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)
from windows_games import details_uri
import windows_runner as runner


RENDERERS = {'environment':'Usar renderizador do ambiente', 'wined3d':'WineD3D (OpenGL, Direct3D 9 a 11)'}
WINDOWS = ('normal','1024x768','1280x720','1280x768','1600x900','1920x1080')
DEFAULT = {'renderer':'environment','window':'normal'}
PROGRAM_MARKER = 'LINUXBR_WINDOWS_PROGRAM_ID'


def record_path(identifier):
    program = runner.read_program(identifier)
    return valid_path(runner.data_root()/'graphics'/f"{program['id']}.json")


def valid_path(path):
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('Os ajustes do programa não podem usar um atalho de arquivo.')
    return path


def checked(data):
    if (not isinstance(data,dict) or set(data) != {'renderer','window'} or
            not isinstance(data['renderer'],str) or data['renderer'] not in RENDERERS or
            data['window'] not in WINDOWS):
        raise ValueError('Selecione um renderizador e uma resolução oferecidos.')
    return dict(data)


def read(identifier):
    return read_settings(record_path(identifier))


def read_settings(path):
    if not path.exists():
        return {'current':dict(DEFAULT),'previous':None}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict):
        raise ValueError('O registro de gráficos tem um formato inválido.')
    return {'current':checked(data.get('current')),
            'previous':checked(data['previous']) if data.get('previous') is not None else None}


def save(identifier, settings):
    save_settings(record_path(identifier),settings)


def save_settings(path, settings):
    if os.geteuid()==0:
        raise ValueError('Configure o programa na sua conta.')
    settings = checked(settings)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor = os.open(path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old = read_settings(valid_path(path))
        if settings != old['current']:
            runner.write_json(path,{
                'current':settings, 'previous':old['current'], 'changed':datetime.now(timezone.utc).isoformat(),
            })


def registered_executable(identifier, environment, filename):
    item = runner.read_program(identifier)
    path, kind = runner.inspect_windows_file(filename)
    if kind not in ('x86','x64') or item['environment'] != environment or Path(item['file']).resolve() != path:
        raise ValueError('Os ajustes gráficos pertencem a outro atalho.')
    return path


def apply_launch(identifier, environment, filename, argv, env):
    executable = registered_executable(identifier, environment, filename)
    settings = read(identifier)['current']
    env[PROGRAM_MARKER] = identifier
    if settings['renderer'] == 'wined3d':
        env['WINEDLLOVERRIDES'] = 'd3d9,d3d10core,d3d11,dxgi=b'
    if settings['window'] != 'normal':
        path = subprocess.check_output(['winepath','-w',str(executable)], env=env, text=True, timeout=8).rstrip('\r\n')
        if not path or any(char in path for char in ('\x00','\n','\r','"')):
            raise ValueError('Não foi possível localizar o programa no ambiente Wine.')
        desktop = f"LinuxBR-{identifier[:16]}-{settings['window']},{settings['window']}"
        argv = ['wine','explorer','/desktop='+desktop,path]
    return argv, env


def process_match(process, executable, prefix, identifier):
    """Ordinary Wine helpers and unrelated programs in the prefix are ignored."""
    try:
        info = process.stat()
        if info.st_uid != os.getuid():
            return None
        with (process/'cmdline').open('rb') as stream:
            command = stream.read(8192).split(b'\0', 1)[0]
        if ntpath.basename(os.fsdecode(command)).casefold() != executable:
            return None
        with (process/'environ').open('rb') as stream:
            env = stream.read(512*1024).split(b'\0')
        if b'WINEPREFIX='+os.fsencode(prefix) not in env:
            return None
        marker = os.fsencode(PROGRAM_MARKER+'='+identifier)
        return info.st_ino, marker in env
    except OSError:
        return None


def close_program(identifier):
    if os.geteuid()==0:
        raise ValueError('Reabra o programa na sua conta.')
    item = runner.read_program(identifier)
    executable = Path(item['file']).name.casefold()
    prefix = runner.environment_path(item['environment'])/'prefix'
    processes = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            match = process_match(entry, executable, prefix, identifier)
            if match:
                processes.append((entry, match))
    if any(not match[1] for _, match in processes):
        raise ValueError('Feche a instância aberta por outro atalho e então reabra este programa.')
    descriptors = []
    try:
        wait = select.poll()
        pending = set()
        deadline = time.monotonic() + 2.2
        for entry, identity in processes:
            try:
                fd = os.pidfd_open(int(entry.name))
            except ProcessLookupError:
                continue
            descriptors.append(fd)
            if process_match(entry, executable, prefix, identifier) != identity:
                continue
            try:
                signal.pidfd_send_signal(fd, signal.SIGTERM)
            except ProcessLookupError:
                continue
            wait.register(fd, select.POLLIN)
            pending.add(fd)
        while pending:
            budget = int((deadline - time.monotonic()) * 1000)
            if budget <= 0:
                raise ValueError('O programa ainda está aberto. Feche a janela antes de reabrir.')
            for fd, _event in wait.poll(budget):
                pending.discard(fd)
                wait.unregister(fd)
    finally:
        for fd in descriptors:
            os.close(fd)


class GraphicsOptions(QDialog):
    def __init__(self, identifier, parent=None):
        super().__init__(parent)
        self.identifier = identifier
        self.state = read(identifier)
        self.reopen = False
        self.setWindowTitle('Gráficos do programa')
        self.resize(570, 350)
        body = QVBoxLayout(self)
        note = QLabel('Use o modo janela para recuperar um programa que abriu fora da tela. A escolha se aplica às próximas aberturas por este atalho.')
        note.setWordWrap(True)
        body.addWidget(note)
        form = QFormLayout()
        self.renderer = QComboBox()
        for key, label in RENDERERS.items():
            self.renderer.addItem(label,key)
        self.window = QComboBox()
        for choice in WINDOWS:
            self.window.addItem('Abrir normalmente' if choice=='normal' else f'Janela de recuperação {choice}',choice)
        form.addRow('&Renderizador',self.renderer)
        form.addRow('&Modo de exibição',self.window)
        body.addLayout(form)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        previous = QPushButton('Recuperar ajuste anterior')
        previous.setEnabled(self.state['previous'] is not None)
        previous.clicked.connect(lambda: self.load(self.state['previous']))
        body.addWidget(previous)
        body.addStretch()
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Save).setText('Salvar')
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        restart = actions.addButton('Salvar e reabrir programa…',QDialogButtonBox.ButtonRole.ActionRole)
        restart.clicked.connect(lambda:self.commit(True))
        actions.accepted.connect(lambda:self.commit(False))
        actions.rejected.connect(self.reject)
        body.addWidget(actions)
        self.load(self.state['current'])

    def load(self, settings):
        self.renderer.setCurrentIndex(self.renderer.findData(settings['renderer']))
        self.window.setCurrentIndex(self.window.findData(settings['window']))

    def commit(self, restart):
        if restart and QMessageBox.question(self,'Reabrir o programa',
                'Salve o trabalho deste programa antes de fechar e reabrir sua janela.',
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:
            return
        try:
            save(self.identifier,dict(renderer=self.renderer.currentData(),window=self.window.currentData()))
            if restart:
                close_program(self.identifier)
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        self.reopen = restart
        self.accept()


def steam_option(renderer, window):
    settings = checked({'renderer':renderer,'window':window})
    parts = []
    if settings['renderer'] == 'wined3d':
        parts.append('PROTON_USE_WINED3D=1')
    if settings['window'] != 'normal':
        width, height = settings['window'].split('x')
        parts.extend(['gamescope','-w',width,'-h',height,'-W',width,'-H',height,'--'])
    return ' '.join([*parts,'%command%']) if parts else ''


class SteamGraphics(QDialog):
    def __init__(self, game, has_gamescope, parent=None):
        super().__init__(parent)
        details_uri(game['id'])
        self.path = valid_path(runner.data_root()/'steam-graphics'/f"{game['id']}.json")
        self.state = read_settings(self.path)
        self.has_gamescope = has_gamescope
        self.setWindowTitle('Gráficos do jogo na Steam')
        self.resize(610, 395)
        body = QVBoxLayout(self)
        guidance = QLabel(f"{game['name']}\n\n"
            "Na biblioteca da Steam, abra Propriedades → Geral → Opções de inicialização. "
            "Guarde o conteúdo anterior, cole a opção indicada e reabra só este jogo.")
        guidance.setTextFormat(Qt.TextFormat.PlainText)
        guidance.setWordWrap(True)
        body.addWidget(guidance)
        form = QFormLayout()
        self.renderer = QComboBox()
        self.renderer.addItem('Usar o padrão do Proton','environment')
        self.renderer.addItem(RENDERERS['wined3d'],'wined3d')
        self.window = QComboBox()
        self.window.addItem('Manter o modo do jogo','normal')
        if has_gamescope:
            for choice in WINDOWS[1:]:
                self.window.addItem(f'Janela de recuperação {choice}',choice)
        else:
            notice = QLabel('A recuperação em janela precisa do Gamescope instalado na sessão da Steam.')
            notice.setWordWrap(True)
            body.addWidget(notice)
        form.addRow('&Renderizador',self.renderer)
        form.addRow('&Modo de exibição',self.window)
        self.option = QPlainTextEdit()
        self.option.setReadOnly(True)
        self.option.setFixedHeight(54)
        self.option.setPlaceholderText('Nenhuma opção adicional')
        self.option.setAccessibleName('Opção de inicialização')
        form.addRow('&Opção de inicialização',self.option)
        body.addLayout(form)
        self.previous = QPushButton('Carregar opção anterior')
        self.previous.clicked.connect(lambda:self.load(self.state['previous']))
        body.addWidget(self.previous,alignment=Qt.AlignmentFlag.AlignLeft)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        body.addStretch()
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        actions.button(QDialogButtonBox.StandardButton.Close).setText('Fechar')
        self.copy_button = actions.addButton('Copiar e guardar opção',QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy_option)
        actions.rejected.connect(self.reject)
        body.addWidget(actions)
        self.renderer.currentIndexChanged.connect(self.update_option)
        self.window.currentIndexChanged.connect(self.update_option)
        self.load(self.state['current'])

    def load(self, value):
        window = value['window'] if self.has_gamescope else 'normal'
        self.renderer.setCurrentIndex(self.renderer.findData(value['renderer']))
        self.window.setCurrentIndex(self.window.findData(window))
        self.update_option()

    def update_option(self):
        self.option.setPlainText(steam_option(self.renderer.currentData(),self.window.currentData()) or '%command%')
        previous = self.state['previous']
        self.previous.setEnabled(bool(previous and (self.has_gamescope or previous['window']=='normal')))
        self.status.clear()

    def copy_option(self):
        try:
            settings = dict(renderer=self.renderer.currentData(),window=self.window.currentData())
            save_settings(self.path,settings)
            self.state = read_settings(self.path)
        except (OSError,ValueError) as error:
            self.status.setText(str(error))
            return
        QApplication.clipboard().setText(self.option.toPlainText())
        self.update_option()
        self.status.setText('Opção copiada e guardada neste computador. Cole nas propriedades deste jogo na Steam.')
