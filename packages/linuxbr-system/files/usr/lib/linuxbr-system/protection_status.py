"""Read native backup records and pre-update conditions without changing them."""
import configparser
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
from urllib.parse import unquote, urlsplit


def command(argv, timeout=8):
    try:
        process = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                 env={**os.environ, 'LC_ALL': 'C'})
        return process.returncode, process.stdout[:128000], process.stderr[:4000]
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, '', str(error)


def free_space(path):
    try:
        target = Path(path)
        if target.is_dir():
            return shutil.disk_usage(target).free
    except OSError:
        pass
    return None


def mounted_volumes():
    code, output, _ = command(['findmnt', '--json', '--output', 'UUID,TARGET,FSTYPE,SOURCE'])
    if code:
        return []
    try:
        records = json.loads(output).get('filesystems', [])
    except (ValueError, AttributeError):
        return []
    result = []
    def visit(items):
        for item in items:
            result.append(item)
            visit(item.get('children', []))
    visit(records)
    return result


def kconfig_date(value):
    if not value:
        return None
    try:
        fields = value.split(',')
        if len(fields) in (6, 7):
            from PyQt6.QtCore import QDate, QDateTime, QTime, QTimeZone, Qt
            seconds = Decimal(fields[5])
            integer = int(seconds)
            milliseconds = int(((seconds-integer)*1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            zone = QTimeZone(fields[6].encode('utf-8')) if len(fields) == 7 else QTimeZone.systemTimeZone()
            parsed = QDateTime(QDate(*map(int, fields[:3])), QTime(int(fields[3]), int(fields[4]), integer, milliseconds), zone)
            return parsed.toString(Qt.DateFormat.ISODateWithMs) if zone.isValid() and parsed.isValid() else None
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).isoformat()
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return None


def backup_plans(config_path=None, volumes=None, read_key=None):
    path = Path(config_path) if config_path else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'kuprc'
    if not path.is_file():
        return []
    parser = configparser.RawConfigParser(strict=False, interpolation=None)
    try:
        parser.read(path, encoding='utf-8')
    except (OSError, configparser.Error):
        return [{'name': 'Configuração de backup', 'error': 'Não foi possível ler os planos do Kup.'}]
    volumes = mounted_volumes() if volumes is None else volumes
    result = []
    for section in parser.sections():
        match = re.fullmatch(r'Plan(?:/|\]\[)(\d+)', section)
        if not match:
            continue
        group = 'Plan/' + match[1]
        def read(name, default=''):
            if read_key is not None:
                return read_key(group, name, default)
            code, output, _ = command(['kreadconfig6', '--file', str(path), '--group', group,
                                       '--key', name, '--default', default])
            if code == 0:
                return output.rstrip('\n')
            return parser.get(section, name, fallback=default)
        enabled = parser.get('General', 'Backups enabled', fallback='false').strip().lower() in ('true', 'yes', 'on', '1')
        item = {'id': match[1], 'name': read('Description', 'Plano ' + match[1]), 'enabled': enabled,
                'last_complete': kconfig_date(read('Last complete backup')),
                'type': 'versions' if read('Backup type', '0') == '0' else 'sync',
                'schedule': read('Schedule type', '2'), 'destination': None, 'available': False, 'free': None}
        if read('Destination type', '1') == '0':
            value = read('Filesystem destination path')
            address = urlsplit(value)
            if address.scheme == 'file' and address.netloc in ('', 'localhost'):
                value = unquote(address.path)
            elif address.scheme:
                value = ''
            if value and Path(value).is_absolute():
                item['destination'] = value
        else:
            identity = read('External drive UUID')
            relative = Path(read('External drive destination path', 'Backups'))
            point = next((entry.get('target') for entry in volumes if entry.get('uuid') == identity and identity), None)
            if point and not relative.is_absolute() and '..' not in relative.parts:
                item['destination'] = str(Path(point) / relative)
        if item['destination']:
            item['free'] = free_space(item['destination'])
            item['available'] = item['free'] is not None
        result.append(item)
    return result


def snapshot_status(volumes=None):
    import snapshot_service
    info = snapshot_service.status()
    config = snapshot_service.read_json(snapshot_service.CONFIG)
    identity = config.get('backup_device_uuid')
    volumes = mounted_volumes() if volumes is None else volumes
    point = next((item.get('target') for item in volumes if item.get('uuid') == identity and identity), None)
    info['destination'] = point
    info['destination_available'] = bool(point)
    info['free'] = free_space(point) if point else None
    success = info.get('last_success', {})
    info['last_success'] = success.get('time') if isinstance(success, dict) else None
    return info


def index_validity(directory=Path('/var/lib/apt/lists')):
    now = datetime.now(timezone.utc)
    result = []
    for path in sorted(Path(directory).glob('*InRelease')):
        if 'linuxbr' not in path.name.lower() and '8443' not in path.name:
            continue
        try:
            content = path.read_text(encoding='utf-8')
            match = re.search(r'^Valid-Until:\s*(.+)$', content, re.M)
            expiration = parsedate_to_datetime(match[1]) if match else None
            result.append({'index': path.name, 'valid_until': expiration.isoformat() if expiration else None,
                           'expired': expiration < now if expiration else None,
                           'days_remaining': int((expiration-now).total_seconds()//86400) if expiration else None})
        except (OSError, ValueError, TypeError, OverflowError):
            result.append({'index': path.name, 'valid_until': None, 'expired': None, 'days_remaining': None})
    return result


def power_status(base=Path('/sys/class/power_supply')):
    ac = []; batteries = []
    for path in Path(base).glob('*'):
        try:
            kind = (path/'type').read_text().strip()
            if kind in ('Mains', 'USB', 'USB_C') and (path/'online').is_file():
                ac.append((path/'online').read_text().strip() == '1')
            elif kind == 'Battery' and (path/'capacity').is_file():
                batteries.append(int((path/'capacity').read_text()))
        except (OSError, ValueError):
            pass
    return {'ac': any(ac) if ac else None, 'battery': min(batteries) if batteries else None}


def preflight(root=Path('/')):
    code, output, error = command(['dpkg', '--audit'], timeout=15)
    free = free_space(root)
    power = power_status()
    warnings = []
    if code != 0: warnings.append('Não foi possível conferir o estado dos pacotes.')
    elif output.strip(): warnings.append('O gerenciador informou pacotes pendentes de configuração. Confira os detalhes antes de atualizar.')
    if free is not None and free < 2 * 1024**3:
        warnings.append('Há menos de 2 GiB livres na raiz. Confira o espaço necessário para a atualização.')
    if power['ac'] is False:
        warnings.append('O computador está na bateria. Conecte a alimentação antes de atualizar.')
    if power['battery'] is not None and power['battery'] < 20:
        warnings.append('A carga da bateria está abaixo de 20%.')
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'free': free,
            'dpkg_audit': output.strip(), 'dpkg_audit_error': error if code else '',
            'power': power, 'warnings': warnings}


def protection_report():
    volumes = mounted_volumes()
    return {'backups': backup_plans(volumes=volumes), 'snapshots': snapshot_status(volumes),
            'preflight': preflight(), 'indexes': index_validity()}


def repository_addresses(directory=Path('/etc/apt/sources.list.d')):
    result = []
    for path in Path(directory).glob('*'):
        if 'linuxbr' not in path.name.lower() or path.suffix not in ('.sources', '.list'):
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        for stanza in re.split(r'\n\s*\n', text):
            if re.search(r'^Enabled:\s*no\s*$', stanza, re.I | re.M):
                continue
            for line in stanza.splitlines():
                line = line.strip()
                if line.startswith('#'):
                    continue
                if line.lower().startswith('uris:'):
                    result.extend(line.split(':', 1)[1].split())
                elif line.startswith('deb '):
                    result.extend(re.findall(r'https://\S+', line)[:1])
    return sorted(set(value for value in result if value.startswith('https://')))


def check_repository_tls(address, ca_file=Path('/etc/apt/certs/linuxbr-local-ca.crt')):
    parsed = urlsplit(address)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use um endereço HTTPS sem credenciais.')
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file.is_file() else None)
    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=5) as connection:
        with context.wrap_socket(connection, server_hostname=parsed.hostname) as secured:
            certificate = secured.getpeercert()
            expiration = datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate['notAfter']), timezone.utc)
            return {'address': address, 'verified': True, 'expires_at': expiration.isoformat(),
                    'days_remaining': int((expiration-datetime.now(timezone.utc)).total_seconds()//86400)}


if __name__ == '__main__':
    print(json.dumps(protection_report(), ensure_ascii=False))
