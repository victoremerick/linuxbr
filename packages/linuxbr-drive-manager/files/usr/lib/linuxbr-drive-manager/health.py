"""Track the SMART telemetry that UDisks2 reports for attached drives."""

from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

from core import PREFIX


BUS = 'org.freedesktop.UDisks2'
ATA = PREFIX + 'Drive.Ata'
NVME = PREFIX + 'NVMe.Controller'
INTERVAL_SECONDS = 30 * 60
HISTORY_DAYS = 90
MAX_SAMPLES = 240
MAX_DRIVES = 64
MAX_BYTES = 4 * 1024 * 1024
COUNT_LABELS = {
    'bad_sectors': 'Setores defeituosos',
    'attributes_failing': 'Atributos SMART em falha',
    'attributes_failed_before': 'Atributos com falhas anteriores',
    'media_errors': 'Erros de mídia e integridade',
    'error_log_entries': 'Registros de erro do controlador',
    'unsafe_shutdowns': 'Desligamentos sem notificação',
}
WARNING_LABELS = {
    'spare': 'Reserva abaixo do limite',
    'temperature': 'Aviso de temperatura',
    'degraded': 'Confiabilidade degradada',
    'readonly': 'Mídia em modo somente leitura',
    'volatile-mem': 'Falha na proteção da memória volátil',
    'pmr-readonly': 'Região persistente em modo somente leitura',
}


def count(value):
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if 0 <= number <= 2**64 - 1 else None


def temperature(kelvin):
    try:
        celsius = float(kelvin) - 273.15
    except (TypeError, ValueError, OverflowError):
        return None
    return round(celsius, 1) if -50 <= celsius <= 180 else None


def drive_identity(drive):
    wwn = str(drive.get('WWN') or '').strip()
    serial = str(drive.get('Serial') or '').strip()
    vendor = str(drive.get('Vendor') or '').strip()
    model = str(drive.get('Model') or '').strip()
    if not wwn and not serial:
        return ''
    fields = ['wwn', wwn] if wwn else ['serial', vendor, model, serial]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode()).hexdigest()


def supported_drives(objects):
    for path, interfaces in objects.items():
        drive = interfaces.get(PREFIX + 'Drive')
        if not drive or not drive.get('MediaAvailable', True):
            continue
        if NVME in interfaces:
            yield str(path), drive, NVME
        elif interfaces.get(ATA, {}).get('SmartSupported'):
            yield str(path), drive, ATA


def sample(protocol, properties, attributes=None, now=None):
    timestamp = count(properties.get('SmartUpdated'))
    now = time.time() if now is None else now
    if not timestamp or timestamp > now + 300:
        return None
    item = {'read_at': timestamp}
    temp = temperature(properties.get('SmartTemperature'))
    if temp is not None:
        item['temperature'] = temp
    if protocol == ATA:
        if not properties.get('SmartEnabled'):
            return None
        item['warnings'] = ['smart-failing'] if properties.get('SmartFailing') else []
        counters = {'bad_sectors': properties.get('SmartNumBadSectors'),
                    'attributes_failing': properties.get('SmartNumAttributesFailing'),
                    'attributes_failed_before': properties.get('SmartNumAttributesFailedInThePast')}
    else:
        item['warnings'] = [str(value)[:80] for value in properties.get('SmartCriticalWarning', [])][:16]
        attrs = attributes or {}
        counters = {'media_errors': attrs.get('media_errors'),
                    'error_log_entries': attrs.get('num_err_log_entries'),
                    'unsafe_shutdowns': attrs.get('unsafe_shutdowns'),
                    'percent_used': attrs.get('percent_used')}
    item.update({key: number for key, value in counters.items() if (number := count(value)) is not None})
    return item


def alerts(previous, current):
    if not current:
        return []
    messages = [WARNING_LABELS.get(value, 'Alerta SMART informado pela unidade')
                if value != 'smart-failing' else 'SMART informa possível falha da unidade.'
                for value in current.get('warnings', [])]
    if previous:
        for key, label in COUNT_LABELS.items():
            before = count(previous.get(key))
            after = count(current.get(key))
            if before is not None and after is not None and after > before:
                messages.append(f'{label} aumentaram em {after - before} desde a leitura anterior.')
    if current.get('bad_sectors', 0) and not any(msg.startswith(COUNT_LABELS['bad_sectors']) for msg in messages):
        messages.append('A unidade informou setores defeituosos.')
    if current.get('media_errors', 0) and not any(msg.startswith(COUNT_LABELS['media_errors']) for msg in messages):
        messages.append('A unidade informou erros de mídia ou integridade.')
    if current.get('percent_used', 0) >= 100:
        messages.append('A estimativa de vida útil usada atingiu o valor nominal de 100%.')
    return list(dict.fromkeys(messages))


