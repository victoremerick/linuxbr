"""Service for staged Linux BR package authorizations and support requests."""
import argparse
import base64
import binascii
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys


NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
HASH = re.compile(r'[a-f0-9]{64}')
TOKEN = re.compile(r'[A-Za-z0-9_-]{43}')
REQUEST_ID = re.compile(r'[a-f0-9]{32}')
VERSION = re.compile(r'[0-9][A-Za-z0-9.+~:-]{0,79}')
RULE_ID = re.compile(r'[a-z][a-z0-9-]{0,60}')
WINDOW_TIME = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?'
                         r'(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])')
MAX_BODY = 16384
WAVES = {'pilot', 'general'}
ROLES = {'admin', 'release', 'support', 'audit'}
FILES = Path(__file__).resolve().parent
SCHEMA = """
CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK (id=1), organization TEXT NOT NULL,
                       revision TEXT, general INTEGER NOT NULL DEFAULT 0,
                       paused INTEGER NOT NULL DEFAULT 0);
CREATE TABLE revisions (name TEXT PRIMARY KEY, archives TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE policy_profiles (name TEXT PRIMARY KEY, rules TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE operators (name TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, role TEXT NOT NULL);
CREATE TABLE devices (name TEXT PRIMARY KEY, wave TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                      enabled INTEGER NOT NULL DEFAULT 1, last_contact TEXT, release TEXT,
                      free_bytes INTEGER, reboot_pending INTEGER);
CREATE TABLE results (device TEXT NOT NULL REFERENCES devices(name),
                      revision TEXT NOT NULL REFERENCES revisions(name),
                      state TEXT NOT NULL, checked TEXT NOT NULL,
                      PRIMARY KEY(device, revision));
CREATE TABLE policy_assignments (device TEXT PRIMARY KEY REFERENCES devices(name),
                                 profile TEXT NOT NULL REFERENCES policy_profiles(name));
CREATE TABLE diagnostics (id TEXT PRIMARY KEY, device TEXT NOT NULL REFERENCES devices(name),
                          created TEXT NOT NULL, expires TEXT NOT NULL,
                          state TEXT NOT NULL, report TEXT, completed TEXT);
CREATE UNIQUE INDEX pending_diagnostics ON diagnostics(device) WHERE state='pending';
CREATE TABLE audit (id INTEGER PRIMARY KEY, checked TEXT NOT NULL,
                    actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT);
"""
WINDOW_SCHEMA = """CREATE TABLE IF NOT EXISTS maintenance_windows (
    revision TEXT PRIMARY KEY REFERENCES revisions(name),
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL
)"""


class ServiceError(ValueError):
    def __init__(self, message, status='400 Bad Request'):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


def checked(value, pattern, message):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ServiceError(message)
    return value


def window_time(value):
    error = 'Informe data, horário e fuso da janela de manutenção.'
    checked(value, WINDOW_TIME, error)
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ServiceError(error) from exc


def normalized_window(value):
    if not isinstance(value, dict) or value.keys() != {'starts_at', 'ends_at'}:
        raise ServiceError('Informe o início e o fim da janela de manutenção.')
    start, end = window_time(value['starts_at']), window_time(value['ends_at'])
    if end <= start:
        raise ServiceError('O fim da janela precisa ser depois do início.')
    return {'starts_at': start.isoformat(), 'ends_at': end.isoformat()}


def window_state(window, instant):
    if window is None:
        return 'none'
    if instant < window_time(window['starts_at']):
        return 'scheduled'
    if instant >= window_time(window['ends_at']):
        return 'closed'
    return 'open'


def digest(data):
    return hashlib.sha256(data.encode('ascii')).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')


def inventory_fields(value):
    if not isinstance(value, dict) or value.keys() != {'release', 'free_bytes', 'reboot_pending'}:
        raise ServiceError('Inventário inválido.')
    release = value['release']
    free_bytes = value['free_bytes']
    if release is not None:
        checked(release, VERSION, 'Versão inválida no inventário.')
    if type(free_bytes) is not int or not 0 <= free_bytes <= 2**63 - 1:
        raise ServiceError('Espaço inválido no inventário.')
    if type(value['reboot_pending']) is not bool:
        raise ServiceError('Estado de reinício inválido.')
    return release, free_bytes, value['reboot_pending']


