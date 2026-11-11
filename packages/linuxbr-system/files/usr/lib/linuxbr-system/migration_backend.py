"""Copy selected personal folders with verification and explicit conflict policy."""
from datetime import datetime, timezone
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled('Operação cancelada.')


def directory_fd(path):
    absolute = Path(path).absolute()
    root = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        return beneath(root, absolute.parts[1:])
    finally:
        os.close(root)


def beneath(root_fd, parts, create=False):
    """Open directory components relative to a held root without following links."""
    current = os.dup(root_fd)
    try:
        for part in parts:
            if part in ('', '.', '..') or '/' in part:
                raise ValueError('Componente de caminho inválido.')
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=current)
            os.close(current)
            current = following
        return current
    except BaseException:
        os.close(current)
        raise


def prepare(sources, destination, cancel=None, notify=None, *, policy=None):
    destination = Path(destination).expanduser().resolve(strict=True)
    if not destination.is_dir():
        raise ValueError('Escolha uma pasta de destino existente.')
    result = {'destination': str(destination), 'sources': [], 'files': [], 'directories': [],
              'bytes': 0, 'hashed_bytes': 0, 'skipped': [], 'errors': [], 'conflicts': 0,
              'resume_bytes': 0}
    labels = set()
    for raw in sources:
        check_cancel(cancel)
        path = Path(raw).expanduser()
        if path.is_symlink():
            raise ValueError('Selecione a pasta original, em vez de um link: ' + str(path))
        source = path.resolve(strict=True)
        if source == destination or source in destination.parents or destination in source.parents:
            raise ValueError('Origem e destino devem ser pastas separadas, sem conter uma à outra.')
        if any(source == Path(item['path']) or source in Path(item['path']).parents
               or Path(item['path']) in source.parents for item in result['sources']):
            raise ValueError('As origens não podem repetir ou conter outra pasta já selecionada.')
        label = source.name or 'Arquivos importados'
        stem, number = label, 2
        while label.casefold() in labels:
            label = f'{stem} ({number})'; number += 1
        labels.add(label.casefold())
        index = len(result['sources'])
        source_record = {'path': str(source), 'label': label, 'files': 0, 'bytes': 0}
        result['sources'].append(source_record)
        root_fd = directory_fd(source)
        try:
            def error(problem):
                result['errors'].append(str(problem))
            for base, directories, files, fd in os.fwalk('.', follow_symlinks=False,
                                                        dir_fd=root_fd, onerror=error):
                check_cancel(cancel)
                relative = Path(base)
                parts = list(relative.parts) if str(relative) != '.' else []
                result['directories'].append({'source': index, 'parts': parts})
                for name in directories[:]:
                    try:
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                        if not stat.S_ISDIR(info.st_mode):
                            directories.remove(name)
                            result['skipped'].append(str(relative / name))
                    except OSError as problem:
                        directories.remove(name); error(problem)
                for name in files:
                    check_cancel(cancel)
                    try:
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                        if not stat.S_ISREG(info.st_mode):
                            result['skipped'].append(str(relative / name)); continue
                        item = {'source': index, 'parts': parts + [name], 'size': info.st_size,
                                'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns,
                                'inode': info.st_ino, 'device': info.st_dev}
                        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                        try:
                            if fingerprint(os.fstat(descriptor)) != fingerprint(info):
                                raise OSError('O arquivo mudou antes da conferência: ' + name)
                            def progress(size):
                                result['hashed_bytes'] += size
                                if notify:
                                    notify({'phase': 'scan', 'files': len(result['files']),
                                            'bytes': result['bytes'], 'hashed_bytes': result['hashed_bytes']})
                            item['sha256'] = digest_fd(descriptor, cancel, progress)
                            confirmation = digest_fd(descriptor, cancel)
                            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                            if (item['sha256'] != confirmation or fingerprint(os.fstat(descriptor)) != fingerprint(info)
                                    or fingerprint(current) != fingerprint(info)):
                                raise OSError('O arquivo mudou durante a conferência: ' + name)
                        finally:
                            os.close(descriptor)
                        result['files'].append(item)
                        result['bytes'] += info.st_size
                        source_record['bytes'] += info.st_size
                        source_record['files'] += 1
                        target = destination / label / relative / name
                        if target.exists() or target.is_symlink():
                            result['conflicts'] += 1
                            if policy == 'keep':
                                try:
                                    existing_fd = directory_fd(target.parent)
                                    try:
                                        if verified_copy(existing_fd, name, item, cancel):
                                            result['resume_bytes'] += item['size']
                                    finally:
                                        os.close(existing_fd)
                                except OSError:
                                    pass
                        if len(result['files']) > 200000:
                            raise ValueError('Selecione menos de 200.000 arquivos por importação.')
                    except OSError as problem:
                        error(problem)
                if notify:
                    notify({'phase': 'scan', 'files': len(result['files']), 'bytes': result['bytes']})
        finally:
            os.close(root_fd)
    if not result['sources']:
        raise ValueError('Escolha ao menos uma pasta de origem.')
    result['available'] = shutil.disk_usage(destination).free
    result['required_bytes'] = result['bytes'] - result['resume_bytes']
    result['enough_space'] = result['available'] >= result['required_bytes'] + 16 * 1024**2
    return result


def fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def rename_noreplace(source_fd, source_name, destination_fd, destination_name):
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(source_fd, os.fsencode(source_name), destination_fd, os.fsencode(destination_name), 1):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), destination_name)


def digest_fd(descriptor, cancel=None, progress=None):
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while True:
        check_cancel(cancel)
        block = os.read(descriptor, 1024*1024)
        if not block: return digest.hexdigest()
        digest.update(block)
        if progress: progress(len(block))


class DestinationChanged(ValueError):
    def __init__(self, message, preserved=None):
        super().__init__(message)
        self.preserved = preserved


def entry_info(fd, name):
    try:
        return os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def conflict_name(fd, name, policy):
    existing = entry_info(fd, name)
    if existing is None:
        return name, None
    if policy == 'skip':
        return None, existing
    if not stat.S_ISREG(existing.st_mode):
        if policy == 'replace':
            raise ValueError('O destino não é um arquivo regular: ' + name)
    elif policy == 'replace':
        return name, existing
    original = Path(name)
    for number in range(2, 100000):
        candidate = f'{original.stem} ({number}){original.suffix}'
        if entry_info(fd, candidate) is None:
            return candidate, None
    raise ValueError('Não foi possível escolher um nome livre para ' + name)


def verified_copy(fd, name, item, cancel):
    """Find an unchanged copy created under the keep-both naming policy."""
    original = Path(name)
    for number in range(1, 100000):
        candidate = name if number == 1 else f'{original.stem} ({number}){original.suffix}'
        info = entry_info(fd, candidate)
        if info is None:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_size != item['size']:
            continue
        try:
            descriptor = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                 dir_fd=fd)
        except (FileNotFoundError, PermissionError):
            continue
        try:
            if fingerprint(os.fstat(descriptor)) != fingerprint(info):
                continue
            if digest_fd(descriptor, cancel) != item['sha256']:
                continue
            current = entry_info(fd, candidate)
            if (current is not None and fingerprint(current) == fingerprint(info)
                    and fingerprint(os.fstat(descriptor)) == fingerprint(info)):
                return candidate
        finally:
            os.close(descriptor)
    return None


