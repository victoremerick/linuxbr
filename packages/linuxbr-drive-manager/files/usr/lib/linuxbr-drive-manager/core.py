"""Storage model and per-user drive aliases. No privileged operations here."""
import fcntl
import json
import os
import string
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, quote, unquote

PREFIX = 'org.freedesktop.UDisks2.'
LETTERS = string.ascii_uppercase[3:]


def smb_url(text):
    text = text.strip().replace('\\', '/')
    if text.startswith('//'):
        text = 'smb:' + text
    p = urlsplit(text)
    if (p.scheme.lower() != 'smb' or not p.hostname or p.username is not None
            or p.password is not None or p.query or p.fragment or not p.path.strip('/')):
        raise ValueError('Use smb://servidor/compartilhamento, sem usuário ou senha na URL.')
    if any(ord(c) < 32 for c in text) or p.port is not None:
        raise ValueError('Endereço SMB inválido; não informe porta ou caracteres de controle.')
    path = quote(unquote(p.path).rstrip('/'), safe='/')
    if any(c in unquote(p.path) for c in ['\x00', '\n', '\r']):
        raise ValueError('Endereço SMB inválido.')
    return urlunsplit(('smb', p.netloc.lower(), path, '', ''))


def decode(value):
    return bytes(value).rstrip(b'\0').decode('utf-8', errors='replace')


def inventory(objects):
    rows = [dict(key='system', name='Sistema', kind='Sistema', device='', size=0,
                 mounts=['/'], path='', fs='', protected=True)]
    for path, interfaces in objects.items():
        block = interfaces.get(PREFIX + 'Block')
        if not block or block.get('HintIgnore'):
            continue
        drive = objects.get(str(block.get('Drive')), {}).get(PREFIX + 'Drive', {})
        fs = interfaces.get(PREFIX + 'Filesystem')
        mounts = [decode(m) for m in fs.get('MountPoints', [])] if fs is not None else []
        partition = interfaces.get(PREFIX + 'Partition', {})
        topology = dict(parent=str(partition.get('Table', '')),
                        offset=int(partition.get('Offset', 0)),
                        partition_number=int(partition.get('Number', 0)),
                        table_type=str(interfaces.get(PREFIX + 'PartitionTable', {}).get('Type', '')),
                        is_disk=PREFIX + 'PartitionTable' in interfaces or (not partition and str(block.get('Drive', '/')) != '/'),
                        drive=str(block.get('Drive', '')))
        if '/' in mounts:
            rows[0].update(topology)
            rows[0].update(path=str(path), size=int(block.get('Size', 0)), device=decode(block['Device']), fs=str(block.get('IdType', '')))
            continue
        uuid = str(block.get('IdUUID', ''))
        partition = interfaces.get(PREFIX + 'Partition', {})
        key = ('uuid:' + uuid) if uuid else ('part:' + str(partition['UUID']) if partition.get('UUID') else '')
        removable = bool(drive.get('Removable') or drive.get('ConnectionBus') == 'usb')
        # Include disks/containers as read-only inventory, but assign letters only to filesystems.
        protected = any(m == '/boot' or m.startswith(('/boot/', '/usr', '/var', '/run/live', '/lib', '/etc')) for m in mounts)
        rows.append(dict(key=key if fs is not None else '', path=str(path),
                         name=str(block.get('IdLabel') or drive.get('Model') or decode(block['Device'])).strip(),
                         device=decode(block['Device']), size=int(block.get('Size', 0)),
                         kind='Removível' if removable else ('Volume' if fs is not None else 'Disco / contêiner'),
                         mounts=mounts, fs=str(block.get('IdType', '')), protected=protected,
                         mountable=fs is not None and not protected, **topology))
    # Cloned UUIDs must never silently share an alias.
    keys = [r['key'] for r in rows if r['key']]
    for row in rows:
        if row['key'] and keys.count(row['key']) > 1:
            row['key'] = ''
            row['name'] += ' (identificador duplicado)'
        if not row['key']:
            row['mountable'] = False
    return rows


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'linuxbr/drive-manager.json'

    def update(self, action=lambda data: None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.path) + '.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.exists():
                data = json.loads(self.path.read_text())
                if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('letters'), dict) or not isinstance(data.get('shares'), dict):
                    raise ValueError('Configuração inválida. O arquivo foi preservado: ' + str(self.path))
                values = list(data['letters'].values())
                if any(not isinstance(v, str) or len(v) != 1 or v not in LETTERS for v in values) or len(set(values)) != len(values):
                    raise ValueError('Configuração contém letras inválidas ou repetidas.')
                for url, label in data['shares'].items():
                    if smb_url(url) != url or not isinstance(label, str):
                        raise ValueError('Configuração contém compartilhamento inválido.')
            else:
                data = dict(version=1, letters={}, shares={})
            before = json.dumps(data, sort_keys=True)
            action(data)
            if before != json.dumps(data, sort_keys=True) or not self.path.exists():
                fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix='.drives-')
                try:
                    with os.fdopen(fd, 'w') as stream:
                        json.dump(data, stream, ensure_ascii=False, indent=2)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(tmp, self.path)
                finally:
                    if os.path.exists(tmp): os.unlink(tmp)
            return data

    def assign(self, key, letter):
        if not key or key == 'system' or len(letter) != 1 or letter not in LETTERS:
            raise ValueError('Escolha uma letra entre D e Z para um volume identificável.')
        def action(data):
            if any(k != key and v == letter for k, v in data['letters'].items()):
                raise ValueError('Esta letra já está reservada, inclusive para unidades desconectadas.')
            data['letters'][key] = letter
        return self.update(action)

    def discover(self, rows):
        def action(data):
            for row in rows:
                key = row['key']
                if key and key != 'system' and key not in data['letters'] and not row.get('protected'):
                    available = [c for c in LETTERS if c not in data['letters'].values()]
                    if available: data['letters'][key] = available[0]
        return self.update(action)

    def add_share(self, url, label):
        url = smb_url(url)
        def action(data):
            data['shares'][url] = label.strip() or url
            key = 'smb:' + url
            if key not in data['letters']:
                available = [c for c in reversed(LETTERS) if c not in data['letters'].values()]
                if not available: raise ValueError('Todas as letras estão reservadas.')
                data['letters'][key] = available[0]
        return self.update(action)

    def forget(self, key):
        def action(data):
            data['letters'].pop(key, None)
            if key.startswith('smb:'): data['shares'].pop(key[4:], None)
        return self.update(action)