def diagnostic_report(value):
    if (not isinstance(value, dict) or value.keys() != {'schema', 'diagnóstico'}
            or type(value['schema']) is not int or value['schema'] != 1):
        raise ServiceError('Relatório de diagnóstico inválido.')
    categories = value['diagnóstico']
    status = {'active', 'inactive', 'failed', 'activating', 'deactivating', 'indisponível'}
    checks = {
        'Sistema e espaço': {
            'versão': lambda v: v == 'indisponível' or isinstance(v, str) and VERSION.fullmatch(v),
            'kernel': lambda v: isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9._+-]{1,128}', v),
            'espaço livre no sistema (bytes)': lambda v: type(v) is int and 0 <= v <= 2**63 - 1,
        },
        'Rede': {'conectividade': lambda v: isinstance(v, str) and
                 v in {'none', 'portal', 'limited', 'full', 'unknown', 'indisponível'}},
        'Atualização e recuperação': {
            'reinício solicitado pelo sistema': lambda v: type(v) is bool,
            'destino de recuperação configurado': lambda v: type(v) is bool,
            'última proteção': lambda v: isinstance(v, str) and
            v in {'created', 'failed', 'disabled', 'not-configured', 'indisponível'},
            'revisão associada à proteção': lambda v: isinstance(v, str) and NAME.fullmatch(v),
            'revisão preparada nesta conta': lambda v: isinstance(v, str) and NAME.fullmatch(v),
            'código da última proteção': lambda v: type(v) is int and -255 <= v <= 255,
        },
        'Sessão gráfica e captura': {
            'sessão': lambda v: isinstance(v, str) and v in {'wayland', 'x11', 'indisponível'},
            **{name: lambda v: isinstance(v, str) and v in status for name in (
                'xdg-desktop-portal', 'plasma-xdg-desktop-portal-kde',
                'plasma-kwin_wayland', 'pipewire', 'wireplumber')},
            **{name: lambda v: v == 'indisponível' or type(v) is int and 0 <= v <= 30 for name in (
                'avisos do portal KDE nas últimas 24 h', 'avisos do KWin nas últimas 24 h')},
        },
    }
    if not isinstance(categories, dict) or not categories:
        raise ServiceError('Escolha pelo menos uma categoria para o diagnóstico.')
    for category, fields in categories.items():
        if category not in checks or not isinstance(fields, dict) or not fields:
            raise ServiceError('Categoria de diagnóstico inválida.')
        for key, item in fields.items():
            if key not in checks[category] or not checks[category][key](item):
                raise ServiceError('Campo de diagnóstico inválido.')
    return value


