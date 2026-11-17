"""Inspect account names and data partition layout before reinstalling."""

from pathlib import PurePosixPath
import re

from update_recovery import UUID, available, device_for, disks, mounted, read

ACCOUNT = re.compile(r'[a-z_][a-z0-9_-]{0,63}\$?', re.I)
PLAIN_PATH = re.compile(r'/[-\w./ ]{1,240}')


def fstab_entries(raw):
    entries = {}
    for line in raw.decode('utf-8', 'strict').splitlines():
        fields = line.partition('#')[0].split()
        if not fields:
            continue
        if len(fields) != 6:
            raise ValueError('A tabela de montagens da instalação está inválida.')
        source, target, filesystem, options = fields[:4]
        target = target.replace(r'\040', ' ')
        if not target.startswith('/') or '..' in PurePosixPath(target).parts:
            continue
        if target in entries:
            raise ValueError('A tabela apresenta dois volumes para o mesmo ponto de montagem.')
        entries[target] = (source, filesystem, set(options.split(',')))
    return entries


def homes(raw):
    accounts = []
    for line in raw.decode('utf-8', 'strict').splitlines():
        fields = line.split(':')
        if len(fields) != 7 or not ACCOUNT.fullmatch(fields[0]) or not fields[2].isascii() or not fields[2].isdigit():
            continue
        uid, name, folder = int(fields[2]), fields[0], fields[5]
        if (1000 <= uid < 60000 and PLAIN_PATH.fullmatch(folder) and
                '..' not in PurePosixPath(folder).parts and
                not folder.startswith('//') and not fields[6].endswith(('/false', '/nologin'))):
            accounts.append((name, uid, str(PurePosixPath(folder))))
    return accounts


def prepare(items, root, fstab, passwd):
    entries = fstab_entries(fstab)
    root_mapping = entries.get('/')
    if (not root_mapping or root_mapping[0].lower() != ('UUID=' + root['uuid']).lower()
            or root_mapping[1] != 'ext4'):
        raise ValueError('O volume raiz selecionado não corresponde ao fstab da instalação.')
    volumes = {}
    users = []
    for name, uid, home in homes(passwd)[:80]:
        matches = ['/']
        matches.extend(path for path in entries if path != '/' and
                       (home == path or home.startswith(path.rstrip('/') + '/')))
        target = max(matches, key=len)
        if target not in volumes:
            source, filesystem, options = entries[target]
            uuid = source.removeprefix('UUID=')
            partitions = [device for device in items
                          if isinstance(device.get('uuid'), str) and device['uuid'].lower() == uuid.lower()]
            independent = (target != '/' and source.startswith('UUID=') and UUID.fullmatch(uuid)
                           and uuid.lower() != root['uuid'].lower() and len(partitions) == 1
                           and partitions[0]['fstype'] == 'ext4' and available(partitions[0])
                           and not {'bind', 'rbind'}.intersection(options))
            volumes[target] = {'mount': target, 'volume': partitions[0]['path'] if independent else '',
                               'kind': 'independent' if independent else
                                       'root' if target == '/' else 'unverified'}
        users.append({'name': name, 'uid': uid, 'home': home, 'mount': target})
    return {'root': root['path'], 'users': users, 'volumes': list(volumes.values())}


def inspect(uuid):
    items = disks()
    root = device_for(items, uuid, 'ext4')
    with mounted(root) as system:
        if b'ID=linuxbr' not in read(system, 'usr/lib/os-release').splitlines():
            raise ValueError('A partição não contém uma instalação Linux BR.')
        return prepare(items, root, read(system, 'etc/fstab'), read(system, 'etc/passwd'))
