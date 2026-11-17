"""Histórico de autorizações disponível à conta atual."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QHeaderView, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from desktop_jobs import Query
from windows_runner import write_json


LIMIT = 200
PROGRAM = re.compile(r'^[A-Za-z0-9_.+@-]{1,100}$')
POLKIT = re.compile(
    r'^Operator of [^ ]+ (?:(successfully authenticated) as [^ ]+ to gain (?:TEMPORARY|ONE-SHOT) '
    r'|FAILED to authenticate to gain )authorization for action ([A-Za-z0-9_.-]{1,180}) for [^ ]+ \[(.*)\]$')


def record_path():
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local/state')
    return state/'linuxbr/consent-history.json'


def account():
    uid = os.getuid()
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def stored_records(path):
    if path.is_symlink():
        raise OSError('O histórico de autorizações não pode usar um link de arquivo.')
    try:
        with path.open('rb') as file:
            data = file.read(262145)
    except FileNotFoundError:
        return []
    if len(data) > 262144:
        raise ValueError('O histórico de autorizações excede o tamanho esperado.')
    rows = json.loads(data)
    if not isinstance(rows,list):
        raise ValueError('Formato do histórico de autorizações inválido.')
    return [row for row in rows if isinstance(row,dict)][-LIMIT:]


def request(title, argv):
    if not argv or argv[0] not in ('/usr/bin/pkexec','pkexec'):
        return None
    # Retain only the operation label and the executable identity.
    executable = Path(argv[1]).name if len(argv)>1 else ''
    if executable=='python3' and len(argv)>2:
        candidate = Path(argv[2])
        if candidate.parent == Path('/usr/lib/linuxbr-system') and candidate.suffix=='.py':
            executable = candidate.stem
    if not PROGRAM.fullmatch(executable):
        executable='pkexec'
    label = ' '.join(title.split())[:140]
    return dict(request=label, app=executable, account=account(),
                time=datetime.now(timezone.utc).isoformat(), source='Linux BR')


def record_result(entry, code):
    if not entry or not os.getuid():
        return
    result = {0:'Operação concluída',126:'Solicitação cancelada',
              127:'Não autorizada ou indisponível'}.get(code,'Operação falhou')
    path = record_path()
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor = os.open(path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows = stored_records(path)
        rows.append(dict(entry,result=result))
        write_json(path,rows[-LIMIT:])


def journal_row(row, owner, uid):
    if row.get('_COMM')!='polkitd' or row.get('_SYSTEMD_UNIT')!='polkit.service':
        return None
    message = row.get('MESSAGE')
    if not isinstance(message,str):
        return None
    entry, separator, suffix = message.rpartition(' (owned by ')
    if not separator or suffix not in ('unix-user:'+owner+')','unix-user:'+str(uid)+')'):
        return None
    match = POLKIT.fullmatch(entry)
    if not match:
        return None
    try:
        instant = datetime.fromtimestamp(int(row['__REALTIME_TIMESTAMP'])/1000000, timezone.utc)
    except (KeyError,TypeError,ValueError,OverflowError,OSError):
        return None
    path = Path(match[3].split(maxsplit=1)[0]).name if match[3].strip() else ''
    return dict(request=match[2],app=path if PROGRAM.fullmatch(path) else 'Aplicativo não identificado',
                account=owner,time=instant.isoformat(),source='Polkit',
                result='Autorizada' if match[1] else 'Autenticação não concluída')


def history():
    owner = account()
    local = [row for row in stored_records(record_path()) if row.get('account')==owner]
    try:
        command = ['/usr/bin/journalctl','--no-pager','--quiet','--output=json',
                   '--output-fields=MESSAGE,_COMM,_SYSTEMD_UNIT','--lines=600',
                   '--since=30 days ago','_COMM=polkitd','_SYSTEMD_UNIT=polkit.service']
        result = subprocess.run(command,capture_output=True,text=True,check=True,timeout=6)
    except (OSError,subprocess.SubprocessError):
        return list(reversed(local)), False
    records = []
    for line in result.stdout.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        event = journal_row(data,owner,os.getuid()) if isinstance(data,dict) else None
        if event:
            records.append(event)
    return sorted(local+records,key=lambda row:str(row.get('time','')),reverse=True)[:LIMIT], True


class ConsentHistory(QWidget):
    def __init__(self):
        super().__init__()
        self.jobs = set()
        body = QVBoxLayout(self)
        title = QLabel('Histórico de autorizações administrativas')
        title.setStyleSheet('font-size:26px;font-weight:600')
        body.addWidget(title)
        note = QLabel('Veja as solicitações dos controles do Linux BR e os eventos do Polkit que sua conta pode consultar. '
                      'O histórico local guarda os últimos 200 resultados dessa conta.')
        note.setWordWrap(True)
        body.addWidget(note)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(['Data e hora','Solicitação','Aplicativo','Conta','Resultado','Origem'])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.header().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        body.addWidget(self.table,1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        self.refresh = QPushButton(QIcon.fromTheme('view-refresh'),'Atualizar')
        self.refresh.clicked.connect(self.load)
        body.addWidget(self.refresh,alignment=Qt.AlignmentFlag.AlignLeft)
        self.load()

    def load(self):
        if self.jobs:
            return
        job = Query(history,self)
        self.jobs.add(job)
        self.refresh.setEnabled(False)
        job.result.connect(self.loaded)
        job.failed.connect(self.status.setText)
        job.finished.connect(lambda:self.jobs.discard(job))
        job.finished.connect(lambda:self.refresh.setEnabled(True))
        job.finished.connect(job.deleteLater)
        job.start()

    def loaded(self, result):
        rows, journal = result
        self.table.clear()
        for row in rows:
            try:
                instant=datetime.fromisoformat(row['time']).astimezone().strftime('%d/%m/%Y %H:%M:%S')
            except (TypeError,KeyError,ValueError):
                continue
            values = [instant,*[str(row.get(key,'')) for key in ('request','app','account','result','source')]]
            item = QTreeWidgetItem(values)
            item.setToolTip(1,values[1])
            self.table.addTopLevelItem(item)
        text = f'{self.table.topLevelItemCount()} registros encontrados.'
        if not journal:
            text += ' O diário do sistema está indisponível para esta conta.'
        self.status.setText(text)