def policy_rules(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 30:
        raise ServiceError('O perfil precisa de 1 a 30 regras.')
    seen = set()
    for rule in value:
        if (not isinstance(rule, dict) or rule.keys() != {'id', 'required', 'value'}
                or type(rule['required']) is not bool):
            raise ServiceError('Regra de política inválida.')
        identifier = checked(rule['id'], RULE_ID, 'Identificador de regra inválido.')
        if identifier in seen or len(json_bytes(rule['value'])) > 2048:
            raise ServiceError('Regra duplicada ou fora do limite.')
        seen.add(identifier)
        data = rule['value']
        if identifier in ('store-snap', 'store-brew') and type(data) is not bool:
            raise ServiceError('A permissão da fonte da Loja precisa ser true ou false.')
        if identifier == 'work-folder' and (not isinstance(data, str) or not 1 <= len(data) <= 80
                or data.strip() != data or not any(c.isalnum() for c in data)
                or not all(c.isalnum() or c in ' _-' for c in data)):
            raise ServiceError('Nome da pasta de trabalho inválido.')
        if identifier == 'store-search' and (not isinstance(data, list) or not 1 <= len(data) <= 12
                or any(not isinstance(term, str) or not 1 <= len(term) <= 80 or not term.strip()
                       or not all(c.isprintable() for c in term) for term in data)):
            raise ServiceError('Termos de pesquisa da Loja inválidos.')
    if len(json_bytes(value)) > MAX_BODY:
        raise ServiceError('Perfil de política grande demais.')
    return value


class Service:
    def __init__(self, database, signer=None, public_origin=None):
        self.database = Path(database)
        self.signer = signer
        self.public_origin = public_origin

    def connect(self):
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    def initialize(self, organization):
        checked(organization, NAME, 'Organização inválida.')
        descriptor = os.open(self.database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with closing(self.connect()) as db, db:
            db.executescript(SCHEMA)
            db.execute(WINDOW_SCHEMA)
            db.execute('INSERT INTO settings(id,organization) VALUES(1,?)', (organization,))

    @staticmethod
    def audit(db, actor, action, target=None):
        db.execute('INSERT INTO audit(checked,actor,action,target) VALUES(?,?,?,?)',
                   (now().isoformat(), actor, action, target))

    def register(self, name, wave=None, role='admin'):
        checked(name, NAME, 'Nome de cadastro inválido.')
        token = secrets.token_urlsafe(32)
        with closing(self.connect()) as db, db:
            if wave is None:
                if role not in ROLES:
                    raise ServiceError('Papel do operador inválido.')
                db.execute('INSERT INTO operators VALUES(?,?,?)', (name, digest(token), role))
                self.audit(db, 'console', 'cadastro de operador', name)
            else:
                if wave not in WAVES:
                    raise ServiceError('Onda inválida.')
                db.execute('INSERT INTO devices(name,wave,token_hash) VALUES(?,?,?)',
                           (name, wave, digest(token)))
                self.audit(db, 'console', 'cadastro de dispositivo', name)
        return token

    def stage(self, revision, paths):
        checked(revision, NAME, 'Revisão inválida.')
        archives = []
        for path in paths:
            if path.suffix != '.deb' or not path.is_file():
                raise ServiceError('Use os arquivos DEB exatos da transação.')
            with path.open('rb') as stream:
                result = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    result.update(chunk)
            archives.append(result.hexdigest())
        if not archives or len(archives) > 512 or len(set(archives)) != len(archives):
            raise ServiceError('Informe de 1 a 512 arquivos DEB distintos.')
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO revisions VALUES(?,?,?)',
                       (revision, json.dumps(sorted(archives)), now().isoformat()))
            self.audit(db, 'console', 'revisão cadastrada', revision)

    def stage_policy(self, name, rules):
        checked(name, NAME, 'Identificador de política inválido.')
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO policy_profiles VALUES(?,?,?)',
                       (name, json_bytes(policy_rules(rules)).decode('utf-8'), now().isoformat()))
            self.audit(db, 'console', 'política cadastrada', name)

    @staticmethod
    def prune(db):
        instant = now()
        db.execute("UPDATE diagnostics SET state='expired' WHERE state='pending' AND expires<=?",
                   (instant.isoformat(),))
        db.execute('DELETE FROM diagnostics WHERE created<=?', ((instant - timedelta(days=7)).isoformat(),))

    @staticmethod
    def active(db):
        return db.execute('SELECT * FROM settings WHERE id=1').fetchone()

    @staticmethod
    def maintenance_window(db, revision):
        row = db.execute('SELECT starts_at,ends_at FROM maintenance_windows WHERE revision=?',
                         (revision,)).fetchone()
        return dict(row) if row else None

    def change_window(self, db, actor, payload):
        revision = checked(payload.get('target'), NAME, 'Revisão inválida.')
        if not db.execute('SELECT 1 FROM revisions WHERE name=?', (revision,)).fetchone():
            raise ServiceError('A revisão não está cadastrada.', '409 Conflict')
        current = self.maintenance_window(db, revision)
        if 'expected_window' not in payload or payload['expected_window'] != current:
            raise ServiceError('A janela mudou. Atualize o painel antes de confirmar.', '409 Conflict')
        if payload['action'] == 'clear-window':
            if current is None:
                raise ServiceError('Esta revisão já está sem janela de manutenção.', '409 Conflict')
            db.execute('DELETE FROM maintenance_windows WHERE revision=?', (revision,))
            action, window = 'clear-window', current
        else:
            window = normalized_window(payload.get('window'))
            db.execute("""INSERT INTO maintenance_windows(revision,starts_at,ends_at) VALUES(?,?,?)
                       ON CONFLICT(revision) DO UPDATE SET starts_at=excluded.starts_at,ends_at=excluded.ends_at""",
                       (revision, window['starts_at'], window['ends_at']))
            action = 'reschedule-window' if current else 'set-window'
        self.audit(db, actor, action, f"{revision} · {window['starts_at']} → {window['ends_at']}")
        return {'ok': True}

    def change(self, db, actor, payload):
        action, target = payload.get('action'), payload.get('target')
        if action in ('set-window', 'clear-window'):
            return self.change_window(db, actor, payload)
        active = self.active(db)
        if action == 'pilot':
            checked(target, NAME, 'Revisão inválida.')
            if active['revision'] == target or not db.execute(
                    'SELECT 1 FROM revisions WHERE name=?', (target,)).fetchone():
                raise ServiceError('Selecione outra revisão cadastrada.')
            if db.execute('SELECT 1 FROM audit WHERE action=? AND target=?',
                          ('pilot', target)).fetchone():
                raise ServiceError('Cadastre uma revisão nova para repetir o piloto.')
            db.execute('UPDATE settings SET revision=?,general=0,paused=0 WHERE id=1', (target,))
        elif action in ('promote', 'pause', 'resume', 'retire'):
            if not active['revision'] or target != active['revision']:
                raise ServiceError('A revisão ativa mudou. Atualize o painel.', '409 Conflict')
            if action == 'promote':
                rows = db.execute("""
                    SELECT r.state FROM devices d LEFT JOIN results r ON r.device=d.name AND r.revision=?
                    WHERE d.wave='pilot' AND d.enabled=1
                """, (target,)).fetchall()
                if active['paused'] or not rows or any(row['state'] != 'completed' for row in rows):
                    raise ServiceError('A promoção exige conclusão de todos os pilotos habilitados.')
                db.execute('UPDATE settings SET general=1 WHERE id=1')
            elif action == 'retire':
                db.execute('UPDATE settings SET revision=NULL,general=0,paused=0 WHERE id=1')
            else:
                db.execute('UPDATE settings SET paused=? WHERE id=1', (action == 'pause',))
        elif action == 'diagnostic':
            checked(target, NAME, 'Dispositivo inválido.')
            if not db.execute('SELECT 1 FROM devices WHERE name=? AND enabled=1', (target,)).fetchone():
                raise ServiceError('Dispositivo não cadastrado ou desabilitado.')
            instant = now()
            db.execute("""INSERT INTO diagnostics(id,device,created,expires,state)
                          VALUES(?,?,?,?,'pending')""",
                       (secrets.token_hex(16), target, instant.isoformat(),
                        (instant + timedelta(hours=24)).isoformat()))
        elif action == 'delete-diagnostic':
            checked(target, REQUEST_ID, 'Identificador de diagnóstico inválido.')
            if not db.execute('DELETE FROM diagnostics WHERE id=?', (target,)).rowcount:
                raise ServiceError('Solicitação de diagnóstico não encontrada.')
        elif action in ('disable-device', 'enable-device'):
            checked(target, NAME, 'Dispositivo inválido.')
            if not db.execute('UPDATE devices SET enabled=? WHERE name=?',
                              (action == 'enable-device', target)).rowcount:
                raise ServiceError('Dispositivo não encontrado.')
        elif action in ('assign-policy', 'clear-policy'):
            checked(target, NAME, 'Dispositivo inválido.')
            if not db.execute('SELECT 1 FROM devices WHERE name=? AND enabled=1', (target,)).fetchone():
                raise ServiceError('Dispositivo não cadastrado ou desabilitado.')
            if action == 'assign-policy':
                profile = checked(payload.get('profile'), NAME, 'Perfil inválido.')
                if not db.execute('SELECT 1 FROM policy_profiles WHERE name=?', (profile,)).fetchone():
                    raise ServiceError('Perfil não cadastrado.')
                db.execute("""INSERT INTO policy_assignments VALUES(?,?)
                              ON CONFLICT(device) DO UPDATE SET profile=excluded.profile""",
                           (target, profile))
                self.audit(db, actor, action, target + ' · ' + profile)
                return {'ok': True}
            db.execute('DELETE FROM policy_assignments WHERE device=?', (target,))
        else:
            raise ServiceError('Ação de administração inválida.')
        self.audit(db, actor, action, target)
        return {'ok': True}

    def manifest(self, db, device, payload):
        nonce = checked(payload.get('nonce'), HASH, 'Solicitação de manifesto inválida.')
        release, free_bytes, reboot = inventory_fields(payload.get('inventory'))
        db.execute('UPDATE devices SET release=?,free_bytes=?,reboot_pending=? WHERE name=?',
                   (release, free_bytes, reboot, device['name']))
        active = self.active(db)
        revision = active['revision']
        if not revision:
            raise ServiceError('Nenhuma revisão está liberada.', '409 Conflict')
        row = db.execute('SELECT archives FROM revisions WHERE name=?', (revision,)).fetchone()
        result = db.execute('SELECT state FROM results WHERE device=? AND revision=?',
                            (device['name'], revision)).fetchone()
        if result and result['state'] in ('failed', 'restored'):
            raise ServiceError('A revisão está bloqueada neste dispositivo.', '409 Conflict')
        instant = now()
        window = self.maintenance_window(db, revision)
        state = window_state(window, instant)
        waves = {wave: ('approved' if not active['paused'] and state in ('none', 'open')
                        and (wave == 'pilot' or active['general']) else 'paused') for wave in WAVES}
        expires = instant + timedelta(minutes=2)
        if state == 'open':
            expires = min(expires, window_time(window['ends_at']))
        manifest = {'schema': 1, 'organization': active['organization'], 'revision': revision,
                    'issued_at': instant.isoformat(), 'expires_at': expires.isoformat(),
                    'waves': waves, 'archives': json.loads(row['archives']), 'nonce': nonce,
                    'device': device['name'], 'wave': device['wave']}
        if window:
            manifest['maintenance_window'] = window
        signed = self.signer(json_bytes(manifest))
        if waves[device['wave']] == 'approved':
            db.execute("INSERT OR IGNORE INTO results VALUES(?,?,'authorized',?)",
                       (device['name'], revision, instant.isoformat()))
        return signed

    def client(self, db, device, method, path, payload):
        name = device['name']
        db.execute('UPDATE devices SET last_contact=? WHERE name=?', (now().isoformat(), name))
        if path == '/v1/manifest' and method == 'POST':
            return self.manifest(db, device, payload)
        if path == '/v1/inventory' and method == 'POST':
            release, free_bytes, reboot = inventory_fields(payload)
            db.execute('UPDATE devices SET release=?,free_bytes=?,reboot_pending=? WHERE name=?',
                       (release, free_bytes, reboot, name))
            return {'ok': True}
        if path == '/v1/policy' and method == 'POST':
            nonce = checked(payload.get('nonce'), HASH, 'Solicitação de política inválida.')
            profile = db.execute("""SELECT p.name,p.rules FROM policy_profiles p
                                 JOIN policy_assignments a ON a.profile=p.name WHERE a.device=?""",
                                 (name,)).fetchone()
            if not profile:
                raise ServiceError('Nenhuma política foi atribuída a este dispositivo.', '409 Conflict')
            instant = now()
            return self.signer(json_bytes({
                'schema': 1, 'kind': 'organization-policy', 'organization': self.active(db)['organization'],
                'device': name, 'revision': profile['name'], 'nonce': nonce,
                'issued_at': instant.isoformat(), 'expires_at': (instant + timedelta(minutes=2)).isoformat(),
                'rules': json.loads(profile['rules']),
            }))
        if path == '/v1/result' and method == 'POST':
            revision = checked(payload.get('revision'), NAME, 'Revisão inválida.')
            state = payload.get('state')
            if state not in ('completed', 'failed', 'restored'):
                raise ServiceError('Resultado inválido.')
            result = db.execute('SELECT state FROM results WHERE device=? AND revision=?',
                                (name, revision)).fetchone()
            if not result or (result['state'] == 'restored' and state != 'restored') or (
                    result['state'] == 'failed' and state == 'completed'):
                raise ServiceError('Nenhuma autorização válida para registrar este resultado.', '409 Conflict')
            if result['state'] != state:
                db.execute('UPDATE results SET state=?,checked=? WHERE device=? AND revision=?',
                           (state, now().isoformat(), name, revision))
                self.audit(db, name, state, revision)
            return {'ok': True}
        if path == '/v1/diagnostic' and method == 'GET':
            row = db.execute("SELECT id,expires FROM diagnostics WHERE device=? AND state='pending'",
                             (name,)).fetchone()
            return {'request_id': row['id'] if row else None,
                    'expires_at': row['expires'] if row else None}
        if path == '/v1/diagnostic' and method == 'POST':
            identifier = checked(payload.get('request_id'), REQUEST_ID, 'Solicitação inválida.')
            if payload.keys() == {'request_id', 'decline'} and payload['decline'] is True:
                state, report = 'declined', None
            elif payload.keys() == {'request_id', 'report'}:
                state, report = 'received', json.dumps(diagnostic_report(payload['report']), ensure_ascii=False)
            else:
                raise ServiceError('Resposta de diagnóstico inválida.')
            if not db.execute("""UPDATE diagnostics SET state=?,report=?,completed=?
                                 WHERE id=? AND device=? AND state='pending'""",
                              (state, report, now().isoformat(), identifier, name)).rowcount:
                raise ServiceError('A solicitação não está pendente neste dispositivo.', '409 Conflict')
            self.audit(db, name, state, identifier)
            return {'ok': True}
        raise ServiceError('Operação desconhecida.', '404 Not Found')

    def dashboard(self, db):
        active = self.active(db)
        window = self.maintenance_window(db, active['revision'])
        return {'active': {**dict(active), 'window_state': window_state(window, now())},
                'revisions': [{'name': row['name'], 'created': row['created'],
                               'window': {'starts_at': row['starts_at'], 'ends_at': row['ends_at']}
                               if row['starts_at'] is not None else None} for row in db.execute("""
                    SELECT r.name,r.created,m.starts_at,m.ends_at FROM revisions r
                    LEFT JOIN maintenance_windows m ON m.revision=r.name
                    ORDER BY r.created DESC LIMIT 200""")],
                'policies': [dict(row) for row in db.execute(
                    'SELECT name,created FROM policy_profiles ORDER BY created DESC LIMIT 200')],
                'devices': [dict(row) for row in db.execute("""
                    SELECT d.name,d.wave,d.enabled,d.last_contact,d.release,d.free_bytes,
                           d.reboot_pending,r.state,r.checked,a.profile,
                           (SELECT revision FROM results WHERE device=d.name AND state='completed'
                            ORDER BY checked DESC LIMIT 1) AS confirmed_revision
                    FROM devices d LEFT JOIN results r ON r.device=d.name AND r.revision=?
                    LEFT JOIN policy_assignments a ON a.device=d.name
                    ORDER BY d.name
                """, (active['revision'],))],
                'diagnostics': [dict(row) for row in db.execute("""SELECT id,device,created,expires,state,
                    completed FROM diagnostics ORDER BY created DESC LIMIT 200""")],
                'audit': [dict(row) for row in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]}

    def credential(self, db, header, admin):
        kind, _, value = header.partition(' ')
        user = None
        if admin and kind.lower() == 'basic' and len(value) <= 256:
            try:
                user, separator, value = base64.b64decode(value, validate=True).decode('ascii').partition(':')
                if not separator or not NAME.fullmatch(user):
                    return None
            except (UnicodeError, binascii.Error):
                return None
        elif kind.lower() != 'bearer':
            return None
        if not TOKEN.fullmatch(value):
            return None
        if admin:
            row = db.execute('SELECT name,role FROM operators WHERE token_hash=?', (digest(value),)).fetchone()
            return row if row and (user is None or row['name'] == user) else None
        return db.execute('SELECT name,wave FROM devices WHERE token_hash=? AND enabled=1',
                          (digest(value),)).fetchone()

    @staticmethod
    def body(environ):
        if environ.get('CONTENT_TYPE', '').split(';')[0].strip().lower() != 'application/json':
            raise ServiceError('Envie um corpo JSON.', '415 Unsupported Media Type')
        size = environ.get('CONTENT_LENGTH', '')
        if not re.fullmatch(r'[0-9]{1,5}', size) or not 0 < int(size) <= MAX_BODY:
            raise ServiceError('Corpo da solicitação fora do limite.', '413 Content Too Large')
        value = json.loads(environ['wsgi.input'].read(int(size)))
        if not isinstance(value, dict):
            raise ServiceError('Corpo da solicitação inválido.')
        return value

    def dispatch(self, environ):
        path, method = environ['PATH_INFO'], environ['REQUEST_METHOD']
        admin = path in ('/', '/panel.js', '/panel.css', '/v1/admin/status',
                         '/v1/admin/action', '/v1/admin/report')
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            actor = self.credential(db, environ.get('HTTP_AUTHORIZATION', ''), admin)
            if not actor:
                extra = [('WWW-Authenticate', 'Basic realm="Linux BR"')] if admin else []
                return '401 Unauthorized', 'application/json', json_bytes({'error': 'Acesso recusado.'}), extra
            if method == 'POST':
                origin = environ.get('HTTP_ORIGIN')
                if origin and origin != self.public_origin:
                    raise ServiceError('Origem da solicitação recusada.', '403 Forbidden')
                payload = self.body(environ)
            else:
                payload = {}
            # Older deployments get the additional table in the existing write transaction.
            db.execute(WINDOW_SCHEMA)
            self.prune(db)
            if admin:
                assets = {'/': ('panel.html', 'text/html; charset=utf-8'),
                          '/panel.js': ('panel.js', 'application/javascript; charset=utf-8'),
                          '/panel.css': ('panel.css', 'text/css; charset=utf-8')}
                if method == 'GET' and path in assets:
                    filename, media = assets[path]
                    return '200 OK', media, (FILES / filename).read_bytes(), []
                if method == 'GET' and path == '/v1/admin/status':
                    result = self.dashboard(db)
                    result['operator_role'] = actor['role']
                elif method == 'POST' and path == '/v1/admin/action':
                    action = payload.get('action')
                    if not isinstance(action, str):
                        raise ServiceError('Operação desconhecida.')
                    allowed = {
                        'release': {'pilot', 'promote', 'pause', 'resume', 'retire',
                                    'set-window', 'clear-window'},
                        'support': {'diagnostic', 'delete-diagnostic'},
                        'audit': set(),
                    }
                    if actor['role'] != 'admin' and action not in allowed.get(actor['role'], set()):
                        raise ServiceError('O papel deste operador não permite a ação.', '403 Forbidden')
                    result = self.change(db, actor['name'], payload)
                elif method == 'POST' and path == '/v1/admin/report':
                    if actor['role'] not in ('admin', 'support'):
                        raise ServiceError('O papel deste operador não permite consultar relatórios.', '403 Forbidden')
                    identifier = checked(payload.get('request_id'), REQUEST_ID, 'Solicitação inválida.')
                    report = db.execute('SELECT report FROM diagnostics WHERE id=? AND state=?',
                                        (identifier, 'received')).fetchone()
                    if not report:
                        raise ServiceError('Relatório não encontrado.', '404 Not Found')
                    self.audit(db, actor['name'], 'diagnóstico consultado', identifier)
                    result = json.loads(report['report'])
                else:
                    raise ServiceError('Operação desconhecida.', '404 Not Found')
            else:
                try:
                    result = self.client(db, actor, method, path, payload)
                except ServiceError as error:
                    # A valid authenticated request confirms contact, even if a wave is paused.
                    if path in ('/v1/manifest', '/v1/policy') and error.status == '409 Conflict':
                        return error.status, 'application/json', json_bytes({'error': str(error)}), []
                    raise
            if isinstance(result, bytes):
                return '200 OK', 'application/octet-stream', result, []
            return '200 OK', 'application/json', json_bytes(result), []

    def __call__(self, environ, start_response):
        try:
            status, content_type, body, extra = self.dispatch(environ)
        except ServiceError as error:
            status, content_type, body, extra = error.status, 'application/json', json_bytes({'error': str(error)}), []
        except sqlite3.IntegrityError:
            status, content_type, body, extra = ('409 Conflict', 'application/json',
                json_bytes({'error': 'Já existe uma operação pendente para este item.'}), [])
        except (ValueError, UnicodeError, RecursionError):
            status, content_type, body, extra = ('400 Bad Request', 'application/json',
                json_bytes({'error': 'Dados inválidos.'}), [])
        except (OSError, sqlite3.Error, subprocess.SubprocessError):
            status, content_type, body, extra = ('503 Service Unavailable', 'application/json',
                json_bytes({'error': 'Serviço indisponível.'}), [])
        start_response(status, [
            ('Content-Type', content_type), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer'),
            ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; "
             "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
            *extra,
        ])
        return [body]


