#!/usr/bin/python3
"""Create configured system restore points before critical APT upgrades."""
import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid

from update_waves import authorize

CONFIG = Path('/etc/timeshift/timeshift.json')
POLICY = Path('/etc/linuxbr/recovery-policy.json')
STATE = Path('/var/lib/linuxbr/recovery')
LIVE = Path('/run/live/medium')
RUNTIME = Path('/run/linuxbr-recovery')
IMPORTANT = re.compile(r'^(linuxbr-|linux-image-|linux-headers-|plasma-|kwin-|kio6$|libkf6kio|libc6$|systemd$|apt$|dpkg$)')
REVISION = re.compile(r'[A-Za-z0-9._-]{1,80}')
PACKAGE = re.compile(r'[a-z0-9][a-z0-9+.-]{0,127}')
VERSION = re.compile(r'[0-9][A-Za-z0-9.+~:-]{0,127}')
ARCHITECTURE = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
HOLD_FILE = 'held-revisions.json'
RESTORED_FILE = 'restored-revisions.json'
DPKG_STATUS = Path('/var/lib/dpkg/status')
SYSTEM_PATH = '/usr/sbin:/usr/bin:/sbin:/bin'


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
    try:
        result['held_revisions'] = held_revisions()
    except (OSError, ValueError):
        result['held_revisions'] = None
    return result


def save_state(data):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o755)
    if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o022:
        raise ValueError('Diretório de recuperação com permissões inválidas.')
    data['time'] = datetime.now(timezone.utc).isoformat()
    destinations = ['last.json'] + (['last-success.json'] if data.get('status') == 'created' else [])
    if data.get('revision'):
        destinations.append('last-managed.json')
    for name in destinations:
        temporary = STATE / (name + '.new')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output)
        temporary.replace(STATE / name)


def read_revisions(name, directory):
    directory = STATE if directory is None else directory
    path = directory / name
    try:
        path.lstat()
    except FileNotFoundError:
        return []
    data = read_json(path, strict=True)
    revisions = data.get('revisions')
    if data.get('schema') != 1 or not isinstance(revisions, list) or any(
            not isinstance(revision, str) or not REVISION.fullmatch(revision)
            for revision in revisions):
        raise ValueError('Lista de revisões de recuperação inválida.')
    return revisions


def held_revisions(directory=None):
    return read_revisions(HOLD_FILE, directory)


def restored_revisions(directory=None):
    return read_revisions(RESTORED_FILE, directory)


