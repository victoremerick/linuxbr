"""Grant named SSH accounts a fixed set of power actions on specific VMs."""

import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from uuid import UUID


POLICY = Path('/etc/sudoers.d')
EXECUTABLE = '/usr/bin/linuxbr-vm-operator'
USERNAME = re.compile(r'[a-z_][a-z0-9_-]{0,30}')
ACTIONS = {'estado': 'domstate', 'ligar': 'start', 'desligar': 'shutdown',
           'reiniciar': 'reboot', 'pausar': 'suspend', 'retomar': 'resume'}


def evaluate_user(value):
    if not USERNAME.fullmatch(value):
        raise ValueError('Informe uma conta local válida.')
    user = pwd.getpwnam(value)
    if user.pw_uid < 1000 or user.pw_uid == 65534:
        raise ValueError('Escolha uma conta de operador comum.')
    return user.pw_name


def virsh(action, identifier):
    return subprocess.run(['/usr/bin/virsh', '--connect', 'qemu:///system', action, identifier],
                          check=True, capture_output=True, text=True, timeout=30).stdout.strip()


def rule(user, identifier):
    commands = ', '.join(f'{EXECUTABLE} {action} {identifier}' for action in ACTIONS)
    return f'{user} ALL=(root) NOPASSWD: {commands}\n'


def change(operation, account, identifier):
    if os.geteuid() != 0:
        raise PermissionError('A delegação exige autorização administrativa.')
    user = evaluate_user(account)
    identifier = str(UUID(identifier))
    path = POLICY / ('linuxbr-vm-' + user + '-' + identifier)
    fd = os.open(POLICY / '.linuxbr-vm.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if operation == 'revogar':
            path.unlink(missing_ok=True)
            return
        virsh('dominfo', identifier)
        with NamedTemporaryFile(mode='w', prefix='.linuxbr-vm-', dir=POLICY, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(rule(user, identifier))
                handle.flush()
                os.fchmod(handle.fileno(), 0o440)
                subprocess.run(['/usr/sbin/visudo', '-cf', str(temporary)],
                               capture_output=True, check=True, timeout=10)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)


def main(argv):
    if len(argv) == 3 and argv[0] in ('conceder', 'revogar'):
        change(*argv)
        print('Delegação atualizada.')
        return
    if len(argv) != 2 or argv[0] not in ACTIONS:
        raise ValueError('Use estado, ligar, desligar, reiniciar, pausar ou retomar, seguido do UUID da VM.')
    action, identifier = argv
    if os.geteuid() != 0:
        raise PermissionError('Use sudo para executar a ação delegada.')
    identifier = str(UUID(identifier))
    if action == 'ligar':
        from xml.etree import ElementTree
        root = ElementTree.fromstring(virsh('dumpxml', identifier))
        if root.find('metadata/{https://linuxbr.local/vm-state}restore') is not None:
            raise ValueError('Conclua a restauração pendente antes de iniciar a VM.')
    print(virsh(ACTIONS[action], identifier))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
