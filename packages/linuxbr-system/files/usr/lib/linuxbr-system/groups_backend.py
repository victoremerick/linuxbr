"""Validate and apply local group changes; never operate on domain identities."""
import grp
import pwd
import re
import subprocess
import sys
from pathlib import Path

LOCAL_GROUPS = Path('/etc/group')
LOCAL_USERS = Path('/etc/passwd')
NAME = re.compile(r'[a-z_][a-z0-9_-]{0,31}\Z')
PROTECTED = {'root', 'sudo', 'adm', 'wheel', 'users', 'nogroup', 'systemd-journal'}


def local_groups():
    return {fields[0]: fields for line in LOCAL_GROUPS.read_text().splitlines()
            if len(fields := line.split(':')) == 4}


def local_users():
    return {fields[0]: fields for line in LOCAL_USERS.read_text().splitlines()
            if len(fields := line.split(':')) == 7}


def execute(action, group, user=''):
    if not NAME.fullmatch(group) or (user and not NAME.fullmatch(user)):
        raise ValueError('Nome de grupo ou usuário inválido.')
    groups, users = local_groups(), local_users()
    if action == 'create':
        if group in groups: raise ValueError('Este grupo já existe.')
        command = ['groupadd', group]
    elif action == 'delete':
        if group not in groups: raise ValueError('Grupo local não encontrado.')
        if group in PROTECTED or int(groups[group][2]) < 1000:
            raise ValueError('Grupo de sistema ou administração protegido.')
        if any(fields[3] == groups[group][2] for fields in users.values()):
            raise ValueError('O grupo é principal de uma conta local.')
        command = ['groupdel', group]
    elif action in ('add', 'remove'):
        if group not in groups or user not in users:
            raise ValueError('Escolha um grupo e uma conta locais.')
        if int(users[user][2]) < 1000 or int(groups[group][2]) < 1000 and group != 'sudo':
            raise ValueError('Contas e grupos do sistema não podem ser alterados aqui.')
        if action == 'remove' and group == 'sudo':
            admins = [name for name in groups['sudo'][3].split(',') if name in users]
            if user in admins and len(admins) <= 1:
                raise ValueError('Mantenha ao menos um administrador local.')
        command = ['gpasswd', '-a' if action == 'add' else '-d', user, group]
    else:
        raise ValueError('Ação desconhecida.')
    subprocess.run(command, check=True, timeout=20, capture_output=True, text=True)


if __name__ == '__main__':
    try:
        if len(sys.argv) not in (3, 4): raise ValueError('Parâmetros inválidos.')
        execute(*sys.argv[1:])
    except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
