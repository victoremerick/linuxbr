"""Require the desktop setup on the first boot of this installation."""

import json
import os
from pathlib import Path

import libcalamares


def pretty_name():
    return 'Preparar a configuração inicial'


def run():
    try:
        root = Path(libcalamares.globalstorage.value('rootMountPoint')).resolve(strict=True)
        if root == Path('/') or not os.path.ismount(root) or not (root / 'etc/debian_version').is_file():
            raise ValueError('O sistema de destino precisa estar montado.')

        state = root / 'var/lib/linuxbr/initial-setup'
        for parent in reversed((state, *state.parents)):
            if parent.is_relative_to(root) and parent.is_symlink():
                raise ValueError('A pasta de configuração contém um link simbólico.')
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        saved_checks = libcalamares.globalstorage.value('linuxbrLiveChecks')
        if saved_checks:
            checks = json.loads(saved_checks)
            if set(checks) != {'schema', 'keyboard', 'touchpad', 'audio', 'video'} or checks['schema'] != 1:
                raise ValueError('O registro de verificações da sessão Live está inválido.')
            if any(value is not None and type(value) is not bool for key, value in checks.items() if key != 'schema'):
                raise ValueError('O registro de verificações contém um resultado inválido.')
            fd = os.open(state / 'live-checks.json',
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(checks, stream)
                stream.flush()
                os.fsync(stream.fileno())
        marker = state / 'pending'
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except (KeyError, OSError, TypeError, ValueError) as error:
        return ('Não foi possível preparar a configuração inicial.', str(error))
    return None
