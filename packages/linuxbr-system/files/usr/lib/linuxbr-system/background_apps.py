"""Revisão do consumo e das permissões dos aplicativos da conta."""
import os
from pathlib import Path
import re
import shlex
import shutil
import time

from PyQt6.QtCore import QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QHeaderView, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from desktop_jobs import Query
import startup_backend as startup
from tasks import NumericItem, snapshot


SCOPE = re.compile(r'app-(?:(flatpak)-)?(.+)-[a-zA-Z0-9]+\.scope')
AUTOSTART = re.compile(r'app-(.+)@autostart\.service')
DESKTOP_ID = re.compile(r'[A-Za-z0-9_.-]{1,200}')


def application_scope(cgroup):
    for line in cgroup.splitlines():
        for unit in reversed(line.split('/')):
            match = SCOPE.fullmatch(unit)
            autostart = AUTOSTART.fullmatch(unit)
            if match or autostart:
                identifier = (match[2] if match else autostart[1]).replace(r'\x2d','-')
                if DESKTOP_ID.fullmatch(identifier):
                    return identifier.removesuffix('.desktop'), bool(match and match[1])
    return '', False


def direct_program(row):
    try:
        command = shlex.split(row['command'])
    except ValueError:
        return ''
    if not command or Path(command[0]).name in ('env','sh','bash','dash','python','python3','wine','java','flatpak'):
        return ''
    path = shutil.which(command[0])
    return str(Path(path).resolve()) if path else ''


def apps_snapshot(previous, last, *, proc=Path('/proc')):
    rows, _memory = snapshot(os.getuid())
    now = time.monotonic()
    elapsed = max(.1, now-last)
    starts = startup.inventory()
    by_desktop = {row['id']:row for row in starts}
    by_program = {}
    for row in starts:
        program = direct_program(row)
        if program:
            by_program.setdefault(program,[]).append(row)
    current, groups = {}, {}
    for row in rows:
        identity = (row['pid'],row['start'])
        current[identity] = row['cpu']
        usage = max(0, row['cpu']-previous.get(identity,row['cpu'])) * 100/elapsed
        process = proc/str(row['pid'])
        try:
            identifier, flatpak = application_scope((process/'cgroup').read_text())
        except OSError:
            identifier, flatpak = '', False
        entry = by_desktop.get(identifier+'.desktop')
        if not identifier:
            try:
                executable = os.readlink(process/'exe')
            except OSError:
                executable = ''
            fallback = by_program.get(executable,[])
            if len(fallback)==1:
                entry = fallback[0]
        key = identifier or (entry['id'] if entry else 'process:'+row['name'])
        app = groups.setdefault(key, dict(key=key,name=entry['name'] if entry else identifier or row['name'],
                               startup=entry, flatpak=identifier if flatpak else '',
                               count=0,cpu=0,rss=0))
        app['count'] += 1
        app['cpu'] += usage
        app['rss'] += max(0,row['rss'])
    try:
        from gi.repository import Gio
        for key, app in groups.items():
            if DESKTOP_ID.fullmatch(key):
                try:
                    desktop = Gio.DesktopAppInfo.new(key if key.endswith('.desktop') else key+'.desktop')
                except TypeError:
                    continue
                app['name'] = desktop.get_display_name()
    except ImportError:
        pass
    return current, now, sorted(groups.values(), key=lambda item:item['name'].casefold())


class BackgroundApps(QWidget):
    def __init__(self, navigate, permissions):
        super().__init__()
        self.navigate, self.permissions = navigate, permissions
        self.jobs, self.previous = set(), {}
        self.last = time.monotonic()
        body = QVBoxLayout(self)
        title = QLabel('Aplicativos em segundo plano')
        title.setStyleSheet('font-size:26px;font-weight:600')
        body.addWidget(title)
        note = QLabel('Veja o consumo dos programas da sua conta, inclusive sem janela aberta. '
                      'A memória soma o uso residente dos processos e pode contar memória compartilhada.')
        note.setWordWrap(True)
        body.addWidget(note)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Pesquisar aplicativo')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        body.addWidget(self.search)
        self.table = QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['Aplicativo','Processos','CPU','Memória','Inicia no login'])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in range(1,5):
            self.table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.selection)
        body.addWidget(self.table,1)
        actions = QHBoxLayout()
        self.disable = self.add_button(actions,'Desabilitar no login','dialog-cancel',self.stop_startup)
        self.flatpak = self.add_button(actions,'Rever permissões Flatpak','preferences-system-privacy',self.open_permissions)
        self.add_button(actions,'Todos os programas de inicialização','system-run',lambda:self.navigate('startup'))
        body.addLayout(actions)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        body.addWidget(self.status)
        self.timer = QTimer(self, interval=2500)
        self.timer.timeout.connect(self.refresh)
        self.selection()

    def add_button(self, actions, title, icon, callback):
        button = QPushButton(QIcon.fromTheme(icon),title)
        button.clicked.connect(callback)
        actions.addWidget(button)
        return button

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def query(self, operation, receive):
        job = Query(operation,self)
        self.jobs.add(job)
        job.result.connect(receive)
        job.failed.connect(self.status.setText)
        job.finished.connect(lambda:self.jobs.discard(job))
        job.finished.connect(self.selection)
        job.finished.connect(job.deleteLater)
        job.start()

    def refresh(self):
        if not self.jobs:
            previous, last = self.previous, self.last
            self.query(lambda:apps_snapshot(previous,last),self.loaded)

    def selected(self):
        item = self.table.item(self.table.currentRow(),0)
        return item.data(Qt.ItemDataRole.UserRole) if item and item.isSelected() else None

    def selection(self):
        row = self.selected()
        entry = row['startup'] if row else None
        self.disable.setEnabled(bool(entry and entry['editable'] and not entry['hidden'] and not entry['protected']))
        self.flatpak.setEnabled(bool(row and row['flatpak']))

    def filter(self):
        term = self.search.text().strip().casefold()
        for index in range(self.table.rowCount()):
            self.table.setRowHidden(index,term not in self.table.item(index,0).text().casefold())

    def loaded(self, result):
        self.previous, self.last, apps = result
        selected = self.selected()
        with QSignalBlocker(self.table):
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(apps))
            keep = None
            for index, app in enumerate(apps):
                count, cpu, rss = app['count'],app['cpu'],app['rss']
                startup_status = app['startup']['status'] if app['startup'] else 'Sem entrada identificada'
                cells = [QTableWidgetItem(app['name']),NumericItem(str(count),count),
                         NumericItem(f'{cpu:.1f} %',cpu),NumericItem(f'{rss/1048576:.1f} MiB',rss),
                         QTableWidgetItem(startup_status)]
                cells[0].setData(Qt.ItemDataRole.UserRole,app)
                for column, cell in enumerate(cells):
                    self.table.setItem(index,column,cell)
                if selected and selected['key']==app['key']:
                    keep = cells[0]
            self.table.setSortingEnabled(True)
            self.table.clearSelection()
            if keep:
                self.table.selectRow(keep.row())
        self.filter()
        self.selection()

    def stop_startup(self):
        row = self.selected()
        entry = row['startup'] if row else None
        if not entry or self.jobs:
            return
        if QMessageBox.question(self,'Desabilitar no próximo login',
                f"Desabilitar a inicialização de {entry['name']} na sua conta?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:
            return
        self.query(lambda:startup.change(entry['id'],entry['sha256'],False),self.status.setText)

    def open_permissions(self):
        row = self.selected()
        if row and row['flatpak']:
            self.permissions(row['flatpak'])