def write_revisions(name, revisions, directory):
    directory = STATE if directory is None else directory
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != 0 or directory.stat().st_mode & 0o022:
        raise ValueError('Diretório de recuperação com permissões inválidas.')
    fd, temporary_name = tempfile.mkstemp(dir=directory, prefix='.revisions-')
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, 'w') as output:
            os.fchmod(output.fileno(), 0o644)
            json.dump({'schema': 1, 'revisions': sorted(set(revisions))}, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(directory / name)
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def save_holds(revisions, directory=None):
    write_revisions(HOLD_FILE, revisions, directory)


def save_restored_revisions(revisions, directory=None):
    write_revisions(RESTORED_FILE, revisions, directory)


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


def archive_targets(lines):
    targets = {}
    for line in lines:
        fields = subprocess.check_output(['/usr/bin/dpkg-deb', '-f', line.strip(),
            'Package', 'Version', 'Architecture'], text=True, timeout=20)
        metadata = dict(item.split(': ', 1) for item in fields.splitlines() if ': ' in item)
        package, version, arch = (metadata.get(field, '') for field in ('Package', 'Version', 'Architecture'))
        if (not PACKAGE.fullmatch(package) or not VERSION.fullmatch(version) or not ARCHITECTURE.fullmatch(arch)
                or (package, arch) in targets or len(targets) >= 4096):
            raise ValueError('O lote autorizado contém metadados de pacote inválidos ou repetidos.')
        targets[package, arch] = {'package': package, 'version': version, 'architecture': arch}
    return list(targets.values())


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


@contextmanager
def checksum_rsync_environment():
    """Compare content when distinct package builds share size and timestamps."""
    with tempfile.TemporaryDirectory(prefix='rsync-', dir=RUNTIME) as directory:
        hook = Path(directory) / 'timeshift-bash'
        results = Path(directory) / 'exit-codes'
        # Timeshift launches noninteractive Bash scripts. The hook is sourced,
        # so it also works when /run is mounted noexec.
        hook.write_text('rsync() {\n    local linuxbr_rsync_code\n    /usr/bin/rsync --checksum "$@"\n'
                        '    linuxbr_rsync_code=$?\n'
                        f'    printf "%s\\n" "$linuxbr_rsync_code" >> \'{results}\'\n'
                        '    return "$linuxbr_rsync_code"\n}\n')
        yield {'BASH_ENV': str(hook)}, results


def rsync_completed(results):
    try:
        codes = results.read_text().splitlines()
    except FileNotFoundError:
        return False
    return bool(codes) and all(code == '0' for code in codes)


def before_upgrade(lines):
    if LIVE.exists() or Path('/.live-build').exists():
        return 0
    lines = list(lines)
    revision = authorize(lines)
    if revision is not None and revision in held_revisions():
        raise ValueError('A revisão '+revision+' está suspensa neste computador.')
    targets = archive_targets(lines) if revision is not None else []
    packages = sorted({target['package'] for target in targets}) if targets else critical_upgrades(lines)
    if not packages and revision is None:
        return 0
    policy = read_json(POLICY, strict=True)
    if type(policy.get('before_critical_updates', True)) is not bool:
        raise ValueError('Política de recuperação inválida.')
    if policy.get('before_critical_updates', True) is not True:
        if revision is not None:
            raise ValueError('A onda exige a proteção automática de recuperação.')
        save_state({'status': 'disabled', 'packages': packages})
        return 0
    config = read_json(CONFIG, strict=True)
    if not config or config.get('backup_device_uuid', '') == '':
        if revision is not None:
            raise ValueError('Configure o destino de recuperação antes de instalar esta onda.')
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
        if revision is None:
            return create_snapshot(packages)
        previous = held_revisions()
        if revision in previous:
            raise ValueError('A revisão '+revision+' está suspensa neste computador.')
        # The rollback point itself carries the hold, even if recovery is interrupted
        # after Timeshift has replaced the package database.
        save_holds([*previous, revision])
        try:
            return create_snapshot(packages, revision, targets)
        finally:
            save_holds(previous)


def create_snapshot(packages, revision=None, targets=None):
    transaction = {'packages': packages}
    comment = 'Linux BR: antes de atualização importante'
    if revision is not None:
        transaction['revision'] = revision
        transaction['targets'] = targets or []
        comment = f'Linux BR: antes da revisão {revision} ({uuid.uuid4().hex})'
        transaction['point_comment'] = comment
        with DPKG_STATUS.open('rb') as database:
            transaction['dpkg_status_sha256'] = hashlib.file_digest(database, 'sha256').hexdigest()
    try:
        environment = checksum_rsync_environment() if revision is not None else nullcontext(({}, None))
        with environment as (extra, results):
            result = subprocess.run(['/usr/bin/timeshift', '--create', '--scripted',
                                     '--comments', comment], env={**os.environ, 'PATH': SYSTEM_PATH, **extra},
                                    timeout=7200, check=False)
            completed = results is None or rsync_completed(results)
    except (OSError, subprocess.SubprocessError):
        save_state({'status': 'failed', **transaction})
        raise
    if result.returncode or not completed:
        save_state({'status': 'failed', **transaction, 'code': result.returncode})
        print('Linux BR: atualização interrompida porque o ponto de restauração falhou. '
              'Confira o destino e o espaço no Timeshift e tente novamente.', file=sys.stderr)
        return 1
    save_state({'status': 'created', **transaction})
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'apt', 'release-hold'])
    parser.add_argument('--revision')
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps(status(), ensure_ascii=False)); return 0
    if os.geteuid() != 0:
        parser.exit(1, 'A operação APT exige autenticação administrativa.\n')
    os.environ['PATH'] = SYSTEM_PATH
    try:
        if args.action == 'release-hold':
            if LIVE.exists() or not args.revision or not REVISION.fullmatch(args.revision):
                raise ValueError('Informe uma revisão válida a partir do sistema instalado.')
            with snapshot_lock():
                restored = restored_revisions()
                if args.revision in restored:
                    save_restored_revisions([revision for revision in restored if revision != args.revision])
                save_holds([revision for revision in held_revisions() if revision != args.revision])
            return 0
        return before_upgrade(sys.stdin)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Linux BR: proteção da atualização não concluída. ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
