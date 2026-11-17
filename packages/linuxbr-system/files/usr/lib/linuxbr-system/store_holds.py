"""Temporary pauses for updates started through the Loja."""
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path

from store_sources import atomic_write


def path():
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    return config/'linuxbr/store-pauses.json'


def key(target):
    identity = target['target']
    origin = target['origin']
    # Managers can resolve the same installed instance to a full ref.
    if target['manager'] == 'flatpak':
        identity = identity.split('/')[0]
    elif target['manager'] == 'deb':
        identity = identity.split(':')[0]
        origin = ''
    return json.dumps([target['manager'], target['scope'], origin, identity])


def entries():
    try:
        value = json.loads(path().read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def active(target, now=None):
    row = entries().get(key(target))
    if not isinstance(row, dict):
        return None
    try:
        until = datetime.fromisoformat(row['until'])
        if until.tzinfo and until > (now or datetime.now(timezone.utc)):
            reason = row.get('reason', '')
            return until, reason[:180] if isinstance(reason, str) else ''
    except (KeyError, ValueError, TypeError):
        pass
    return None


def change(target, days, reason=''):
    if type(days) is not int or not 0 <= days <= 90:
        raise ValueError('Escolha até 90 dias de pausa.')
    reason = ' '.join(reason.split())[:180]
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with file.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = entries()
        identity = key(target)
        if days:
            until = datetime.now(timezone.utc) + timedelta(days=days)
            data[identity] = {'until': until.isoformat(), 'reason': reason}
        else:
            data.pop(identity, None)
        atomic_write(file, json.dumps(data, ensure_ascii=False).encode('utf-8'), mode=0o600)


def description(hold):
    until, reason = hold
    suffix = ' · ' + reason if reason else ''
    return 'Atualização pausada na Loja até ' + until.astimezone().strftime('%d/%m/%Y às %H:%M') + suffix
