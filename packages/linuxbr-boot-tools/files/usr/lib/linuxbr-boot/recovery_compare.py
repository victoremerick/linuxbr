"""Compare system metadata without copying any snapshot data to the installation."""

import hashlib
import os
from pathlib import Path
import stat

from update_recovery import POINT, STATUS, UUID, device_for, disks, mounted, read, read_object, trusted


MAX_CHANGES = 40
MAX_POINTS = 150
MAX_FILES = 6000
CONFIG_AREAS = ('etc/default', 'etc/sysctl.d', 'etc/systemd/system', 'etc/xdg')
CONFIG_SUFFIXES = {'.conf', '.service', '.timer', '.socket', '.target', '.desktop', '.cfg', '.rules', '.ini'}
PLAIN_CONFIGS = {'etc/fstab', 'etc/hostname', 'etc/default/locale', 'etc/default/keyboard', 'etc/default/grub'}


def eligible(backup, name, uuid, machine, fstab):
    if not POINT.fullmatch(name):
        raise ValueError('Ponto de recuperação inválido.')
    point = f'timeshift/snapshots/{name}'
    meta = read_object(backup, point + '/info.json')
    if (meta.get('type') != 'rsync' or str(meta.get('sys-uuid', '')).lower() != uuid.lower()):
        raise ValueError('O ponto pertence a outra instalação ou tipo de cópia.')
    folder = trusted(backup, point + '/localhost', directory=True)
    if read(folder, 'etc/machine-id') != machine or read(folder, 'etc/fstab') != fstab:
        raise ValueError('A identidade e a tabela de volumes do ponto precisam corresponder à instalação.')
    return folder


def installed_packages(raw):
    packages = {}
    for paragraph in raw.decode('utf-8', 'replace').split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines()
                      if line and not line[0].isspace() and ': ' in line)
        if fields.get('Status', '').endswith(' ok installed') and all(
                key in fields for key in ('Package', 'Architecture', 'Version')):
            packages[f"{fields['Package']}:{fields['Architecture']}"] = fields['Version'][:150]
    if not packages:
        raise ValueError('O banco de pacotes do ponto está vazio ou inválido.')
    return packages


def config_entries(folder):
    configurations, services = {}, {}
    walked = 0
    incomplete = False
    for directory in CONFIG_AREAS:
        try:
            base = trusted(folder, directory, directory=True)
        except FileNotFoundError:
            continue
        for root, subdirs, files in os.walk(base, followlinks=False):
            root = Path(root)
            if len(root.relative_to(base).parts) >= 4:
                subdirs.clear()
            for name in sorted(files):
                walked += 1
                if walked > MAX_FILES:
                    return configurations, services, True
                path = root / name
                relative = str(path.relative_to(folder))
                try:
                    parent = trusted(folder, str(root.relative_to(folder)), directory=True)
                    info = path.lstat()
                    if info.st_uid != 0:
                        continue
                    if relative.startswith('etc/systemd/system/') and stat.S_ISLNK(info.st_mode):
                        target = os.readlink(parent / name)
                        if target == '/dev/null':
                            services[relative] = 'Mascarado'
                        elif root.suffix in ('.wants', '.requires'):
                            services[relative] = 'Ativado em ' + root.name.rsplit('.', 1)[0]
                        else:
                            services[relative] = 'Vinculado a ' + Path(target).name
                        continue
                    if path.suffix in CONFIG_SUFFIXES or relative in PLAIN_CONFIGS:
                        configurations[relative] = hashlib.sha256(read(folder, relative, 1024 * 1024)).digest()
                except (OSError, ValueError):
                    incomplete = True
    for relative in PLAIN_CONFIGS - configurations.keys():
        try:
            configurations[relative] = hashlib.sha256(read(folder, relative, 1024 * 1024)).digest()
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            incomplete = True
    return configurations, services, incomplete


def delta(before, after, summarize=False):
    entries = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        item = {'name': key[:220], 'action': 'Alterado' if old is not None and new is not None
                else 'Adicionado' if old is None else 'Removido'}
        if not summarize:
            item.update(before=old, after=new)
        entries.append(item)
    return {'changes': entries[:MAX_CHANGES], 'total': len(entries)}


def compare_folders(before, after):
    packages = [installed_packages(read(folder, STATUS, 32 * 1024 * 1024)) for folder in (before, after)]
    old_config, old_services, old_incomplete = config_entries(before)
    new_config, new_services, new_incomplete = config_entries(after)
    return {'packages': delta(*packages), 'services': delta(old_services, new_services),
            'configuration': delta(old_config, new_config, summarize=True),
            'incomplete_configuration': old_incomplete or new_incomplete}


def compare(uuid, names=()):
    items = disks()
    device = device_for(items, uuid, 'ext4')
    with mounted(device) as target:
        if b'ID=linuxbr' not in read(target, 'usr/lib/os-release').splitlines():
            raise ValueError('A partição não contém uma instalação Linux BR.')
        backup_uuid = read_object(target, 'etc/timeshift/timeshift.json').get('backup_device_uuid')
        if not isinstance(backup_uuid, str) or not UUID.fullmatch(backup_uuid) or backup_uuid.lower() == uuid.lower():
            raise ValueError('Selecione no Timeshift um destino de pontos em outra partição ext4.')
        backup_device = device_for(items, backup_uuid, 'ext4')
        machine, fstab = read(target, 'etc/machine-id'), read(target, 'etc/fstab')
        with mounted(backup_device) as backup:
            if names:
                folders = [eligible(backup, name, uuid, machine, fstab) for name in names]
                return {'before': names[0], 'after': names[1], **compare_folders(*folders)}
            snapshots = trusted(backup, 'timeshift/snapshots', directory=True)
            points = []
            for name in sorted((entry.name for entry in snapshots.iterdir() if POINT.fullmatch(entry.name)),
                               reverse=True)[:MAX_POINTS]:
                try:
                    eligible(backup, name, uuid, machine, fstab)
                except (OSError, ValueError):
                    continue
                points.append(name)
            return points