def copy_file(source_fd, destination_fd, item, name, previous, cancel, progress):
    descriptor = os.open(item['parts'][-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=source_fd)
    temporary = '.linuxbr-import-' + uuid.uuid4().hex
    output = None
    previous_fd = None
    captured = None
    published = False
    try:
        original = os.fstat(descriptor)
        if not stat.S_ISREG(original.st_mode) or fingerprint(original) != (
                item['device'], item['inode'], item['size'], item['mtime_ns'], item['ctime_ns']):
            raise ValueError('O arquivo de origem mudou após a conferência: ' + name)
        if previous is not None:
            previous_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=destination_fd)
            if fingerprint(os.fstat(previous_fd)) != fingerprint(previous):
                raise DestinationChanged('O destino mudou antes da cópia: ' + name)
            previous_digest = digest_fd(previous_fd, cancel)
            if fingerprint(os.fstat(previous_fd)) != fingerprint(previous):
                raise DestinationChanged('O destino mudou durante a conferência: ' + name)
        output = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=destination_fd)
        digest = hashlib.sha256()
        while True:
            check_cancel(cancel)
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            pending = memoryview(block)
            while pending:
                count = os.write(output, pending)
                pending = pending[count:]
            progress(len(block))
        if (fingerprint(original) != fingerprint(os.fstat(descriptor))
                or digest.hexdigest() != item['sha256']):
            raise ValueError('O arquivo foi modificado durante a cópia: ' + name)
        os.fsync(output)
        os.lseek(output, 0, os.SEEK_SET)
        verified = hashlib.sha256()
        while True:
            check_cancel(cancel)
            block = os.read(output, 1024 * 1024)
            if not block:
                break
            verified.update(block)
        if verified.digest() != digest.digest():
            raise OSError('A verificação da cópia não corresponde à origem: ' + name)
        current = entry_info(destination_fd, name)
        if (previous is None and current is not None) or (previous is not None and (
                current is None or fingerprint(previous) != fingerprint(current))):
            raise ValueError('O destino mudou durante a cópia: ' + name)
        os.utime(output, ns=(original.st_atime_ns, original.st_mtime_ns))
        os.close(output); output = None
        if previous is None:
            # RENAME_NOREPLACE also supports destinations without hard links.
            rename_noreplace(destination_fd, temporary, destination_fd, name)
        else:
            captured = '.linuxbr-anterior-' + uuid.uuid4().hex
            rename_noreplace(destination_fd, name, destination_fd, captured)
            captured_info = entry_info(destination_fd, captured)
            # Rename updates ctime. Check identity/content and retain this version
            # after a successful replacement, including all original metadata.
            if (captured_info is None or fingerprint(captured_info)[:4] != fingerprint(previous)[:4]
                    or captured_info.st_mode != previous.st_mode or digest_fd(previous_fd, cancel) != previous_digest):
                try:
                    rename_noreplace(destination_fd, captured, destination_fd, name)
                    captured = None
                except OSError:
                    pass
                raise DestinationChanged('O destino mudou; a versão encontrada foi preservada.', captured)
            try:
                rename_noreplace(destination_fd, temporary, destination_fd, name)
            except OSError:
                try:
                    rename_noreplace(destination_fd, captured, destination_fd, name)
                    captured = None
                except OSError:
                    pass
                raise DestinationChanged('O nome de destino passou a ser usado por outro arquivo. Os dados anteriores foram preservados.', captured) from None
        try:
            os.fsync(destination_fd)
        except OSError as error:
            if error.errno not in (errno.EINVAL, errno.ENOTSUP): raise
        published = True
        return {'sha256': digest.hexdigest(), 'previous_copy': captured}
    except BaseException as error:
        if captured and not published:
            try:
                rename_noreplace(destination_fd, captured, destination_fd, name)
                captured = None
            except OSError:
                if isinstance(error, Cancelled):
                    raise DestinationChanged('Cancelamento solicitado; uma versão anterior foi preservada para revisão.', captured) from None
                if isinstance(error, DestinationChanged): error.preserved = captured
        raise
    finally:
        if output is not None:
            os.close(output)
        os.close(descriptor)
        if previous_fd is not None: os.close(previous_fd)
        try:
            os.unlink(temporary, dir_fd=destination_fd)
        except FileNotFoundError:
            pass


