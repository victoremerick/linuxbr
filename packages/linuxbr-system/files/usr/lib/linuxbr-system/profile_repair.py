"""Preview a clean Plasma session and repair selected preferences before login."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from uuid import uuid4

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
STATE = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'linuxbr' / 'profile-repair'
FILES = {'panel': ('plasmashellrc', 'plasma-org.kde.plasma.desktop-appletsrc'),
         'windows': ('kwinrc', 'kwinrulesrc')}
BACKUP = re.compile(r'\d{8}-\d{6}-[0-9a-f]{8}')


def writable_private(directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('Diretório de preferências sem proteção da sua conta.')


def safe_data(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o022 or info.st_size > 16 * 1024 ** 2):
            raise ValueError('Arquivo de configuração fora do escopo do reparo.')
        return stream.read(16 * 1024 ** 2 + 1)


def put(path, data):
    if data is None:
        path.unlink(missing_ok=True)
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def saved():
    try:
        return [item.name for item in sorted(STATE.iterdir(), reverse=True)
                if BACKUP.fullmatch(item.name) and item.is_dir() and not item.is_symlink()][:25]
    except OSError:
        return []


def queue(groups, choice='defaults'):
    names = list(dict.fromkeys(groups))
    if not names or any(name not in FILES for name in names) or choice not in ['defaults', *saved()]:
        raise ValueError('Selecione as preferências e uma ação válidas.')
    writable_private(STATE)
    put(STATE / 'pending.json', json.dumps({'groups': names, 'choice': choice}).encode())


def apply():
    pending = STATE / 'pending.json'
    request = safe_data(pending)
    if request is None:
        return
    writable_private(CONFIG)
    writable_private(STATE)
    plan = json.loads(request)
    groups, choice = plan['groups'], plan['choice']
    if not isinstance(groups, list) or not groups or any(name not in FILES for name in groups):
        raise ValueError('Plano de reparo inválido.')
    names = tuple(dict.fromkeys(file for name in groups for file in FILES[name]))
    before = {name: safe_data(CONFIG / name) for name in names}
    if choice == 'defaults':
        after = {name: None for name in names}
    else:
        if not isinstance(choice, str) or not BACKUP.fullmatch(choice) or choice not in saved():
            raise ValueError('Cópia das preferências indisponível.')
        folder = STATE / choice
        writable_private(folder)
        available = json.loads(safe_data(folder / 'files.json') or b'[]')
        after = {name: safe_data(folder / name) for name in names if name in available}
        if not after:
            raise ValueError('A cópia não contém as preferências selecionadas.')
    new = STATE / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8])
    new.mkdir(mode=0o700)
    for name in after:
        put(new / name, before[name])
    put(new / 'files.json', json.dumps(list(after)).encode())
    changed = []
    try:
        for name, data in after.items():
            put(CONFIG / name, data)
            changed.append(name)
        pending.unlink()
    except OSError:
        for name in reversed(changed):
            put(CONFIG / name, before[name])
        raise


def preview():
    required = ('dbus-run-session', 'kwin_wayland', 'plasmashell')
    if any(not shutil.which(executable) for executable in required):
        raise RuntimeError('A sessão de teste requer Plasma e KWin Wayland instalados.')
    if not (os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')):
        raise RuntimeError('Abra a sessão de teste a partir da área de trabalho.')
    with tempfile.TemporaryDirectory(prefix='linuxbr-perfil-') as directory:
        env = os.environ.copy()
        for variable, name in (('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'),
                               ('XDG_STATE_HOME', 'state'), ('XDG_DATA_HOME', 'data')):
            target = Path(directory) / name
            target.mkdir(mode=0o700)
            env[variable] = str(target)
        for variable in ('SESSION_MANAGER', 'KDE_FULL_SESSION', 'DBUS_SESSION_BUS_ADDRESS'):
            env.pop(variable, None)
        env.update(QT_QPA_PLATFORM='wayland', XDG_SESSION_TYPE='wayland')
        args = ['dbus-run-session', '--', 'kwin_wayland', '--width', '1024', '--height', '640',
                '--socket', 'linuxbr-preview-' + uuid4().hex, '--no-global-shortcuts',
                '--exit-with-session', '/usr/bin/plasmashell']
        if subprocess.run(args, env=env, check=False).returncode:
            raise RuntimeError('O compositor não conseguiu abrir o perfil de teste.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('apply', 'preview'))
    args = parser.parse_args()
    try:
        (apply if args.action == 'apply' else preview)()
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
