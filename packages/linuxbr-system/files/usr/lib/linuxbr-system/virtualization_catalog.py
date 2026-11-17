"""Versioned quick-create profiles distributed by the local administrator."""

import json
from pathlib import Path
import re
import stat

from virtualization_backend import checked_name, NAME, REVISION_ID

CATALOG = Path('/etc/linuxbr/vm-templates.d')
LIMIT = 64 * 1024
BUILTIN = ({'id': 'linux-desktop', 'name': 'Linux Desktop', 'revision': '1.0.0', 'memory': 4096,
            'cpus': 2, 'disk_gib': 48, 'firmware': 'uefi', 'network': '', 'windows': False, 'tpm': False},
           {'id': 'windows-11', 'name': 'Windows 11', 'revision': '1.0.0', 'memory': 8192,
            'cpus': 4, 'disk_gib': 80, 'firmware': 'uefi-secure', 'network': '', 'windows': True, 'tpm': True},
           {'id': 'linux-legacy', 'name': 'Linux com BIOS', 'revision': '1.0.0', 'memory': 2048,
            'cpus': 2, 'disk_gib': 32, 'firmware': 'bios', 'network': '', 'windows': False, 'tpm': False})
FIELDS = frozenset(BUILTIN[0])


def check(profile):
    if not isinstance(profile, dict) or set(profile) != FIELDS:
        raise ValueError('Campos inesperados no modelo.')
    checked_name(profile['name'])
    for field, pattern in (('id', NAME), ('revision', REVISION_ID)):
        if not isinstance(profile[field], str) or not pattern.fullmatch(profile[field]):
            raise ValueError('O identificador e a revisão do modelo são obrigatórios.')
    for key, low, high in (('memory', 256, 262144), ('cpus', 1, 256), ('disk_gib', 4, 2048)):
        if type(profile[key]) is not int or not low <= profile[key] <= high:
            raise ValueError(f'Recurso fora do intervalo para {key}.')
    if profile['firmware'] not in ('bios', 'uefi', 'uefi-secure'):
        raise ValueError('Firmware do modelo inválido.')
    if profile['network'] != '':
        checked_name(profile['network'])
    if type(profile['windows']) is not bool or type(profile['tpm']) is not bool:
        raise ValueError('Compatibilidade Windows e TPM devem ser valores booleanos.')
    if profile['tpm'] and profile['firmware'] == 'bios':
        raise ValueError('Este assistente exige UEFI para TPM virtual.')
    return profile


def catalog(include_builtin=True, path=None):
    folder = CATALOG if path is None else path
    rows = {item['id']: item.copy() for item in BUILTIN} if include_builtin else {}
    diagnostics = []
    try:
        files = sorted(folder.glob('*.json'))[:150]
        info = folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            return list(rows.values()), ['O diretório de modelos precisa pertencer ao administrador.']
    except FileNotFoundError:
        return list(rows.values()), diagnostics
    except OSError:
        return list(rows.values()), ['O diretório de modelos está indisponível.']
    loaded = set()
    for candidate in files:
        try:
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_size > LIMIT:
                raise ValueError('arquivo sem proteção administrativa ou acima do limite')
            value = check(json.loads(candidate.read_text(encoding='utf-8')))
            if value['id'] in loaded or value['id'] != candidate.stem:
                raise ValueError('o identificador deve ser único e igual ao nome do arquivo')
            loaded.add(value['id'])
            rows[value['id']] = value
        except (OSError, UnicodeError, ValueError) as error:
            diagnostics.append(f'{candidate.name[:140]} · {error}')
    return sorted(rows.values(), key=lambda item: item['name'].casefold()), diagnostics[:10]
