#!/usr/bin/python3
"""Create configured system restore points before critical APT upgrades."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

CONFIG = Path('/etc/timeshift/timeshift.json')
POLICY = Path('/etc/linuxbr/recovery-policy.json')
STATE = Path('/var/lib/linuxbr/recovery')
LIVE = Path('/run/live/medium')
RUNTIME = Path('/run/linuxbr-recovery')
IMPORTANT = re.compile(r'^(linuxbr-|linux-image-|linux-headers-|plasma-|kwin-|kio6$|libkf6kio|libc6$|systemd$|apt$|dpkg$)')


def read_json(path, strict=False):
    try:
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError('Permissões inválidas em ' + str(path))
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError('Configuração deve ser um objeto: ' + str(path))
        return data
    except FileNotFoundError:
        if strict and path.is_symlink():
            raise ValueError('Configuração não pode ser um link simbólico: ' + str(path))
        return {}
    except (OSError, ValueError):
        if strict:
            raise ValueError('Revise o arquivo de configuração e suas permissões: ' + str(path))
        return {}


def configuration():
    config = read_json(CONFIG)
    # The destination is selected in Timeshift, never inferred by the hook.
    return valid_destination(config.get('backup_device_uuid'))


def valid_destination(value):
    return (isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9-]{8,64}', value) is not None
            and re.search(r'[a-fA-F0-9]', value) is not None)


def status():
    result = {'configured': configuration(), 'live': LIVE.exists(),
              'automatic': read_json(POLICY).get('before_critical_updates', True) is True}
    try:
        result['last'] = json.loads((STATE / 'last.json').read_text())
    except (OSError, ValueError):
        result['last'] = {}
    if not isinstance(result['last'], dict):
        result['last'] = {}
    try:
        success = json.loads((STATE / 'last-success.json').read_text())
    except (OSError, ValueError):
        success = {}
    result['last_success'] = success if isinstance(success, dict) and success.get('status') == 'created' else (
        result['last'] if result['last'].get('status') == 'created' else {})
    return result


def save_state(data):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o755)
    if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o022:
        raise ValueError('Diretório de recuperação com permissões inválidas.')
    data['time'] = datetime.now(timezone.utc).isoformat()
    destinations = ['last.json'] + (['last-success.json'] if data.get('status') == 'created' else [])
    for name in destinations:
        temporary = STATE / (name + '.new')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output)
        temporary.replace(STATE / name)


def critical_upgrades(lines):
    result = []
    for line in lines:
        path = line.strip()
        if not path or not path.startswith('/') or not path.endswith('.deb'):
            continue
        fields = subprocess.check_output(['/usr/bin/dpkg-deb', '-f', path, 'Package', 'Version'],
                                         text=True, timeout=20)
        metadata = dict(item.split(': ', 1) for item in fields.splitlines() if ': ' in item)
        package, new = metadata.get('Package', ''), metadata.get('Version', '')
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', package) or not IMPORTANT.match(package):
            continue
        old = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${db:Status-Status} ${Version}', package],
                             capture_output=True, text=True, timeout=20)
        installed, _, version = old.stdout.partition(' ')
        if old.returncode == 0 and installed == 'installed' and subprocess.run(
                ['/usr/bin/dpkg', '--compare-versions', new, 'gt', version], check=False).returncode == 0:
            result.append(package)
    return sorted(set(result))


@contextmanager
def snapshot_lock():
    """Create a root-owned runtime directory only when a snapshot is needed."""
    parent = os.open(RUNTIME.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    directory = descriptor = None
    try:
        info = os.fstat(parent)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Diretório temporário de recuperação com permissões inválidas.')
        try:
            os.mkdir(RUNTIME.name, mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
        directory = os.open(RUNTIME.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=parent)
        info = os.fstat(directory)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Diretório temporário de recuperação com permissões inválidas.')
        descriptor = os.open('snapshot.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                             0o600, dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError('Arquivo de bloqueio da recuperação com permissões inválidas.')
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)
        os.close(parent)


def before_upgrade(lines):
    if LIVE.exists() or Path('/.live-build').exists():
        return 0
    packages = critical_upgrades(lines)
    if not packages:
        return 0
    policy = read_json(POLICY, strict=True)
    if type(policy.get('before_critical_updates', True)) is not bool:
        raise ValueError('Política de recuperação inválida.')
    if policy.get('before_critical_updates', True) is not True:
        save_state({'status': 'disabled', 'packages': packages})
        return 0
    config = read_json(CONFIG, strict=True)
    if not config or config.get('backup_device_uuid', '') == '':
        save_state({'status': 'not-configured', 'packages': packages})
        print('Linux BR: configure Pontos de restauração na Central para proteger futuras atualizações.', file=sys.stderr)
        return 0
    if not valid_destination(config.get('backup_device_uuid')):
        raise ValueError('Escolha um destino válido no Timeshift antes de atualizar.')
    mode = config.get('btrfs_mode')
    if mode is not False and mode != 'false' and mode is not None:
        raise ValueError('A proteção automática desta versão requer Timeshift em modo RSYNC.')
    # Preserve separation between system rollback and personal-file backups.
    excludes = config.get('exclude', [])
    if not isinstance(excludes, list) or any(not isinstance(item, str) for item in excludes):
        raise ValueError('Filtros de recuperação inválidos.')
    if any(item.strip().startswith('+') for item in excludes):
        raise ValueError('Revise os filtros do Timeshift: a proteção automática não aceita inclusões pessoais.')
    with snapshot_lock():
        return create_snapshot(packages)


def create_snapshot(packages):
    try:
        result = subprocess.run(['/usr/bin/timeshift', '--create', '--scripted',
                                 '--comments', 'Linux BR: antes de atualização importante'],
                                timeout=7200, check=False)
    except (OSError, subprocess.SubprocessError):
        save_state({'status': 'failed', 'packages': packages})
        raise
    if result.returncode:
        save_state({'status': 'failed', 'packages': packages, 'code': result.returncode})
        print('Linux BR: atualização interrompida porque o ponto de restauração falhou. '
              'Confira o destino e o espaço no Timeshift e tente novamente.', file=sys.stderr)
        return 1
    save_state({'status': 'created', 'packages': packages})
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'apt'])
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps(status(), ensure_ascii=False)); return 0
    if os.geteuid() != 0:
        parser.exit(1, 'A operação APT exige autenticação administrativa.\n')
    os.environ['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    try:
        return before_upgrade(sys.stdin)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Linux BR: proteção da atualização não concluída. ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