class History:
    def __init__(self, path=None):
        home = os.environ.get('XDG_STATE_HOME') or str(Path.home() / '.local/state')
        self.path = Path(path) if path else Path(home) / 'linuxbr/storage-health.json'

    def read(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return {}
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
                raise ValueError('O arquivo de histórico de saúde foi preservado porque está inválido.')
            data = json.load(stream)
        if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('disks'), dict):
            raise ValueError('O arquivo de histórico de saúde foi preservado porque está inválido.')
        for key, item in data['disks'].items():
            if (len(key) != 64 or not isinstance(item, dict) or not isinstance(item.get('samples'), list)
                    or any(not isinstance(row, dict) or type(row.get('read_at')) is not int or row['read_at'] <= 0
                           for row in item['samples'])):
                raise ValueError('O arquivo de histórico de saúde contém uma leitura inválida.')
        return data['disks']

    def record(self, drives, now=None):
        now = int(time.time()) if now is None else now
        cutoff = now - HISTORY_DAYS * 86_400
        identities = Counter(drive['id'] for drive in drives if drive['id'])
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(str(self.path) + '.lock', os.O_CREAT | os.O_NOFOLLOW | os.O_WRONLY | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            history = self.read()
            initial = json.dumps(history, sort_keys=True)
            for drive in drives:
                identity, current = drive['id'], drive['current']
                if not identity or identities[identity] != 1 or not current:
                    continue
                entry = history.setdefault(identity, {'samples': [], 'device': drive['name'], 'protocol': drive['protocol']})
                readings = entry['samples']
                if not readings or current['read_at'] > readings[-1]['read_at']:
                    readings.append(current)
                elif current['read_at'] == readings[-1]['read_at'] and current != readings[-1]:
                    readings[-1] = current
            for identity, entry in list(history.items()):
                recent = [row for row in entry['samples'] if row['read_at'] >= cutoff]
                if recent:
                    entry['samples'] = recent[-MAX_SAMPLES:]
                else:
                    del history[identity]
            if len(history) > MAX_DRIVES:
                history = dict(sorted(history.items(), key=lambda pair: pair[1]['samples'][-1]['read_at'],
                                      reverse=True)[:MAX_DRIVES])
            if json.dumps(history, sort_keys=True) != initial:
                with tempfile.NamedTemporaryFile('w', dir=self.path.parent, prefix='.storage-health-',
                                                 delete=False, encoding='utf-8') as stream:
                    temporary = Path(stream.name)
                    try:
                        json.dump({'schema': 1, 'disks': history}, stream, ensure_ascii=False, separators=(',', ':'))
                        stream.flush()
                        os.fsync(stream.fileno())
                        os.replace(temporary, self.path)
                    finally:
                        temporary.unlink(missing_ok=True)
        return history, identities


def collect(bus, manager, objects):
    # Interact with the standard UDisks2 SMART API only. An inactive session
    # cannot trigger an authentication dialog or a command that wakes SATA.
    import dbus
    from core import decode

    for path, drive, protocol in supported_drives(objects):
        if protocol == ATA and not objects[path][ATA].get('SmartEnabled'):
            continue
        options = {'auth.no_user_interaction': dbus.Boolean(True)}
        if protocol == ATA:
            options['nowakeup'] = dbus.Boolean(True)
        try:
            device = bus.get_object(BUS, path, introspect=False)
            dbus.Interface(device, protocol).SmartUpdate(dbus.Dictionary(options, signature='sv'), timeout=3)
        except dbus.DBusException:
            pass
    objects = manager.GetManagedObjects(timeout=20)
    drives = []
    for path, drive, protocol in supported_drives(objects):
        attrs = None
        if protocol == NVME and objects[path][protocol].get('SmartUpdated'):
            try:
                device = bus.get_object(BUS, path, introspect=False)
                attrs = dbus.Interface(device, protocol).SmartGetAttributes(
                    dbus.Dictionary({}, signature='sv'), timeout=3)
            except dbus.DBusException:
                pass
        name = ' '.join(str(drive.get(key) or '').strip() for key in ('Vendor', 'Model')).strip() or 'Disco'
        block = next((iface[PREFIX + 'Block'] for iface in objects.values()
                      if str(iface.get(PREFIX + 'Block', {}).get('Drive', '')) == path
                      and PREFIX + 'Partition' not in iface), {})
        drives.append({'id': drive_identity(drive), 'name': name[:180],
                       'node': decode(block['Device']) if block.get('Device') else '',
                       'protocol': 'NVMe' if protocol == NVME else 'ATA',
                       'enabled': protocol == NVME or bool(objects[path][ATA].get('SmartEnabled')),
                       'current': sample(protocol, objects[path][protocol], attrs), 'connected': True})
    history, identities = History().record(drives)
    for drive in drives:
        identity = drive.pop('id')
        drive['history_available'] = bool(identity) and identities[identity] == 1
        records = history.get(identity, {}).get('samples', []) if drive['history_available'] else []
        current = drive['current'] or (records[-1] if records else None)
        prior = next((row for row in reversed(records) if current and row['read_at'] < current['read_at']), None)
        drive['alerts'] = alerts(prior, current)
        drive['samples'] = records
    for identity, entry in history.items():
        if identity not in identities:
            records = entry['samples']
            drives.append({'name': entry.get('device', 'Disco'), 'protocol': entry.get('protocol', 'SMART'),
                           'node': '', 'enabled': True, 'current': None, 'connected': False,
                           'history_available': True, 'samples': records,
                           'alerts': alerts(records[-2] if len(records) > 1 else None, records[-1])})
    return drives
