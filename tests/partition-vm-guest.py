#!/usr/bin/python3
"""Destructive test ONLY inside the purpose-built disposable QEMU guest."""
import hashlib
import json
import os
import pwd
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, '/opt/linuxbr-partition-test/code')
import dbus
from core import PREFIX
from partitioning import MIB, describe


def command(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def log(message):
    print(message, flush=True)


def wait_for(fn, timeout=30):
    limit = time.monotonic()+timeout
    while time.monotonic() < limit:
        value = fn()
        if value: return value
        time.sleep(.25)
    raise RuntimeError('Timed out waiting for UDisks state')


def main():
    if 'linuxbr.partition-test=1' not in Path('/proc/cmdline').read_text():
        raise RuntimeError('Missing disposable guest marker')
    if command('systemd-detect-virt') not in ('qemu', 'kvm'):
        raise RuntimeError('Not a QEMU guest')
    # No test operation occurs until BOTH independent disposable serials are checked.
    disks = [('vda', 'LINUXBR-TEST-GPT', 'gpt'), ('vdb', 'LINUXBR-TEST-MBR', 'dos')]
    for name, serial, _ in disks:
        assert Path(f'/sys/class/block/{name}/serial').read_text().strip() == serial
        assert int(Path(f'/sys/class/block/{name}/size').read_text()) == 2*1024**3//512
    assert not list(Path('/sys/class/block').glob('nvme*'))
    log('ENVIRONMENT '+command('uname', '-r'))
    log(command('dpkg-query', '-W', '-f=${Package} ${Version}\n', 'udisks2', 'libblockdev-fs3', 'e2fsprogs', 'ntfs-3g', 'exfatprogs', 'dosfstools'))
    runtime=Path('/run/linuxbr-partition-test'); runtime.mkdir(mode=0o700, exist_ok=True)
    os.environ['XDG_RUNTIME_DIR']=str(runtime)
    mount=Path('/mnt/linuxbr-test'); mount.mkdir(exist_ok=True)
    bus=dbus.SystemBus()
    manager=dbus.Interface(bus.get_object('org.freedesktop.UDisks2','/org/freedesktop/UDisks2'), 'org.freedesktop.DBus.ObjectManager')
    def snapshot(name):
        return describe(manager.GetManagedObjects(), '/org/freedesktop/UDisks2/block_devices/'+name)
    def execute(request, expect_error=False, prefix=()):
        result=subprocess.run([*prefix, sys.executable, '/opt/linuxbr-partition-test/code/backend.py', 'partition', json.dumps(request)], text=True, capture_output=True)
        log('OPERATION '+json.dumps(request, sort_keys=True))
        log('RESULT '+result.stdout.strip())
        if result.stderr: log('STDERR '+result.stderr.strip())
        if expect_error:
            assert result.returncode != 0, 'Operation unexpectedly accepted'
        else:
            assert result.returncode == 0, result.stdout+result.stderr
        return result
    def request(name, action, **kwargs):
        s=snapshot(name)
        return dict(action=action, disk=s['path'], token=s['token'], **kwargs)
    def part(name):
        return wait_for(lambda: snapshot(name)['parts'])[0]
    def verify_files(device, checksums):
        command('mount', '-o', 'ro', device, str(mount))
        try:
            for path, digest in checksums.items():
                assert hashlib.sha256((mount/path).read_bytes()).hexdigest()==digest, path
        finally: command('umount', str(mount))
        command('e2fsck', '-f', '-n', device)
    for name, _, scheme in disks:
        disk='/dev/'+name
        command('parted', '-s', disk, 'mklabel', 'gpt' if scheme=='gpt' else 'msdos')
        command('udevadm', 'settle')
        wait_for(lambda: snapshot(name)['scheme']==scheme)
        s=snapshot(name); assert not s['reason'], s['reason']
        assert s['gaps'] == [dict(start=MIB, size=2046*MIB)]
        log('PASS '+scheme+' initial free-space bounds')
        execute(request(name, 'create', start=MIB, size=768*MIB, format='ext4'))
        p=part(name); device=p['device']; assert command('blkid', '-s', 'TYPE', '-o', 'value', device)=='ext4'
        assert p['start']==MIB and p['size']==768*MIB
        if scheme=='gpt':
            command('useradd', '-M', '-s', '/usr/sbin/nologin', 'linuxbr-test-denied')
            uid=pwd.getpwnam('linuxbr-test-denied').pw_uid
            user_runtime=Path('/run/linuxbr-test-denied'); user_runtime.mkdir(mode=0o700)
            os.chown(user_runtime,uid,uid)
            rules=Path('/etc/polkit-1/rules.d/00-linuxbr-test-denied.rules')
            rules.write_text('polkit.addRule(function(action, subject) { if (subject.user == "linuxbr-test-denied" && action.id.indexOf("org.freedesktop.udisks2.") == 0) return polkit.Result.NO; });\n')
            time.sleep(2)
            denied=execute(request(name,'format',path=p['path'],format='ntfs'),expect_error=True,
                           prefix=('runuser','-u','linuxbr-test-denied','--','env','XDG_RUNTIME_DIR='+str(user_runtime)))
            assert 'NotAuthorized' in denied.stdout or 'Not authorized' in denied.stdout, denied.stdout
            assert command('blkid','-p','-s','TYPE','-o','value',device)=='ext4'
            assert part(name)['size']==768*MIB
            log('PASS real polkit denial; existing filesystem and partition preserved')
        # Ensure last-mount time differs from mkfs/fsck time: regression for
        # resize2fs requiring a recorded writable fsck after any later mount.
        time.sleep(2)
        # Multiple noncompressible files and Unicode paths, checked after BOTH resizes.
        command('mount', device, str(mount))
        checksums={}
        try:
            (mount/'Documentos').mkdir()
            for index in range(8):
                path=f'Documentos/validação-{index}.bin'; data=os.urandom(8*MIB)
                (mount/path).write_bytes(data); checksums[path]=hashlib.sha256(data).hexdigest()
            os.sync()
            denied=execute(request(name, 'delete', path=p['path']), expect_error=True)
            assert 'Desmonte' in denied.stdout
            log('PASS '+scheme+' mounted disk protected')
        finally: command('umount', str(mount))
        wait_for(lambda: not snapshot(name)['reason'])
        execute(request(name, 'resize', path=p['path'], size=256*MIB))
        wait_for(lambda: part(name)['size']==256*MIB)
        verify_files(device, checksums)
        log('PASS '+scheme+' shrink 768 -> 256 MiB; SHA-256 of 8 files (64 MiB) and e2fsck')
        execute(request(name, 'resize', path=p['path'], size=1024*MIB))
        wait_for(lambda: part(name)['size']==1024*MIB)
        verify_files(device, checksums)
        log('PASS '+scheme+' grow 256 -> 1024 MiB; SHA-256 of 8 files (64 MiB) and e2fsck')
        # Too-small filesystem must fail before the containing partition is reduced.
        execute(request(name, 'resize', path=p['path'], size=32*MIB), expect_error=True)
        assert part(name)['size']==1024*MIB
        verify_files(device, checksums)
        log('PASS '+scheme+' refused unsafe shrink; data and partition preserved')
        # A stale confirmation must not act after an external change.
        stale=request(name, 'delete', path=p['path'])
        command('parted', '-s', disk, 'mkpart', 'primary', '1536MiB', '1664MiB')
        command('udevadm', 'settle'); wait_for(lambda: len(snapshot(name)['parts'])==2)
        denied=execute(stale, expect_error=True); assert 'mudaram' in denied.stdout
        log('PASS '+scheme+' stale geometry rejected')
        # Delete the extra partition through the same application worker.
        extra=snapshot(name)['parts'][1]
        execute(request(name, 'delete', path=extra['path']))
        wait_for(lambda: len(snapshot(name)['parts'])==1)
        for fmt in ('ntfs', 'exfat', 'vfat', 'ext4'):
            execute(request(name, 'format', path=p['path'], format=fmt))
            wait_for(lambda: part(name)['fs']==fmt)
            assert command('blkid', '-p', '-s', 'TYPE', '-o', 'value', device)==fmt
            command('mount', device, str(mount))
            try:
                assert not (mount/'Documentos').exists()
                (mount/'teste.txt').write_text('Linux BR — ação e cedilha: ç\n')
                os.sync()
            finally: command('umount', str(mount))
            command('mount', '-o', 'ro', device, str(mount))
            try: assert (mount/'teste.txt').read_text()=='Linux BR — ação e cedilha: ç\n'
            finally: command('umount', str(mount))
            log('PASS '+scheme+' format '+fmt+'; mount/write/remount/read')
        execute(request(name, 'delete', path=p['path']))
        wait_for(lambda: not snapshot(name)['parts'])
        assert snapshot(name)['gaps']==[dict(start=MIB,size=2046*MIB)]
        log('PASS '+scheme+' delete; full allocatable space restored')
        # Check create+format also works for each offered format, not only reformat.
        for fmt in ('ntfs', 'exfat', 'vfat'):
            execute(request(name, 'create', start=MIB, size=256*MIB, format=fmt))
            p=part(name); assert command('blkid','-p','-s','TYPE','-o','value',p['device'])==fmt
            execute(request(name,'delete',path=p['path']))
            wait_for(lambda: not snapshot(name)['parts'])
            log('PASS '+scheme+' create and delete '+fmt)
    log('LINUXBR_PARTITION_VM_PASS')

if __name__=='__main__':
    try: main()
    except Exception:
        traceback.print_exc(); log('LINUXBR_PARTITION_VM_FAIL'); sys.exit(1)
