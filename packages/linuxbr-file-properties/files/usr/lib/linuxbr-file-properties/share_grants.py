"""Issue expiring Samba access for one local account on an existing share."""

import argparse
import configparser
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import usershare_entries

STATE = Path('/var/lib/linuxbr/share-grants')
PART = re.compile(r'linuxbr-temporario-[0-9a-f]{16}')
USERNAME = re.compile(r'[a-z_][a-z0-9_.-]{0,63}')
SID = re.compile(r'(?m)^User SID\s*:\s*(S-1-(?:\d+-){2,14}\d+)\s*$')
PERMISSION = {'read': 'R', 'edit': 'F'}
NETWORK_TOOLS = {'net': '/usr/bin/net', 'pdbedit': '/usr/bin/pdbedit',
                 'smbcontrol': '/usr/bin/smbcontrol', 'setpriv': '/usr/bin/setpriv',
                 'testparm': '/usr/bin/testparm', 'systemctl': '/usr/bin/systemctl'}


def run(tool, *args):
    return subprocess.run([NETWORK_TOOLS[tool], *args], stdin=subprocess.DEVNULL, capture_output=True,
                          timeout=12, text=True, errors='replace', check=False,
                          env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})


def registered():
    info = run('net', 'usershare', 'info', '--long')
    if info.returncode:
        raise ValueError('Não foi possível consultar as publicações SMB deste computador.')
    try:
        return usershare_entries(info.stdout)
    except configparser.Error:
        raise ValueError('O cadastro de compartilhamentos SMB não pôde ser interpretado.') from None


def account(name):
    if not USERNAME.fullmatch(name):
        raise ValueError('Informe uma conta local válida.')
    local = pwd.getpwnam(name)
    if not 1000 <= local.pw_uid < 65000:
        raise ValueError('Escolha uma conta de usuário deste computador.')
    result = run('pdbedit', '-L', '-v', '-u', local.pw_name)
    sid = SID.search(result.stdout)
    if result.returncode or not sid:
        raise ValueError('A conta precisa estar cadastrada no Samba deste computador.')
    return local, sid.group(1)


def local_permission(user, scope, folder):
    options = ['--reuid', str(user.pw_uid), '--regid', str(user.pw_gid), '--init-groups', '--']
    modes = ('-r', '-x', '-w') if scope == 'edit' else ('-r', '-x')
    if any(run('setpriv', *options, '/usr/bin/test', mode, str(folder)).returncode for mode in modes):
        raise ValueError('As permissões locais da pasta ou do caminho não permitem este acesso para a conta.')


def dir_identity(raw, shares):
    requested = Path(raw)
    if not requested.is_absolute() or not requested.is_dir() or any(ord(c) < 32 for c in raw):
        raise ValueError('Escolha uma pasta local publicada nas propriedades.')
    folder = requested.resolve(strict=True)
    if folder != requested or folder == Path('/'):
        raise ValueError('Escolha o caminho original da pasta compartilhada.')
    source = next((name for name, row in shares.items() if not PART.fullmatch(name)
                   and row.get('path', '').rstrip('/') == str(folder)), None)
    if source is None:
        raise ValueError('Publique a pasta na aba Compartilhamento antes de criar uma concessão.')
    info = folder.stat()
    return folder, source, [info.st_dev, info.st_ino]


