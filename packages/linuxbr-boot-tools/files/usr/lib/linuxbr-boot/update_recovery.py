"""Inspect and restore the last managed Timeshift point from live media."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, '/usr/lib/linuxbr-system')
from snapshot_service import (LIVE, REVISION, checksum_rsync_environment, held_revisions,
                              restored_revisions, rsync_completed, save_holds,
                              save_restored_revisions, snapshot_lock)


UUID = re.compile(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}')
POINT = re.compile(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}')
HASH = re.compile(r'[a-f0-9]{64}')
STATE = 'var/lib/linuxbr/recovery'
STATUS = 'var/lib/dpkg/status'
TOOLS = '/usr/sbin:/usr/bin:/sbin:/bin'


def command(*argv, timeout=15):
    return subprocess.check_output(argv, text=True, timeout=timeout,
                                   env={'PATH': TOOLS, 'LC_ALL': 'C'})


def disks():
    return json.loads(command('/usr/bin/lsblk', '--json', '--paths', '--list', '--output',
        'PATH,TYPE,FSTYPE,UUID,RO,MOUNTPOINTS,PKNAME,MAJ:MIN'))['blockdevices']


def available(device):
    return (device['type'] == 'part' and not device['ro'] and
            not any(device['mountpoints'] or []) and
            re.fullmatch(r'/dev/[A-Za-z0-9_.+-]+', device['path']))


def device_for(items, uuid, filesystem):
    matches = [device for device in items if (device['uuid'] or '').lower() == uuid.lower()]
    if len(matches) != 1:
        raise ValueError('UUID ausente ou duplicado. Confira os discos conectados.')
    device = matches[0]
    if not available(device) or device['fstype'] != filesystem:
        raise ValueError('O dispositivo deve ser uma partição '+filesystem+' desmontada.')
    return device


def trusted(base, relative, directory=False, root_group_mount=False):
    """Never follow links or load data from user-writable snapshot paths."""
    path = base
    parts = Path(relative).parts
    for index, part in enumerate(parts):
        path = path / part
        info = path.lstat()
        expected = stat.S_ISDIR if directory or index < len(parts) - 1 else stat.S_ISREG
        mask = 0o002 if root_group_mount and index == len(parts) - 1 and info.st_gid == 0 else 0o022
        if not expected(info.st_mode) or info.st_uid != 0 or info.st_mode & mask:
            raise ValueError('Caminho sem proteção administrativa no ponto ou na instalação. '
                             + '/'.join(parts[:index + 1]))
    return path


def read(base, relative, limit=128 * 1024):
    with trusted(base, relative).open('rb') as source:
        value = source.read(limit + 1)
    if len(value) > limit:
        raise ValueError('Metadados da recuperação excedem o limite.')
    return value


def read_object(base, relative):
    value = json.loads(read(base, relative))
    if not isinstance(value, dict):
        raise ValueError('Metadados de recuperação inválidos.')
    return value


def identifier(base, relative):
    return hashlib.sha256(read(base, relative, 32 * 1024 * 1024)).hexdigest()


@contextmanager
def mounted(device, writable=False):
    options = 'rw,nosuid,nodev,noexec' if writable else 'ro,noload,nosuid,nodev,noexec'
    path = Path(tempfile.mkdtemp(prefix='linuxbr-update-', dir='/run'))
    directory = str(path)
    try:
        command('/usr/bin/mount', '-t', 'ext4', '-o', options, 'UUID='+device['uuid'], directory)
        try:
            yield path
        finally:
            command('/usr/bin/umount', directory)
    finally:
        # A failed unmount must never cause recursive cleanup of the installed system.
        try:
            path.rmdir()
        except OSError:
            pass


def layout(items, root, fstab):
    """Accept Calamares ext4 with optional EFI and swap on the same disk."""
    found = set()
    for line in fstab.decode().splitlines():
        fields = line.partition('#')[0].split()
        if not fields:
            continue
        if len(fields) != 6:
            raise ValueError('Tabela de partições inválida.')
        source, target, kind = fields[:3]
        if (source, target, kind) == ('tmpfs', '/tmp', 'tmpfs'):
            continue
        if not source.startswith('UUID='):
            raise ValueError('O assistente exige partições do sistema identificadas por UUID.')
        uuid = source.removeprefix('UUID=')
        if target == '/' and kind == 'ext4' and uuid.lower() == root['uuid'].lower() and target not in found:
            found.add(target)
            continue
        if target == '/boot/efi' and kind == 'vfat' and target not in found:
            device = device_for(items, uuid, 'vfat')
            found.add(target)
        elif target in ('none', 'swap') and kind == 'swap':
            # Swap is skipped by the Timeshift restore and must still belong to this disk.
            matches = [entry for entry in items if entry['uuid'] == uuid and entry['fstype'] == 'swap']
            if len(matches) != 1:
                raise ValueError('Partição swap ausente ou ambígua.')
            device = matches[0]
        else:
            raise ValueError('Layout de partições fora do escopo do assistente.')
        if device['pkname'] != root['pkname']:
            raise ValueError('As partições auxiliares devem pertencer ao disco do sistema.')
    if '/' not in found or (('/boot/efi' in found) != Path('/sys/firmware/efi').is_dir()):
        raise ValueError('Inicie a mídia no mesmo modo BIOS ou UEFI da instalação.')


def verify_snapshot(backup, point, install, fstab, machine, uuid):
    revision, comment = install.get('revision'), install.get('point_comment')
    expected = install.get('dpkg_status_sha256')
    if (install.get('status') != 'created' or not isinstance(revision, str)
            or not REVISION.fullmatch(revision) or not isinstance(comment, str)
            or not isinstance(expected, str) or not HASH.fullmatch(expected)):
        raise ValueError('O último ponto automático não possui metadados de recuperação guiada.')
    info = read_object(backup, point + '/info.json')
    if (info.get('comments') != comment or info.get('type') != 'rsync'
            or str(info.get('sys-uuid', '')).lower() != uuid.lower()):
        raise ValueError('O ponto não corresponde à instalação e revisão selecionadas.')
    folder = trusted(backup, point + '/localhost', directory=True)
    exclusions = set(read(backup, point + '/exclude.list').decode().splitlines())
    if (not {'/home/*/**', '/root/**'} <= exclusions
            or any(line.lstrip().startswith('+') for line in exclusions)):
        raise ValueError('O ponto não comprova a exclusão das pastas pessoais.')
    if (read(folder, 'etc/fstab') != fstab or read(folder, 'etc/machine-id') != machine
            or identifier(folder, STATUS) != expected):
        raise ValueError('Identidade, partições ou banco de pacotes do ponto não conferem.')
    if revision not in held_revisions(trusted(folder, STATE, directory=True)):
        raise ValueError('O ponto não contém a suspensão local da revisão.')
    return folder


def inspect(uuid):
    items = disks()
    root = device_for(items, uuid, 'ext4')
    with mounted(root) as target:
        if b'ID=linuxbr' not in read(target, 'usr/lib/os-release').splitlines():
            raise ValueError('A partição não contém uma instalação Linux BR.')
        config = read_object(target, 'etc/timeshift/timeshift.json')
        backup_uuid = config.get('backup_device_uuid')
        if not isinstance(backup_uuid, str) or not UUID.fullmatch(backup_uuid) or backup_uuid.lower() == uuid.lower():
            raise ValueError('Selecione no Timeshift um destino de pontos em outra partição ext4.')
        backup = device_for(items, backup_uuid, 'ext4')
        state = trusted(target, STATE, directory=True)
        current_holds = held_revisions(state)
        prior_restores = restored_revisions(state)
        install = read_object(target, STATE + '/last-success.json')
        fstab = read(target, 'etc/fstab')
        machine = read(target, 'etc/machine-id')
        layout(items, root, fstab)
        if '/boot/efi' in fstab.decode():
            # Calamares leaves the EFI mount point group-writable for the root group.
            trusted(target, 'boot/efi', directory=True, root_group_mount=True)
        current = identifier(target, STATUS)
    comment = install.get('point_comment')
    if not comment:
        raise ValueError('A instalação não tem um ponto automático associado a uma revisão.')
    with mounted(backup) as volume:
        snapshots = trusted(volume, 'timeshift/snapshots', directory=True)
        matches = []
        for entry in snapshots.iterdir():
            if POINT.fullmatch(entry.name):
                point = 'timeshift/snapshots/' + entry.name
                try:
                    info = read_object(volume, point + '/info.json')
                except FileNotFoundError:
                    continue  # Timeshift may leave an incomplete point after interruption.
                if info.get('comments') == comment:
                    matches.append((entry.name, point))
        if len(matches) != 1:
            raise ValueError('O ponto automático correspondente não foi localizado com segurança.')
        name, point = matches[0]
        folder = verify_snapshot(volume, point, install, fstab, machine, uuid)
        release = read(folder, 'usr/lib/os-release').decode()
        version = next((line.split('=', 1)[1].strip('"') for line in release.splitlines()
                        if line.startswith('VERSION_ID=')), None)
        if not version or not REVISION.fullmatch(version.replace('~', '-')):
            raise ValueError('A versão armazenada no ponto não pôde ser identificada.')
    return {'target': root, 'backup': backup, 'point': name, 'revision': install['revision'],
            'packages': install.get('packages', []), 'version': version,
            'held': current_holds, 'verified_restores': prior_restores, 'current_status': current,
            'restored_status': install['dpkg_status_sha256']}


def plan_token(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def restore(uuid, token):
    with snapshot_lock():
        plan = inspect(uuid)
        if plan_token(plan) != token:
            raise ValueError('O estado mudou desde a revisão. Consulte o ponto novamente.')
        holds = [*plan['held'], plan['revision']]
        target, backup = plan['target'], plan['backup']
        with mounted(target, writable=True) as directory:
            save_holds(holds, trusted(directory, STATE, directory=True))
        argv = ['/usr/bin/unshare', '--mount', '--propagation', 'private', '--',
                '/usr/bin/timeshift', '--restore', '--rsync', '--snapshot', plan['point'],
                '--snapshot-device', 'UUID='+backup['uuid'], '--target', target['uuid'],
                '--skip-grub', '--scripted', '--yes', '--quiet']
        with checksum_rsync_environment() as (extra, results):
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, check=False,
                                    env={'PATH': TOOLS, 'LC_ALL': 'C', **extra})
            completed = rsync_completed(results)
        if result.returncode or not completed:
            raise ValueError('Timeshift não concluiu a restauração. Confira a instalação pela mídia live.')
        target = device_for(disks(), uuid, 'ext4')
        with mounted(target, writable=True) as directory:
            state = trusted(directory, STATE, directory=True)
            save_holds(holds, state)
            if identifier(directory, STATUS) != plan['restored_status']:
                raise ValueError('A base de pacotes restaurada não confere. Mantenha a mídia live aberta.')
            save_restored_revisions([*plan['verified_restores'], plan['revision']], state)
        print('Banco de pacotes restaurado. A revisão '+plan['revision']+' permanece suspensa.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['devices', 'inspect', 'restore'])
    parser.add_argument('--uuid')
    parser.add_argument('--confirm')
    args = parser.parse_args()
    try:
        if not LIVE.is_dir():
            raise ValueError('A restauração guiada requer a mídia live do Linux BR.')
        if args.action == 'devices':
            print(json.dumps([item for item in disks() if available(item) and item['fstype'] == 'ext4'
                              and isinstance(item['uuid'], str) and UUID.fullmatch(item['uuid'])]))
            return 0
        if os.geteuid() != 0 or not args.uuid or not UUID.fullmatch(args.uuid):
            raise ValueError('Autorização administrativa e UUID de destino são obrigatórios.')
        if args.action == 'inspect':
            plan = inspect(args.uuid)
            print(json.dumps({'plan': plan, 'token': plan_token(plan)}, ensure_ascii=False))
        else:
            if not args.confirm or not HASH.fullmatch(args.confirm):
                raise ValueError('Confirme primeiro o plano de restauração.')
            restore(args.uuid, args.confirm)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
