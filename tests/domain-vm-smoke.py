#!/usr/bin/env python3
"""Two disposable Linux BR guests: isolated Samba AD and client. No host account changes."""
import argparse
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--graphical',action='store_true',help='Expose a private QMP socket and disposable guest control directory for graphical validation')
args=parser.parse_args()
spec=importlib.util.spec_from_file_location('partition_runner',ROOT/'tests/partition-vm-smoke.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
work=Path(tempfile.mkdtemp(prefix='linuxbr-domain-',dir='/tmp'));work.chmod(0o700)
art=Path(tempfile.mkdtemp(prefix='domain-vm.',dir=ROOT/'.cache'))
print('Evidence:',art,flush=True)
if args.graphical:
    (work/'control').mkdir()
    print('Graphical control:',work/'control',flush=True)
iso=ROOT/'dist/linuxbr-0.4.0-amd64.iso'
processes=[]; logs=[]
with iso.open('rb') as stream: iso_hash=hashlib.file_digest(stream,'sha256').hexdigest()
(art/'manifest.json').write_text(json.dumps(dict(iso=str(iso),iso_sha256=iso_hash,backend_sha256=hashlib.sha256((ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system/accounts_backend.py').read_bytes()).hexdigest(),checks_sha256=hashlib.sha256((ROOT/'tests/domain-vm-check.py').read_bytes()).hexdigest(),mode='Two disposable live VMs, injected current backend; '+('interactive SDDM/Plasma graphical validation via private QMP/control directory' if args.graphical else 'SDDM PAM login, no graphical desktop automation')),indent=2))
try:
    subprocess.run(['xorriso','-osirrox','on','-indev',str(iso),'-extract','/live/vmlinuz',str(work/'kernel'),'-extract','/live/initrd.img',str(work/'initrd')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    original=(work/'initrd').read_bytes();order=m.cpio_file(original,'scripts/init-bottom/ORDER')
    payload=work/'payload';payload.mkdir()
    for name in ('admin','user','local'):
        (payload/(name+'.secret')).write_text('Lb9!'+secrets.token_urlsafe(24))
    shutil.copy2(ROOT/'tests/domain-vm-guest.sh',payload/'run.sh')
    shutil.copy2(ROOT/'tests/domain-vm-check.py',payload/'check.py')
    if args.graphical:
        shutil.copy2(ROOT/'tests/domain-vm-graphical.py',payload/'graphical.py')
    shutil.copy2(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system/accounts_backend.py',payload/'accounts_backend.py')
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    for role in ('dc','client'):
        overlay=work/role;overlay.mkdir();shutil.copytree(payload,overlay/'domain-payload')
        def write(name,text):
            p=overlay/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);p.chmod(0o755)
        write('scripts/init-bottom/domain-test', '''#!/bin/sh
case "$1" in prereqs) exit 0;; esac
mkdir -p "$rootmnt/opt/domain-test" "$rootmnt/etc/systemd/system/multi-user.target.wants"
cp -a /domain-payload/. "$rootmnt/opt/domain-test/"
cp /domain-test.service "$rootmnt/etc/systemd/system/domain-test.service"
ln -s ../domain-test.service "$rootmnt/etc/systemd/system/multi-user.target.wants/domain-test.service"
''')
        write('scripts/init-bottom/ORDER',order.decode()+'\n/scripts/init-bottom/domain-test "$@"\n')
        write('domain-test.service',f'''[Unit]
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/bin/bash /opt/domain-test/run.sh {role}
TimeoutStartSec=1800
''')
        names=['.']+[str(p.relative_to(overlay)) for p in sorted(overlay.rglob('*'))]
        archive=subprocess.run(['cpio','--null','-o','-H','newc','--owner=0:0'],cwd=overlay,input=('\0'.join(names)+'\0').encode(),capture_output=True,check=True).stdout
        initrd=work/(role+'.initrd');initrd.write_bytes(original+b'\0'*((-len(original))%4)+archive)
        command=['qemu-system-x86_64','-enable-kvm','-cpu','host','-m','4096','-smp','2','-display','none','-monitor','none','-serial','stdio','-no-reboot','-kernel',str(work/'kernel'),'-initrd',str(initrd),'-append','boot=live components noswap noprompt console=ttyS0 systemd.unit=multi-user.target systemd.mask=sddm.service systemd.mask=serial-getty@ttyS0.service plymouth.enable=0 linuxbr.domain-test=1','-drive',f'file={iso},media=cdrom,format=raw,readonly=on','-netdev','user,id=internet','-device','virtio-net-pci,netdev=internet,addr=0x3','-netdev',f'socket,id=lab,{"listen" if role=="dc" else "connect"}=127.0.0.1:{port}','-device','virtio-net-pci,netdev=lab,addr=0x4']
        if args.graphical and role == 'client':
            command[command.index('-append')+1] = command[command.index('-append')+1].replace('systemd.mask=sddm.service ', '')
            command += ['-qmp', f'unix:{work}/qmp.sock,server=on,wait=off', '-virtfs', f'local,path={work}/control,mount_tag=control,security_model=none,id=control']
        log=(art/(role+'.log')).open('w');logs.append(log)
        processes.append(subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT))
        time.sleep(2)
    processes[1].wait(timeout=3000 if args.graphical else 1800)
    text=(art/'client.log').read_text(errors='replace')
    summary='\n'.join(l for l in text.splitlines() if l.startswith(('PASS ','LINUXBR_DOMAIN_','DEFAULT_AD_POLICY_LOGIN=')))
    (art/'summary.txt').write_text(summary+'\n'); print(summary,flush=True)
    if 'LINUXBR_DOMAIN_PASS' not in text:raise RuntimeError('Validation failed: '+str(art))
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()
    for log in logs:log.close()
    # Remove generated credentials from logs, if upstream tools printed them.
    for log in art.glob('*.log'):
        data=log.read_text(errors='replace')
        for secret in (work/'payload').glob('*.secret'):
            data=data.replace(secret.read_text(),'[REDACTED]')
        log.write_text(data)
    if args.graphical:
        for evidence in (work/'control').glob('*.txt'):
            data=evidence.read_text()
            for secret in (work/'payload').glob('*.secret'):
                data=data.replace(secret.read_text(),'[REDACTED]')
            (art/evidence.name).write_text(data)
        for evidence in (work/'control').glob('*.png'):
            shutil.copy2(evidence,art/evidence.name)
    shutil.rmtree(work)
