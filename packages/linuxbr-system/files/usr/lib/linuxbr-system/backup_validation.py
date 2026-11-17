"""Verify Restic indexes, sample repository data and recover one test file."""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from credentials import inspect_store, libraries
from network_backup import absolute_path, command, password_input, repository

TIMER = 'linuxbr-backup-validation.timer'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'linuxbr' / 'backup-validation.json'
RESULT = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'linuxbr' / 'backup-validation.json'


def load(path):
    try:
        with path.open(encoding='utf-8') as stream:
            result = json.loads(stream.read(32768))
        if isinstance(result, dict):
            return result
    except (OSError, UnicodeError, ValueError):
        pass
    return {}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def secret(repo, value=None, clear=False):
    gio, provider = libraries()
    if inspect_store()['state'] != 'ready':
        raise RuntimeError('Desbloqueie o cofre de credenciais para verificar o backup.')
    schema = provider.Schema.new('org.linuxbr.BackupValidation', provider.SchemaFlags.NONE,
                                 {'repository': provider.SchemaAttributeType.STRING})
    attrs = {'repository': hashlib.sha256(repo.encode()).hexdigest()}
    cancel = gio.Cancellable()
    deadline = threading.Timer(5, cancel.cancel)
    deadline.daemon = True
    deadline.start()
    try:
        if clear:
            provider.password_clear_sync(schema, attrs, cancel)
            return None
        if value is None:
            result = provider.password_lookup_sync(schema, attrs, cancel)
            if not result:
                raise RuntimeError('A senha do backup precisa ser salva novamente no cofre.')
            return password_input(result)
        if not provider.password_store_sync(schema, attrs, provider.COLLECTION_DEFAULT,
                                            'Linux BR – verificação de backup', value.decode().strip(), cancel):
            raise RuntimeError('Não foi possível salvar a senha no cofre de credenciais.')
    finally:
        deadline.cancel()


def validate(repo, source, password, run=subprocess.run):
    attempts = [('index_and_sample', ('check', '--read-data-subset=50M'), 1200),
                ('file', ('dump', 'latest', absolute_path(source)), 300)]
    result = {'repository': repo, 'checked_at': datetime.now(timezone.utc).isoformat(),
              'index_and_sample': False, 'file': False}
    for name, args, timeout in attempts:
        try:
            successful = run(command(repo, *args), input=password, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, timeout=timeout, check=False).returncode == 0
        except (OSError, subprocess.SubprocessError):
            successful = False
        result[name] = successful
        if not successful:
            break
    if result['file']:
        result['recovered_at'] = datetime.now(timezone.utc).isoformat()
    else:
        past = load(RESULT)
        if past.get('repository') == repo:
            result['recovered_at'] = past.get('recovered_at')
    return result


def timer(*options):
    subprocess.run(['/usr/bin/systemctl', '--user', *options, TIMER], check=True, timeout=12)


def check_locked(repo, source, password):
    RESULT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = os.open(RESULT.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Já existe uma verificação de backup em andamento.') from None
        result = validate(repo, source, password)
        write(RESULT, result)
        return result
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'check', 'enable', 'disable'))
    parser.add_argument('--host')
    parser.add_argument('--user')
    parser.add_argument('--port', type=int)
    parser.add_argument('--directory')
    parser.add_argument('--source')
    args = parser.parse_args()
    try:
        old = load(CONFIG)
        if args.action == 'disable':
            timer('disable', '--now')
            CONFIG.unlink(missing_ok=True)
            if old.get('repository'):
                secret(old['repository'], clear=True)
            return 0
        if args.action == 'run':
            if not old:
                return 0
            repo, source = old['repository'], old['source']
            try:
                password = secret(repo)
            except Exception:
                previous = load(RESULT)
                write(RESULT, {'repository': repo, 'checked_at': datetime.now(timezone.utc).isoformat(),
                               'credential_unavailable': True,
                               'recovered_at': previous.get('recovered_at') if previous.get('repository') == repo else None})
                raise RuntimeError('A senha do backup está indisponível no cofre de credenciais.') from None
        else:
            repo = repository(args.host, args.user, args.port, args.directory)
            source = absolute_path(args.source)
            password = password_input(sys.stdin.buffer.readline(4096).decode().removesuffix('\n'))
        if args.action == 'enable':
            secret(repo, password)
            write(CONFIG, {'repository': repo, 'source': source})
            try:
                timer('enable', '--now')
            except (OSError, subprocess.SubprocessError):
                if old:
                    write(CONFIG, old)
                else:
                    CONFIG.unlink(missing_ok=True)
                if old.get('repository') != repo:
                    secret(repo, clear=True)
                raise
            if old.get('repository') and old['repository'] != repo:
                secret(old['repository'], clear=True)
            print('Verificação semanal ativada para esta conta.')
            return 0
        result = check_locked(repo, source, password)
        if not result['index_and_sample']:
            raise RuntimeError('A verificação dos índices e da amostra falhou. Confira a conexão e o repositório.')
        print('Índices e amostra do repositório verificados.')
        if not result['file']:
            raise RuntimeError('O arquivo de teste não pôde ser recuperado da cópia mais recente.')
        print('Arquivo de teste recuperado e conferido sem gravar sobre os originais.')
        return 0
    except (OSError, subprocess.SubprocessError, RuntimeError, TypeError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print('Não foi possível usar o cofre de credenciais da sessão.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
