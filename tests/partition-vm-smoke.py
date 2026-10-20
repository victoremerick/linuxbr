#!/usr/bin/env python3
"""Boot Linux BR live read-only; destructive tests use two NEW /tmp images only."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def cpio_file(data, wanted):
    offset=0
    while offset<len(data):
        while offset<len(data) and data[offset]==0: offset+=1
        if data[offset:offset+4]==b'\x28\xb5\x2f\xfd':
            data=subprocess.run(['zstd','-dc'],input=data[offset:],capture_output=True,check=True).stdout; offset=0
        elif data[offset:offset+2]==b'\x1f\x8b':
            data=gzip.decompress(data[offset:]); offset=0
        if offset>=len(data): break
        if data[offset:offset+6]!=b'070701': raise ValueError('Formato de initramfs não suportado pelo teste')
        header=data[offset:offset+110]; size=int(header[54:62],16); length=int(header[94:102],16)
        name=data[offset+110:offset+110+length-1].decode()
        start=(offset+110+length+3)//4*4
        if name==wanted: return data[start:start+size]
        offset=(start+size+3)//4*4
    raise ValueError('Arquivo ausente no initramfs: '+wanted)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso',type=Path,default=ROOT/'dist/linuxbr-0.4.0-amd64.iso')
    parser.add_argument('--keep-vm',action='store_true',help='Manter os discos descartáveis em /tmp para diagnóstico')
    args=parser.parse_args()
    iso=args.iso.resolve()
    if not iso.is_file(): parser.error('ISO não encontrada')
    for tool in ('xorriso','cpio','zstd','qemu-system-x86_64'):
        if not shutil.which(tool): parser.error('Dependência ausente: '+tool)
    if not os.access('/dev/kvm',os.R_OK|os.W_OK): parser.error('KVM indisponível para este usuário')
    artifacts=Path(tempfile.mkdtemp(prefix='partition-vm.',dir=ROOT/'.cache'))
    work=Path(tempfile.mkdtemp(prefix='linuxbr-partition-vm.',dir='/tmp'))
    print('Artefatos:',artifacts,flush=True); print('Discos descartáveis:',work,flush=True)
    try:
        with (artifacts/'extract.log').open('w') as output:
            subprocess.run(['xorriso','-osirrox','on','-indev',str(iso),'-extract','/live/vmlinuz',str(work/'vmlinuz'),
                            '-extract','/live/initrd.img',str(work/'original.initrd')],stdout=output,stderr=subprocess.STDOUT,check=True)
        original=(work/'original.initrd').read_bytes()
        order=cpio_file(original,'scripts/init-bottom/ORDER')
        overlay=work/'overlay'; overlay.mkdir()
        def write(name, text, executable=False):
            p=overlay/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
            if executable:p.chmod(0o755)
        code=ROOT/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'
        dest=overlay/'linuxbr-test-payload/code';dest.mkdir(parents=True)
        hashes={}
        for p in code.glob('*.py'):
            shutil.copy2(p,dest/p.name); hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        shutil.copy2(ROOT/'tests/partition-vm-guest.py',overlay/'linuxbr-test-payload/guest.py')
        write('linuxbr-test-payload/run.sh', '''#!/bin/bash
exec >/dev/ttyS0 2>&1
export PYTHONUNBUFFERED=1
python3 /opt/linuxbr-partition-test/guest.py
result=$?
echo "LINUXBR_GUEST_EXIT=$result"
sync
systemctl poweroff --force --force
''',True)
        write('scripts/init-bottom/linuxbr-partition-test', '''#!/bin/sh
case "$1" in prereqs) exit 0;; esac
set -eu
echo LINUXBR_TEST_PAYLOAD_INSTALL >/dev/console
mkdir -p "$rootmnt/opt/linuxbr-partition-test" "$rootmnt/etc/systemd/system/multi-user.target.wants"
cp -a /linuxbr-test-payload/. "$rootmnt/opt/linuxbr-partition-test/"
cp /linuxbr-test.service "$rootmnt/etc/systemd/system/linuxbr-partition-test.service"
ln -s ../linuxbr-partition-test.service "$rootmnt/etc/systemd/system/multi-user.target.wants/linuxbr-partition-test.service"
''',True)
        write('scripts/init-bottom/ORDER', order.decode()+'\n/scripts/init-bottom/linuxbr-partition-test "$@"\n')
        write('linuxbr-test.service', '''[Unit]
Description=Linux BR disposable partition integration test
After=udisks2.service
Requires=udisks2.service
[Service]
Type=oneshot
ExecStart=/bin/bash /opt/linuxbr-partition-test/run.sh
TimeoutStartSec=900
''')
        names=['.']+[str(p.relative_to(overlay)) for p in sorted(overlay.rglob('*'))]
        archive=subprocess.run(['cpio','--null','-o','-H','newc','--owner=0:0'],cwd=overlay,
                               input=('\0'.join(names)+'\0').encode(),capture_output=True,check=True).stdout
        (work/'test.initrd').write_bytes(original+b'\0'*((-len(original))%4)+archive)
        for name in ('gpt.raw','mbr.raw'):
            with (work/name).open('xb') as f:f.truncate(2*1024**3)
        command=['qemu-system-x86_64','-enable-kvm','-cpu','host','-m','3072','-smp','2',
                 '-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot',
                 '-kernel',str(work/'vmlinuz'),'-initrd',str(work/'test.initrd'),
                 '-append','boot=live components noswap noprompt console=ttyS0 systemd.unit=multi-user.target systemd.mask=sddm.service systemd.mask=serial-getty@ttyS0.service plymouth.enable=0 linuxbr.partition-test=1',
                 '-drive',f'file={iso},format=raw,media=cdrom,readonly=on',
                 '-drive',f'file={work}/gpt.raw,format=raw,if=none,id=testgpt',
                 '-device','virtio-blk-pci,drive=testgpt,serial=LINUXBR-TEST-GPT',
                 '-drive',f'file={work}/mbr.raw,format=raw,if=none,id=testmbr',
                 '-device','virtio-blk-pci,drive=testmbr,serial=LINUXBR-TEST-MBR']
        with iso.open('rb') as stream: iso_hash=hashlib.file_digest(stream, 'sha256').hexdigest()
        (artifacts/'manifest.json').write_text(json.dumps(dict(iso=str(iso),iso_sha256=iso_hash,source_sha256=hashes,guest_test_sha256=hashlib.sha256((ROOT/'tests/partition-vm-guest.py').read_bytes()).hexdigest(),qemu=command),indent=2))
        with (artifacts/'serial.log').open('w') as output:
            result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,timeout=900)
        log=(artifacts/'serial.log').read_text(errors='replace')
        lines=[line for line in log.splitlines() if line.startswith(('PASS ','LINUXBR_PARTITION_VM_','LINUXBR_GUEST_EXIT='))]
        (artifacts/'summary.txt').write_text('\n'.join(lines)+'\n')
        print('\n'.join(lines),flush=True)
        if result.returncode or 'LINUXBR_PARTITION_VM_PASS' not in log or 'LINUXBR_PARTITION_VM_FAIL' in log:
            raise RuntimeError('Validação não passou. Consulte '+str(artifacts/'serial.log'))
    finally:
        if args.keep_vm: print('VM preservada:',work,flush=True)
        else: shutil.rmtree(work)

if __name__=='__main__': main()
