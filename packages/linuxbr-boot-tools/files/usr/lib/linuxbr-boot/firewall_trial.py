"""Try one firewalld port change with a host-side rollback timer."""

import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic
from uuid import uuid4


STATE = Path('/run/linuxbr-firewall')
RULE = re.compile(r'([1-9][0-9]{0,4})/(tcp|udp)')
ZONE = re.compile(r'[A-Za-z0-9_-]{1,32}')
TOKEN = re.compile(r'[a-f0-9]{32}')


def run(*argv, check=True):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)
    if check and result.returncode:
        raise ValueError(result.stderr.strip() or 'A operação do firewall falhou.')
    return result


def firewalld(zone, option, permanent=False):
    return run('/usr/bin/firewall-cmd', *(['--permanent'] if permanent else []),
               '--zone=' + zone, option, check=False)


def query(zone, port, permanent=False):
    result = firewalld(zone, '--query-port=' + port, permanent)
    if result.returncode not in (0, 1) or result.stdout.strip() not in ('yes', 'no'):
        raise ValueError(result.stderr.strip() or 'Não foi possível consultar a porta na zona.')
    return result.returncode == 0


def update(zone, port, allowed, permanent=False):
    result = firewalld(zone, ('--add-port=' if allowed else '--remove-port=') + port, permanent)
    if result.returncode or query(zone, port, permanent) != allowed:
        raise ValueError(result.stderr.strip() or 'A alteração da porta não foi confirmada.')


def apply(argv):
    if os.geteuid() != 0:
        raise PermissionError('A alteração exige autorização administrativa.')
    STATE.mkdir(mode=0o700, exist_ok=True)
    if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o077:
        raise ValueError('O diretório de controle do firewall é inválido.')
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        pending = STATE / 'pending.json'
        if len(argv) == 4 and argv[0] == 'begin':
            _, zone, port, operation = argv
            match = RULE.fullmatch(port)
            if not ZONE.fullmatch(zone) or not match or int(match[1]) > 65535 or operation not in ('allow', 'remove'):
                raise ValueError('Informe uma zona, porta e operação válidas.')
            if pending.exists():
                raise ValueError('Aguarde a conclusão do teste de firewall em andamento.')
            previous = query(zone, port)
            if query(zone, port, True) != previous:
                raise ValueError('A regra temporária difere da regra salva. Resolva a diferença antes do teste.')
            allowed = operation == 'allow'
            if previous == allowed:
                raise ValueError('A porta já está no estado solicitado.')
            token = uuid4().hex
            with pending.open('x') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(dict(token=token, zone=zone, port=port, previous=previous, allowed=allowed,
                               deadline=monotonic() + 120), stream)
            try:
                run('/usr/bin/systemd-run', '--quiet', '--unit=linuxbr-firewall-' + token,
                    '--on-active=120s', '--timer-property=AccuracySec=1s', '--property=Restart=on-failure',
                    '--property=RestartSec=5s',
                    '/usr/bin/python3', '-I', str(Path(__file__).resolve()), 'rollback', token)
            except Exception:
                pending.unlink(missing_ok=True)
                raise
            update(zone, port, allowed)
            return token
        if len(argv) != 2 or argv[0] not in ('commit', 'rollback') or not TOKEN.fullmatch(argv[1]):
            raise ValueError('Ação de firewall inválida.')
        action, token = argv
        if not pending.exists():
            if action == 'rollback':
                return ''
            raise ValueError('O prazo de confirmação terminou.')
        data = json.loads(pending.read_text())
        if data['token'] != token:
            if action == 'rollback':
                return ''
            raise ValueError('A confirmação não corresponde ao teste ativo.')
        zone, port, previous, allowed = (data[field] for field in ('zone', 'port', 'previous', 'allowed'))
        if action == 'commit':
            if monotonic() >= data['deadline']:
                raise ValueError('O prazo de confirmação terminou.')
            if query(zone, port) != allowed or query(zone, port, True) != previous:
                raise ValueError('A regra mudou durante o teste. Aguarde a reversão antes de tentar novamente.')
            try:
                update(zone, port, allowed, True)
            except Exception:
                if query(zone, port, True) == allowed:
                    update(zone, port, previous, True)
                raise
        else:
            # The saved rule also needs repair after an interrupted commit.
            if query(zone, port, True) == allowed:
                update(zone, port, previous, True)
            if query(zone, port) == allowed:
                update(zone, port, previous)
        pending.unlink()
        return ''


if __name__ == '__main__':
    try:
        token = apply(sys.argv[1:])
        if token:
            print(token)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
