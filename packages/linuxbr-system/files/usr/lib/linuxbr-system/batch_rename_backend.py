"""Preview and apply batch renames without overwriting directory entries."""
import ctypes
from datetime import datetime
import os
from string import Formatter


def plan(items, pattern, find='', replace=''):
    selected = set(items)
    if any(selected.intersection(source.parents) for source in items):
        raise ValueError('Selecione a pasta ou seus itens, em operações separadas.')
    for _, field, specification, conversion in Formatter().parse(pattern):
        if field is not None:
            if field not in ('nome', 'data', 'n') or specification or conversion:
                raise ValueError('Use somente {nome}, {data} e {n}, sem especificações.')
    width = max(2, len(str(len(items))))
    rows = []
    for number, source in enumerate(items, 1):
        identity = source.lstat()
        extension = source.suffix if not source.is_dir() or source.is_symlink() else ''
        stem = source.name[:-len(extension)] if extension else source.name
        if find:
            stem = stem.replace(find, replace)
        new_stem = pattern.format(nome=stem, data=datetime.fromtimestamp(identity.st_mtime).date(),
                                  n=str(number).zfill(width))
        name = new_stem + extension
        valid = bool(new_stem.strip() and name not in ('.', '..') and '/' not in name
                     and all(character.isprintable() for character in name))
        if valid:
            try:
                valid = len(os.fsencode(name)) <= os.pathconf(source.parent, 'PC_NAME_MAX')
            except OSError:
                pass
        target = source.with_name(name) if valid else None
        status = ''
        if not valid:
            status = 'Nome inválido ou longo demais'
        elif source == target:
            status = 'Sem alteração'
        elif os.path.lexists(target):
            status = 'O destino já existe'
        rows.append((source, target, (identity.st_dev, identity.st_ino), status))
    counts = {}
    for _, target, _, _ in rows:
        if target is not None:
            counts[target] = counts.get(target, 0) + 1
    return [(source, target, identity, 'Nome repetido na lista' if counts.get(target, 0) > 1 else status)
            for source, target, identity, status in rows]


def rename_noreplace(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError:
        raise OSError('A renomeação protegida não está disponível neste sistema.') from None
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)


def apply_plan(rows, on_commit=None):
    changes = []
    try:
        for source, target, identity, status in rows:
            if status == 'Sem alteração':
                continue
            if status:
                raise ValueError(f'{source.name}: {status}.')
            current = source.lstat()
            if (current.st_dev, current.st_ino) != identity:
                raise ValueError(f'{source.name} mudou desde a prévia.')
            rename_noreplace(source, target)
            changes.append((source, target, identity))
        if on_commit is not None:
            on_commit(changes)
    except (OSError, ValueError) as error:
        remaining = []
        for source, target, identity in reversed(changes):
            try:
                current = target.lstat()
                if (current.st_dev, current.st_ino) != identity:
                    raise ValueError('O destino foi alterado.')
                rename_noreplace(target, source)
            except (OSError, ValueError):
                remaining.append(str(target))
        detail = '\nItens que permaneceram no novo local:\n' + '\n'.join(remaining) if remaining else ''
        raise ValueError(f'{error}{detail}') from error