def gpg_signer(home, key):
    if not re.fullmatch(r'[A-Fa-f0-9]{40}', key):
        raise ValueError('Informe a impressão digital da chave de assinatura.')

    def sign(payload):
        return subprocess.run(['/usr/bin/gpg', '--homedir', home, '--batch', '--no-tty',
                               '--local-user', key, '--compress-algo', 'none',
                               '--output', '-', '--sign'],
                              input=payload, capture_output=True, check=True, timeout=8).stdout
    return sign


def application(environ, start_response):
    service = Service(os.environ['LINUXBR_WAVE_DB'],
                      gpg_signer(os.environ['LINUXBR_WAVE_GNUPG'], os.environ['LINUXBR_WAVE_KEY']),
                      os.environ['LINUXBR_WAVE_ORIGIN'])
    return service(environ, start_response)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Administrar o serviço de ondas do Linux BR')
    parser.add_argument('--database', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init').add_argument('organization')
    operator = commands.add_parser('operator')
    operator.add_argument('name')
    operator.add_argument('--role', choices=sorted(ROLES), default='admin')
    device = commands.add_parser('device')
    device.add_argument('name')
    device.add_argument('wave', choices=sorted(WAVES))
    stage = commands.add_parser('stage')
    stage.add_argument('revision')
    stage.add_argument('archives', nargs='+', type=Path)
    policy = commands.add_parser('stage-policy')
    policy.add_argument('name')
    policy.add_argument('file', type=Path)
    commands.add_parser('purge')
    args = parser.parse_args(argv)
    service = Service(args.database)
    try:
        if args.command == 'init':
            service.initialize(args.organization)
        elif args.command in ('operator', 'device'):
            print(service.register(args.name, getattr(args, 'wave', None), getattr(args, 'role', 'admin')))
        elif args.command == 'stage':
            service.stage(args.revision, args.archives)
        elif args.command == 'stage-policy':
            with args.file.open('rb') as stream:
                raw = stream.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise ServiceError('Perfil de política grande demais.')
            service.stage_policy(args.name, json.loads(raw))
        else:
            with closing(service.connect()) as db, db:
                service.prune(db)
    except (OSError, ValueError, sqlite3.Error, RecursionError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
