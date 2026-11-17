"""State and filesystem operations shared by the Explorer dialogs."""
from contextlib import contextmanager
import errno
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata

from batch_rename_backend import apply_plan, rename_noreplace


BLOCK_SIZE = 1024 * 1024
WINDOWS_DEVICE = re.compile(r'^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)', re.I)
WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]|[. ]$')


class State:
    def __init__(self, directory=None):
        self.directory = directory or Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linuxbr/files'
        self.path = self.directory / 'workflows.json'

    def read(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            value = {}
        if not isinstance(value, dict):
            raise ValueError('Não foi possível ler as preferências de arquivos.')
        return value

    @contextmanager
    def exclusive(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.directory / 'workflows.lock').open('a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @contextmanager
    def update(self):
        with self.exclusive():
            value = self.read()
            yield value
            self.write(value)

    def write(self, value):
        descriptor, temporary = tempfile.mkstemp(prefix='.workflows-', dir=self.directory)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def set_tag(self, label, paths, add):
        label = label.strip()
        if not label or len(label) > 80 or any(not char.isprintable() for char in label):
            raise ValueError('Informe uma etiqueta com até 80 caracteres.')
        with self.update() as value:
            tags = value.setdefault('tags', {})
            items = set(tags.get(label, ()))
            changes = {str(path) for path in paths}
            remaining = (items | changes) if add else (items - changes)
            if remaining:
                tags[label] = sorted(remaining)
            else:
                tags.pop(label, None)

    def remember(self, operation, changes):
        if not changes:
            return
        with self.update() as value:
            rows = [[str(source), str(target), list(identity)] for source, target, identity in changes]
            value['undo'] = [dict(operation=operation, changes=rows), *value.get('undo', [])][:20]
            self.relocate_tags(value, changes)

    @staticmethod
    def relocate_tags(state, changes):
        for label, tagged in state.get('tags', {}).items():
            updated = []
            for location in tagged:
                path = Path(location)
                for source, target, _ in changes:
                    if path.is_relative_to(source):
                        path = target / path.relative_to(source)
                        break
                updated.append(str(path))
            state['tags'][label] = sorted(set(updated))

    def undo(self, snapshot):
        with self.exclusive():
            value = self.read()
            history = value.get('undo', [])
            if not history or history[0] != snapshot:
                raise ValueError('O histórico mudou. Reabra a operação para conferir os itens.')
            rows = []
            for source, target, identity in reversed(snapshot['changes']):
                former = Path(source)
                present = Path(target)
                if os.path.lexists(former):
                    raise ValueError(f'O destino {former} já foi ocupado.')
                if not former.parent.is_dir():
                    raise ValueError(f'A pasta {former.parent} não está disponível.')
                rows.append((present, former, tuple(identity), ''))
            def commit(changes):
                self.relocate_tags(value, changes)
                value['undo'] = history[1:]
                self.write(value)

            apply_plan(rows, on_commit=commit)

    def mark_transfer(self, source, destination, folder_info):
        key = hashlib.sha256(os.fsencode(str(source) + '\0' + str(destination))).hexdigest()
        identity = [folder_info.st_dev, folder_info.st_ino]
        with self.update() as value:
            pending = value.setdefault('pending_copies', {})
            if pending.get(key, identity) != identity:
                raise ValueError('A pasta de destino mudou. Reconecte a unidade original para retomar a cópia.')
            pending[key] = identity
        return key

    def complete_transfer(self, key):
        with self.update() as value:
            value.get('pending_copies', {}).pop(key, None)


def regular_files(root):
    def failure(error):
        raise error

    for folder, directories, files in os.walk(root, followlinks=False, onerror=failure):
        directories.sort()
        for name in sorted(files):
            path = Path(folder) / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                yield path, info


def checked_root(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError(f'Escolha uma pasta disponível: {value}')
    return path.resolve()


def find_files(roots, pattern, extension, minimum, maximum, from_time, to_time, limit=2000):
    matched = []
    seen = set()
    for root in dict.fromkeys(checked_root(value) for value in roots):
        for path, info in regular_files(root):
            if path in seen:
                continue
            if pattern and not fnmatch.fnmatchcase(path.name.casefold(), pattern.casefold()):
                continue
            if extension and not path.name.casefold().endswith('.' + extension.lower().lstrip('.')):
                continue
            if ((minimum is not None and info.st_size < minimum)
                    or (maximum is not None and info.st_size > maximum)
                    or (from_time is not None and info.st_mtime < from_time)
                    or (to_time is not None and info.st_mtime >= to_time)):
                continue
            seen.add(path)
            if len(matched) >= limit:
                return matched, True
            matched.append(path)
    return matched, False


def digest_file(stream):
    checksum = hashlib.sha256()
    while block := stream.read(BLOCK_SIZE):
        checksum.update(block)
    return checksum.hexdigest()


def compare_folders(first, second, checksum):
    first, second = checked_root(first), checked_root(second)
    if first == second:
        raise ValueError('Escolha duas pastas diferentes.')
    paired = [{path.relative_to(root): info for path, info in regular_files(root)} for root in (first, second)]
    left, right = paired
    rows = []
    for name in sorted(left.keys() | right.keys()):
        if name not in right:
            kind = 'Somente na primeira pasta'
        elif name not in left:
            kind = 'Somente na segunda pasta'
        elif left[name].st_size != right[name].st_size:
            kind = 'Tamanho diferente'
        elif checksum:
            with opened_regular(first / name) as origin, opened_regular(second / name) as destination:
                if digest_file(origin) == digest_file(destination):
                    continue
            kind = 'Conteúdo diferente'
        elif left[name].st_mtime_ns != right[name].st_mtime_ns:
            kind = 'Data de modificação diferente'
        else:
            continue
        rows.append((str(name), kind))
    return rows


def windows_key(name):
    return unicodedata.normalize('NFC', name.rstrip('. ')).casefold()


def names_to_review(paths, destination):
    names = {windows_key(path.name): path.name for path in destination.iterdir()}
    conflicts = []
    for path in paths:
        key = windows_key(path.name)
        if WINDOWS_FORBIDDEN.search(path.name) or WINDOWS_DEVICE.match(key):
            conflicts.append(f'{path.name} — nome incompatível com Windows')
        elif key in names and names[key] != path.name:
            conflicts.append(f'{path.name} — conflito com {names[key]}')
        names[key] = path.name
    return conflicts


@contextmanager
def opened_regular(path, flags=os.O_RDONLY):
    descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    mode = 'r+b' if flags & os.O_RDWR else 'rb'
    with os.fdopen(descriptor, mode) as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f'{path} não é um arquivo comum.')
        yield stream


def signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def verified_copy(source, destination, state=None):
    folder_info = destination.parent.stat()
    folder_identity = (folder_info.st_dev, folder_info.st_ino)
    key = state.mark_transfer(source, destination, folder_info) if state else None
    if os.path.lexists(destination):
        # Earlier files in an interrupted batch may already be complete.
        with opened_regular(source) as origin, opened_regular(destination) as current:
            source_signature = signature(os.fstat(origin.fileno()))
            current_signature = signature(os.fstat(current.fileno()))
            checksum = digest_file(origin)
            matches = (
                checksum == digest_file(current)
                and source_signature == signature(source.stat(follow_symlinks=False))
                and current_signature == signature(destination.stat(follow_symlinks=False))
            )
        if not matches:
            raise FileExistsError(errno.EEXIST, 'O destino já contém um arquivo diferente', destination)
        if state:
            state.complete_transfer(key)
        return checksum
    token = hashlib.sha256(os.fsencode(str(source) + '\0' + destination.name)).hexdigest()[:32]
    partial = destination.parent / f'.linuxbr-copy-{token}.part'
    with opened_regular(source) as origin, opened_regular(partial, os.O_RDWR | os.O_CREAT) as output:
        if os.fstat(output.fileno()).st_nlink != 1:
            raise ValueError('O arquivo parcial contém vínculos externos.')
        fcntl.flock(output.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        version = signature(os.fstat(origin.fileno()))
        before = os.fstat(output.fileno())
        offset = 0
        while offset < before.st_size:
            block = output.read(min(before.st_size - offset, BLOCK_SIZE))
            if not block or origin.read(len(block)) != block:
                origin.seek(0)
                output.seek(0)
                output.truncate()
                break
            offset += len(block)
        while block := origin.read(BLOCK_SIZE):
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
        origin.seek(0)
        output.seek(0)
        source_digest, target_digest = digest_file(origin), digest_file(output)
        source_info = os.fstat(origin.fileno())
        if (source_digest != target_digest or version != signature(source_info)
                or version != signature(source.stat(follow_symlinks=False))):
            raise ValueError('O arquivo original mudou ou a soma de verificação divergiu. Refaça a cópia.')
        current = partial.lstat()
        if (current.st_dev, current.st_ino, current.st_nlink) != (before.st_dev, before.st_ino, 1):
            raise ValueError('O arquivo parcial mudou de lugar.')
        current_folder = destination.parent.stat()
        if (current_folder.st_dev, current_folder.st_ino) != folder_identity:
            raise ValueError('A pasta de destino mudou durante a cópia. Reconecte a unidade original.')
        # The original mode is limited to ordinary permission bits.
        os.fchmod(output.fileno(), stat.S_IMODE(source_info.st_mode) & 0o777)
        rename_noreplace(partial, destination)
    if state:
        state.complete_transfer(key)
    return source_digest
