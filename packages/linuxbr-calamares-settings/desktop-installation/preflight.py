"""Read-only storage and firmware checks for the Desktop installation."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys


def hibernation(path):
    device = Path(path)
    try:
        if not device.is_relative_to('/dev') or not stat.S_ISBLK(device.stat().st_mode):
            return 'unknown'
        # ntfscat opens the volume read-only. Read only the header and discard
        # it after evaluation. Never mount NTFS or use the read-write probe.
        with subprocess.Popen(
            ['/usr/bin/timeout', '--kill-after=1', '3', '/usr/bin/ntfscat', '--quiet', path, '/hiberfil.sys'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ) as process:
            with process.stdout:
                header = process.stdout.read(4096)
    except OSError:
        return 'unknown'
    if header[:4].lower() == b'hibr':
        return 'hibernated'
    if header == bytes(4096):
        return 'inactive'
    return 'unknown'


def protection(row):
    filesystem = (row.get('fstype') or '').lower()
    if filesystem == 'bitlocker':
        return 'bitlocker'
    if filesystem == 'crypto_luks':
        return 'luks'
    if filesystem == 'ntfs':
        return hibernation(row['path'])
    return ''


def scan_storage():
    result = subprocess.run(
        ['/usr/bin/lsblk', '--bytes', '--json', '--output',
         'NAME,PATH,TYPE,VENDOR,MODEL,SIZE,TRAN,FSTYPE,START'],
        stdout=subprocess.PIPE, text=True, check=True, timeout=6,
    )
    return storage_model(json.loads(result.stdout))


def extent(row):
    return dict(
        path=row['path'], filesystem=row.get('fstype') or '',
        start=int(row.get('start') or 0) * 512,
        size=int(row.get('size') or 0),
    )


def storage_model(report):
    devices = [row for row in report['blockdevices'] if row.get('type') in ('disk', 'mpath', 'raid0', 'raid1', 'raid5', 'raid6', 'raid10')]
    rows = []
    for device in devices:
        parts = [child for child in device.get('children', []) if child.get('type') == 'part']
        rows.extend([device, *parts])
    with ThreadPoolExecutor(max_workers=4) as pool:
        flags = dict(zip((entry['path'] for entry in rows), pool.map(protection, rows)))
    return [
        dict(
            **extent(disk), vendor=(disk.get('vendor') or '').strip(),
            model=(disk.get('model') or '').strip(), transport=(disk.get('tran') or '').strip(),
            protection=flags[disk['path']],
            volumes=[dict(**extent(part), protection=flags[part['path']])
                     for part in disk.get('children', []) if part.get('type') == 'part'],
        )
        for disk in devices
    ]


def firmware():
    efi = Path('/sys/firmware/efi')
    secure_boot = 'unknown'
    if efi.is_dir():
        try:
            variable = efi / 'efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c'
            state = variable.read_bytes()[4:]
            secure_boot = {b'\0': 'disabled', b'\1': 'enabled'}.get(state, 'unknown')
        except OSError:
            pass
    try:
        cpuinfo = Path('/proc/cpuinfo').read_text(encoding='ascii', errors='replace')
    except OSError:
        cpuinfo = ''
    flags = {flag for line in cpuinfo.splitlines() if line.startswith('flags')
             for flag in line.partition(':')[2].split()}
    try:
        kvm = stat.S_ISCHR(Path('/dev/kvm').stat().st_mode)
    except OSError:
        kvm = False
    acceleration = 'enabled' if kvm else 'no-kvm' if flags.intersection(('vmx', 'svm')) else 'unknown'
    return dict(mode='uefi' if efi.is_dir() else 'bios',
                secure_boot=secure_boot, acceleration=acceleration)


def play_test_sound():
    uid = int(os.environ.get('PKEXEC_UID', os.getuid()))
    sound = '/usr/share/sounds/freedesktop/stereo/bell.oga'
    command = ['/usr/bin/paplay', sound]
    if os.getuid() == 0 and uid:
        account = pwd.getpwuid(uid)
        command = ['/usr/sbin/runuser', '-u', account.pw_name, '--', '/usr/bin/env',
                   f'XDG_RUNTIME_DIR=/run/user/{uid}',
                   f'PULSE_SERVER=unix:/run/user/{uid}/pulse/native', *command]
    return subprocess.run(command, check=False, timeout=5).returncode


def main():
    if sys.argv[1:] == ['tone']:
        try:
            return play_test_sound()
        except (KeyError, ValueError, OSError, subprocess.SubprocessError):
            return 1
    report = dict(firmware=firmware(), disks=[], storage_available=False)
    try:
        report.update(disks=scan_storage(), storage_available=True)
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        pass
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
