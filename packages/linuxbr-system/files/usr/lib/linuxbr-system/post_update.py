"""Check the first installed-system boot after a managed update."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time

from snapshot_service import (STATE, LIVE, REVISION, PACKAGE, VERSION, ARCHITECTURE,
                              read_json, restored_revisions, snapshot_lock)
from update_waves import decode_manifest, HttpStatusError, read_config, request, request_json

REPORT = 'boot-check.json'
MIN_FREE = 1024 ** 3
MESSAGES = {
    'packages': 'Pacotes da revisão',
    'session': 'Sessão gráfica ou tela de login',
    'network': 'Conectividade local',
    'storage': 'Armazenamento raiz gravável com espaço disponível',
}


def command(*argv):
    try:
        run = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False,
                             env={'LC_ALL': 'C', 'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
        return run.stdout.strip() if run.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def installed_targets(targets):
    if not isinstance(targets, list) or not 0 < len(targets) <= 4096:
        return False
    expected = set()
    for target in targets:
        if not isinstance(target, dict):
            return False
        package, version, arch = (target.get(key) for key in ('package', 'version', 'architecture'))
        if not all(isinstance(value, str) and pattern.fullmatch(value)
                   for value, pattern in ((package, PACKAGE), (version, VERSION), (arch, ARCHITECTURE))):
            return False
        expected.add((package, arch, version, 'installed'))
    actual = {tuple(line.split('\t')) for line in command(
        '/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Architecture}\t${Version}\t${db:Status-Status}\n'
    ).splitlines()}
    return expected <= actual


def session_ready():
    sessions = command('/usr/bin/loginctl', 'list-sessions', '--no-legend').splitlines()
    for line in sessions[:16]:
        fields = line.split()
        if not fields or not fields[0].isalnum():
            continue
        properties = set(command('/usr/bin/loginctl', 'show-session', fields[0],
                                 '-p', 'Type', '-p', 'Class', '-p', 'Active').splitlines())
        if {'Class=user', 'Active=yes'} <= properties and properties.intersection({'Type=wayland', 'Type=x11'}):
            return True
    return command('/usr/bin/systemctl', 'is-active', 'display-manager.service') == 'active'


def network_ready():
    state = command('/usr/bin/nmcli', '--terse', '--fields', 'STATE', 'general', 'status')
    if state:
        return state.startswith('connected')
    return bool(command('/usr/sbin/ip', 'route', 'show', 'default') or
                command('/usr/sbin/ip', '-6', 'route', 'show', 'default'))


def storage_ready():
    try:
        return not os.statvfs('/').f_flag & os.ST_RDONLY and shutil.disk_usage('/').free >= MIN_FREE
    except OSError:
        return False


def custom_health(config, revision):
    if not config or 'endpoint' not in config:
        return {}
    nonce = secrets.token_hex(32)
    try:
        document = decode_manifest(request(config, 'POST', '/v1/health-checks',
                                           {'nonce': nonce, 'revision': revision}))
    except HttpStatusError as error:
        if error.status == 404:
            return {}
        raise
    expected = dict(schema=1, kind='linuxbr-wave-health', device=config['device'],
                    organization=config['organization'], revision=revision, nonce=nonce)
    if not isinstance(document, dict) or any(document.get(field) != value for field, value in expected.items()):
        raise ValueError('Os testes de saúde não correspondem à revisão ou ao dispositivo.')
    checks = document.get('checks')
    if checks is None:
        return {}
    if not isinstance(checks, dict) or set(checks) != {'services', 'packages'}:
        raise ValueError('Testes de saúde inválidos.')
    result = {}
    for field, pattern in (('services', r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,119}\.service'),
                           ('packages', r'[a-z0-9][a-z0-9+.-]{0,119}(?::[a-z0-9-]{1,20})?')):
        names = checks[field]
        if not isinstance(names, list) or len(names) > 12 or any(
                not isinstance(name, str) or not re.fullmatch(pattern, name) for name in names):
            raise ValueError('Um serviço ou pacote da revisão é inválido.')
        for name in names:
            if field == 'services':
                ready = command('/usr/bin/systemctl', 'is-active', '--', name) == 'active'
            else:
                ready = command('/usr/bin/dpkg-query', '-W', '-f=${db:Status-Status}', '--', name) == 'installed'
            result[field + ':' + name] = ready
    return result


def came_from_earlier_boot(transaction, now=None):
    try:
        changed = datetime.fromisoformat(transaction['time'])
        uptime = float(Path('/proc/uptime').read_text().split()[0])
    except (KeyError, TypeError, ValueError, IndexError, OSError):
        return False
    return changed.tzinfo is not None and changed.timestamp() < (time.time() if now is None else now) - uptime


def save(report):
    with tempfile.NamedTemporaryFile('w', dir=STATE, prefix='.boot-check-', delete=False, encoding='utf-8') as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), 0o644)
            json.dump(report, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, STATE / REPORT)
        finally:
            temporary.unlink(missing_ok=True)


def run():
    if LIVE.is_dir() or not (STATE / 'last-managed.json').is_file():
        return
    with snapshot_lock():
        transaction = read_json(STATE / 'last-managed.json', strict=True)
        revision = transaction.get('revision')
        point = transaction.get('point_comment')
        if (transaction.get('status') != 'created' or not isinstance(revision, str) or not REVISION.fullmatch(revision)
                or not isinstance(point, str) or revision in restored_revisions()
                or not came_from_earlier_boot(transaction)):
            return
        previous = read_json(STATE / REPORT, strict=True)
        config = read_config()
        if previous.get('point') == point and previous.get('revision') == revision:
            report = previous
        else:
            checks = {'packages': installed_targets(transaction.get('targets')),
                      'session': session_ready(), 'network': network_ready(), 'storage': storage_ready()}
            report = {'schema': 1, 'revision': revision, 'point': point, 'checks': checks,
                      'checked_at': datetime.now(timezone.utc).isoformat(),
                      'state': 'completed' if all(checks.values()) else 'failed', 'notified': False}
            save(report)
        if config and 'endpoint' in config and not report.get('notified'):
            if not report.get('custom_health_checked'):
                custom = custom_health(config, revision)
                report['custom_health_checked'] = True
                if custom:
                    report['custom_checks'] = custom
                    if not all(custom.values()):
                        report['state'] = 'failed'
                save(report)
            result = {'revision': revision, 'state': report['state']}
            if report.get('custom_checks'):
                result['checks'] = report['custom_checks']
            request_json(config, 'POST', '/v1/result', result)
            report['notified'] = True
            save(report)


if __name__ == '__main__':
    run()