@contextmanager
def lock():
    STATE.mkdir(exist_ok=True, parents=True, mode=0o700)
    for item in (STATE.parent, STATE):
        info = item.lstat()
        mask = 0o077 if item == STATE else 0o022
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & mask:
            raise ValueError('O registro de concessões deve ser protegido pelo administrador.')
    fd = os.open(STATE / '.lock', os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def save(path, entry):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=STATE, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(entry, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def records():
    for path in sorted(STATE.glob('*.json')):
        if not PART.fullmatch(path.stem):
            continue
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_uid != 0 or details.st_mode & 0o077 or details.st_size > 16384:
            continue
        try:
            entry = json.loads(path.read_text(encoding='utf-8'))
            if entry.get('alias') == path.stem:
                yield path, entry
        except (AttributeError, OSError, ValueError):
            continue


def expected(entry):
    return (entry['tag'], entry['folder'], entry['sid'] + ':' + PERMISSION[entry['scope']], 'n')


def actual(share):
    return (share.get('comment'), share.get('path', '').rstrip('/'),
            share.get('usershare_acl', '').rstrip(','), share.get('guest_ok'))


def spool_directory():
    result = run('testparm', '-s', '--parameter-name=usershare path')
    spool = Path(result.stdout.strip())
    if result.returncode or not spool.is_absolute() or spool.resolve(strict=True) != spool:
        raise ValueError('A área de publicações SMB está indisponível.')
    for parent in spool.parents:
        metadata = parent.stat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise ValueError('O caminho da área de publicações SMB precisa de proteção administrativa.')
    info = spool.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o002
            or (info.st_mode & 0o020 and not info.st_mode & stat.S_ISVTX)):
        raise ValueError('A área de publicações SMB deve manter a proteção de proprietário.')
    return spool


def alias_file(alias, spool=None):
    if not PART.fullmatch(alias):
        raise ValueError('Nome de publicação temporária inválido.')
    spool = spool_directory() if spool is None else spool
    try:
        fd = os.open(spool / alias, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_size > 12800:
            raise ValueError('A publicação temporária foi alterada externamente.')
        values = dict(line.split('=', 1) for line in stream.read(12800).splitlines() if '=' in line)
        if values.get('sharename', alias) != alias:
            raise ValueError('O nome da publicação foi alterado externamente.')
        return values


def public(entry):
    alias = entry['alias']
    return {key: entry[key] for key in ('alias', 'folder', 'account', 'scope', 'state')} | {
        'expires': datetime.fromtimestamp(entry['expires'], timezone.utc).isoformat(),
        'address': '\\\\' + socket.gethostname() + '\\' + alias}


def grant(raw, username, scope, minutes):
    if scope not in PERMISSION or not 5 <= minutes <= 7 * 24 * 60:
        raise ValueError('Escolha leitura ou edição e um prazo de 5 minutos a 7 dias.')
    user, sid = account(username)
    with lock():
        shares = registered()
        folder, source, identity = dir_identity(raw, shares)
        local_permission(user, scope, folder)
        if len(list(records())) >= 100:
            raise ValueError('O limite de concessões foi atingido. Revogue uma concessão existente.')
        alias = 'linuxbr-temporario-' + secrets.token_hex(8)
        if alias in shares or (STATE / (alias + '.json')).exists():
            raise RuntimeError('O endereço temporário já existe. Tente novamente.')
        if run('systemctl', 'enable', '--now', 'linuxbr-share-grants.timer').returncode:
            raise ValueError('Não foi possível iniciar a revogação programada de compartilhamentos.')
        entry = {'alias': alias, 'folder': str(folder), 'source': source, 'identity': identity,
                 'account': user.pw_name, 'uid': user.pw_uid, 'sid': sid, 'scope': scope,
                 'expires': int(time.time()) + minutes * 60, 'state': 'pending',
                 'tag': 'Concessão Linux BR ' + alias}
        path = STATE / (alias + '.json')
        save(path, entry)
        result = run('net', 'usershare', 'add', alias, str(folder), entry['tag'],
                     sid + ':' + PERMISSION[scope], 'guest_ok=n')
        current = alias_file(alias) or {}
        if result.returncode or actual(current) != expected(entry):
            raise RuntimeError('O Samba não confirmou a publicação temporária. A limpeza será verificada pelo serviço.')
        entry['state'] = 'active'
        save(path, entry)
    return public(entry)


def stop(path, entry, startup=False):
    alias = entry['alias']
    if not PART.fullmatch(alias) or path != (STATE / (alias + '.json')):
        raise ValueError('Registro de concessão inválido.')
    spool = spool_directory()
    share = alias_file(alias, spool)
    if share is not None:
        if actual(share) != expected(entry):
            raise ValueError(f'A publicação {alias} foi alterada externamente. Confira-a no Samba.')
        (spool / alias).unlink(missing_ok=True)
    entry['state'] = 'revoking'
    save(path, entry)
    if not startup and run('systemctl', 'is-active', 'smbd.service').returncode == 0:
        if run('smbcontrol', '--timeout=5', 'smbd', 'close-share', alias).returncode:
            raise RuntimeError(f'O encerramento das conexões de {alias} será tentado novamente.')
    path.unlink()


def still_valid(entry, shares):
    origin = shares.get(entry['source'], {})
    try:
        target = Path(entry['folder']).lstat()
        return (origin.get('path', '').rstrip('/') == entry['folder'] and stat.S_ISDIR(target.st_mode)
                and [target.st_dev, target.st_ino] == entry['identity']
                and pwd.getpwnam(entry['account']).pw_uid == entry['uid'])
    except (KeyError, OSError):
        return False


def expire(startup=False):
    if not STATE.is_dir():
        return []
    failures = []
    with lock():
        pending = list(records())
        if not pending:
            return failures
        try:
            shares = registered()
        except (OSError, ValueError, subprocess.SubprocessError):
            shares = None
        for path, entry in pending:
            try:
                if (entry['state'] != 'active' or time.time() >= entry['expires'] or alias_file(entry['alias']) is None or
                        shares is not None and not still_valid(entry, shares)):
                    stop(path, entry, startup)
            except (KeyError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                failures.append(str(error))
    return failures


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(dest='action', required=True)
    issue = actions.add_parser('issue')
    for option in ('folder', 'account', 'scope'):
        issue.add_argument(option)
    issue.add_argument('minutes', type=int)
    actions.add_parser('list')
    revoke = actions.add_parser('revoke')
    revoke.add_argument('alias')
    check = actions.add_parser('expire')
    check.add_argument('--startup', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'A concessão exige autenticação administrativa.\n')
    try:
        if args.action == 'issue':
            result = grant(args.folder, args.account, args.scope, args.minutes)
        elif args.action == 'expire':
            failures = expire(args.startup)
            if failures:
                raise RuntimeError('\n'.join(failures))
            result = {'expired': True}
        else:
            with lock():
                if args.action == 'list':
                    result = [public(entry) for _, entry in records()]
                else:
                    found = next(((path, entry) for path, entry in records() if path.stem == args.alias), None)
                    if not found:
                        raise ValueError('A concessão já foi encerrada.')
                    stop(*found)
                    result = {'revoked': True}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except KeyError:
        print('A conta ou a concessão não está disponível.', file=sys.stderr)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