def transfer(plan, policy='keep', cancel=None, notify=None):
    if policy not in ('keep', 'skip', 'replace'):
        raise ValueError('Política de conflitos inválida.')
    if not plan.get('enough_space'):
        raise ValueError('Não há espaço livre suficiente no destino.')
    report = {'version': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
              'status': 'running', 'copied': [], 'skipped': [], 'already_verified': [], 'errors': [], 'bytes': 0}
    roots = []
    destination_fd = directory_fd(plan['destination'])
    processed = 0
    try:
        for item in plan['sources']:
            roots.append(directory_fd(item['path']))
        for item in plan['directories']:
            check_cancel(cancel)
            label = plan['sources'][item['source']]['label']
            fd = beneath(destination_fd, [label] + item['parts'], create=True)
            os.close(fd)
        for item in plan['files']:
            check_cancel(cancel)
            label = plan['sources'][item['source']]['label']
            relative = str(Path(label, *item['parts']))
            source_parent = target_parent = None
            try:
                source_parent = beneath(roots[item['source']], item['parts'][:-1])
                target_parent = beneath(destination_fd, [label] + item['parts'][:-1], create=True)
                if policy == 'keep':
                    existing = verified_copy(target_parent, item['parts'][-1], item, cancel)
                    if existing is not None:
                        source_info = entry_info(source_parent, item['parts'][-1])
                        if source_info is None or fingerprint(source_info) != (
                                item['device'], item['inode'], item['size'], item['mtime_ns'], item['ctime_ns']):
                            raise ValueError('O arquivo de origem mudou após a conferência: ' + relative)
                        report['already_verified'].append(str(Path(label, *item['parts'][:-1], existing)))
                        processed += item['size']
                        continue
                name, previous = conflict_name(target_parent, item['parts'][-1], policy)
                if name is None:
                    report['skipped'].append(relative); processed += item['size']; continue
                space = os.fstatvfs(target_parent)
                if space.f_bavail * space.f_frsize < item['size']:
                    raise OSError('Espaço insuficiente para concluir a cópia.')
                def progress(size):
                    nonlocal processed
                    processed += size
                    if notify:
                        notify({'phase': 'copy', 'path': relative, 'processed': processed,
                                'total': plan['bytes'], 'copied': len(report['copied'])})
                copied = copy_file(source_parent, target_parent, item, name, previous, cancel, progress)
                report['copied'].append({'path': str(Path(label, *item['parts'][:-1], name)),
                                         'sha256': copied['sha256'], 'bytes': item['size'],
                                         'previous_copy': str(Path(label, *item['parts'][:-1], copied['previous_copy'])) if copied['previous_copy'] else None})
                report['bytes'] += item['size']
            except (OSError, ValueError) as error:
                preserved = getattr(error, 'preserved', None)
                report['errors'].append({'path': relative, 'error': str(error),
                                         'preserved_destination': str(Path(label, *item['parts'][:-1], preserved)) if preserved else None})
            finally:
                if source_parent is not None: os.close(source_parent)
                if target_parent is not None: os.close(target_parent)
        report['status'] = 'partial' if report['errors'] or plan.get('errors') else 'completed'
    except Cancelled:
        report['status'] = 'cancelled'
    except (OSError, ValueError) as error:
        report['status'] = 'partial'; report['errors'].append({'error': str(error)})
    finally:
        for fd in roots: os.close(fd)
        os.close(destination_fd)
    report['scan_errors'] = plan.get('errors', [])
    report['links_and_special_files_skipped'] = plan.get('skipped', [])
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    return report


def save_report(report, destination):
    name = 'linuxbr-importacao-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6] + '.json'
    fd = directory_fd(destination)
    try:
        output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(output, 'w', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        return str(Path(destination) / name)
    finally:
        os.close(fd)
