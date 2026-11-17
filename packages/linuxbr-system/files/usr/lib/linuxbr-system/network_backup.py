"""Encrypted, versioned backup to an SFTP repository."""

import ipaddress
import re
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import quote


SSH_OPTIONS = (
    'sftp.args=-oBatchMode=yes -oStrictHostKeyChecking=yes -oConnectTimeout=12 '
    '-oServerAliveInterval=15 -oServerAliveCountMax=3'
)


def repository(host, user, port, directory):
    host = host.strip()
    user = user.strip()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}', user):
        raise ValueError('Informe o usuário SSH do computador de destino.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        labels = host.removesuffix('.').split('.')
        if len(host) > 253 or not all(
            re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels
        ):
            raise ValueError('Informe o nome ou o endereço IP do computador de destino.') from None
    else:
        if address.version == 6:
            if address.scope_id is not None:
                raise ValueError('Use um endereço IPv6 sem identificador de interface.')
            host = f'[{address}]'
    path = absolute_path(directory)
    if not 1 <= port <= 65535:
        raise ValueError('Informe uma porta SSH entre 1 e 65535.')
    return f'sftp://{user}@{host}:{port}/{quote(path, safe="/")}'


def absolute_path(value):
    if (not value.startswith('/') or value.startswith('//')
            or any(part in ('.', '..') for part in value.split('/'))
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError('Informe um caminho absoluto, como /home/usuario/backup.')
    normalized = str(Path(value))
    if normalized == '/':
        raise ValueError('Escolha uma pasta ou arquivo dentro do diretório raiz.')
    return normalized


def password_input(value):
    if not value or value != value.strip() or any(char in value for char in '\r\n\0'):
        raise ValueError('Informe a senha do backup sem espaços nas extremidades ou quebras de linha.')
    return (value + '\n').encode('utf-8')


def command(repo, *args, restic='/usr/bin/restic'):
    return [
        '/usr/bin/env', '-u', 'RESTIC_PASSWORD', '-u', 'RESTIC_PASSWORD_COMMAND',
        '-u', 'RESTIC_REPOSITORY_FILE', restic,
        '--repo', repo, '--password-file', '/dev/stdin', '-o', SSH_OPTIONS, *args,
    ]


def restore_args(snapshot, source, directory):
    if not re.fullmatch(r'(?:latest|[0-9a-f]{8,64})', snapshot):
        raise ValueError('Informe latest ou o identificador hexadecimal da cópia.')
    args = ['restore', snapshot, '--verify', '--overwrite', 'never']
    if source:
        path = absolute_path(source)
        literal = re.sub(r'([\\*?\[])', r'\\\1', path)
        args.extend(['--include', literal])
    target = mkdtemp(prefix='LinuxBR-restaurado-', dir=Path(directory).resolve(strict=True))
    return [*args, '--target', target], target
