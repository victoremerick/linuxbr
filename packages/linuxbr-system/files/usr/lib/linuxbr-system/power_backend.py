"""PowerDevil profile settings used by the embedded energy page."""
from hashlib import sha256
from pathlib import Path
import subprocess

PROFILES = ('AC', 'Battery', 'LowBattery')
DEFAULTS = {
    'AC': (600, 900), 'Battery': (300, 600), 'LowBattery': (120, 300),
}
ACTION_VALUES = (0, 1, 2, 8, 16, 32, 64, 128)


def battery_report(root=Path('/sys/class/power_supply')):
    def read_text(device, field):
        try:
            return (device / field).read_text().strip()
        except OSError:
            return ''

    def number(device, field):
        try:
            value = int(read_text(device, field))
            return value if value >= 0 else None
        except ValueError:
            return None

    reports = []
    for device in sorted(root.glob('*')):
        if read_text(device, 'type') != 'Battery' or read_text(device, 'present') == '0':
            continue
        if read_text(device, 'scope') == 'Device':
            continue
        capacity = [(number(device, f'{field}_full_design'), number(device, f'{field}_full'), unit)
                    for field, unit in (('energy', 'Wh'), ('charge', 'Ah'))]
        design, full, unit = max(capacity, key=lambda entry: sum(value is not None for value in entry[:2]))
        model = read_text(device, 'model_name')
        manufacturer = read_text(device, 'manufacturer')
        serial = read_text(device, 'serial_number')
        identity = sha256(f'{manufacturer}\0{model}\0{serial}'.encode()).hexdigest() if serial and serial not in ('0', '0000') else ''
        reports.append({
            'name': ' '.join(filter(None, (manufacturer, model))) or device.name,
            'design': design / 1_000_000 if design is not None else None,
            'full': full / 1_000_000 if full is not None else None,
            'unit': unit,
            'health': full * 100 / design if design and full is not None else None,
            'cycles': number(device, 'cycle_count'),
            'identity': identity,
        })
    return reports


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=5).stdout.strip()


def read(profile, section, key, default):
    if profile not in PROFILES or section not in ('Display', 'SuspendAndShutdown'):
        raise ValueError('Grupo de energia inválido.')
    try:
        return command('kreadconfig6', '--file', 'powerdevilrc', '--group', profile,
                       '--group', section, '--key', key) or str(default)
    except (OSError, subprocess.SubprocessError):
        return str(default)


def profile(profile):
    if profile not in PROFILES:
        raise ValueError('Perfil de energia inválido.')
    screen, suspend = DEFAULTS[profile]
    try:
        virtual = subprocess.run(['systemd-detect-virt', '--quiet'],
                                 capture_output=True, timeout=3).returncode == 0
    except (OSError, subprocess.SubprocessError):
        virtual = False
    return {
        'screen': int(read(profile, 'Display', 'TurnOffDisplayIdleTimeoutSec', screen)),
        'screen_enabled': read(profile, 'Display', 'TurnOffDisplayWhenIdle', 'true').lower() == 'true',
        'suspend': int(read(profile, 'SuspendAndShutdown', 'AutoSuspendIdleTimeoutSec', suspend)),
        'suspend_action': int(read(profile, 'SuspendAndShutdown', 'AutoSuspendAction', 0 if virtual else 1)),
        'lid': int(read(profile, 'SuspendAndShutdown', 'LidAction', 0 if virtual else 1)),
        'power': int(read(profile, 'SuspendAndShutdown', 'PowerButtonAction', 16)),
    }


def write(profile_id, values, original=None):
    if profile_id not in PROFILES:
        raise ValueError('Perfil de energia inválido.')
    for field in ('screen', 'suspend'):
        if not 30 <= int(values[field]) <= 86400:
            raise ValueError('Tempo de energia fora do intervalo permitido.')
    for field in ('suspend_action', 'lid', 'power'):
        if int(values[field]) not in ACTION_VALUES:
            raise ValueError('Ação de energia inválida.')
    entries = (
        ('Display', 'TurnOffDisplayWhenIdle', 'true' if values['screen_enabled'] else 'false'),
        ('Display', 'TurnOffDisplayIdleTimeoutSec', str(values['screen'])),
        ('SuspendAndShutdown', 'AutoSuspendAction', str(values['suspend_action'])),
        ('SuspendAndShutdown', 'AutoSuspendIdleTimeoutSec', str(values['suspend'])),
        ('SuspendAndShutdown', 'LidAction', str(values['lid'])),
        ('SuspendAndShutdown', 'PowerButtonAction', str(values['power'])),
    )
    fields = ('screen_enabled', 'screen', 'suspend_action', 'suspend', 'lid', 'power')
    for field, (section, key, value) in zip(fields, entries):
        if original is not None and values[field] == original[field]:
            continue
        command('kwriteconfig6', '--file', 'powerdevilrc', '--group', profile_id,
                '--group', section, '--key', key, value)
    if original is None or any(values[field] != original[field] for field in fields):
        command('dbus-send', '--session', '--type=method_call', '--dest=org.kde.Solid.PowerManagement',
                '/org/kde/Solid/PowerManagement', 'org.kde.Solid.PowerManagement.refreshStatus')
