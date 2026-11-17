"""Opt-in exchange of public web app shortcuts through a synchronized folder."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit
from uuid import uuid4

from store_sources import atomic_write
import webapps_backend as backend


SCHEMA = 'linuxbr-webapp-sync-1'
FILE = re.compile(r'linuxbr-webapps-([0-9a-f]{32})\.json')
LIMIT = 256 * 1024


def config():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'linuxbr/webapps-sync.json'


def read_json(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Escolha um arquivo regular para sincronizar.')
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('O arquivo de sincronização excede o tamanho permitido.')
    return json.loads(raw)


def configure(directory):
    path = config()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        identity = read_json(path)['identity']
    except FileNotFoundError:
        identity = uuid4().hex
    if not re.fullmatch('[0-9a-f]{32}', identity):
        raise ValueError('Identificador local inválido.')
    location = Path(directory).resolve(strict=True) if directory else None
    if location is not None and not location.is_dir():
        raise ValueError('Escolha uma pasta sincronizada.')
    atomic_write(path, json.dumps(dict(directory=str(location) if location else '', identity=identity)).encode(), 0o600)


def public_shortcut(row):
    if not isinstance(row, dict) or row.keys() != {'url', 'name'}:
        raise ValueError('Atalho sincronizado inválido.')
    address = backend.clean_url(row['url'])
    service = backend.service_for(address)
    if service:
        return dict(url=backend.clean_url(service['url']), name=service['name'])
    host = urlsplit(address).hostname
    return dict(url=f'https://{host}/', name=host)


def sync():
    if os.geteuid() == 0:
        raise PermissionError('Sincronize atalhos pela sua conta normal.')
    config_path = config()
    try:
        settings = read_json(config_path)
    except FileNotFoundError:
        return 0
    identity = settings['identity']
    if not settings['directory']:
        return 0
    if not re.fullmatch('[0-9a-f]{32}', identity):
        raise ValueError('Identificador local inválido.')
    folder = Path(settings['directory'])
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('A pasta sincronizada está indisponível.')
    fd = os.open(config_path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if read_json(config_path) != settings:
            raise ValueError('A pasta de sincronização mudou. Tente novamente.')
        filename = folder / f'linuxbr-webapps-{identity}.json'
        own_items = {}
        for row in backend.shortcut_records().values():
            item = public_shortcut(row)
            own_items[item['url']] = item
        payload = (json.dumps(dict(schema=SCHEMA, shortcuts=list(own_items.values())), sort_keys=True) + '\n').encode()
        try:
            old = read_json(filename)
        except FileNotFoundError:
            old = None
        if old != json.loads(payload):
            atomic_write(filename, payload, 0o600)
        known = {public_shortcut(row)['url'] for row in backend.shortcut_records(include_hidden=True).values()}
        candidates = {}
        for path in sorted(folder.glob('linuxbr-webapps-*.json'))[:40]:
            if path == filename or not FILE.fullmatch(path.name):
                continue
            try:
                data = read_json(path)
                if not isinstance(data, dict) or data.get('schema') != SCHEMA:
                    continue
                shortcuts = data['shortcuts']
                if not isinstance(shortcuts, list) or len(shortcuts) > 200:
                    continue
                rows = [public_shortcut(row) for row in shortcuts]
            except (OSError, KeyError, ValueError):
                continue
            for item in rows:
                if item['url'] not in known:
                    candidates.setdefault(item['url'], item)
        for item in list(candidates.values())[:max(0, 200 - len(known))]:
            backend.install(item)
        return min(len(candidates), max(0, 200 - len(known)))


if __name__ == '__main__':
    try:
        print(f'Atalhos recebidos e instalados: {sync()}')
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
