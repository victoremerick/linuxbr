#!/usr/bin/env python3
"""Supervised settings/decoration validation using a read-only ISO and private guest control."""
import importlib.util,json,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('helper',ROOT/'tests/partition-vm-smoke.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
work=Path(tempfile.mkdtemp(prefix='linuxbr-settings-',dir='/tmp'));work.chmod(0o700)
control=work/'control';control.mkdir()
art=Path(tempfile.mkdtemp(prefix='settings-vm.',dir=ROOT/'.cache'));print('Artifacts:',art,'Control:',control,flush=True)
p=None
try:
 iso=ROOT/'dist/linuxbr-0.4.0-amd64.iso'
 subprocess.run(['xorriso','-osirrox','on','-indev',str(iso),'-extract','/live/vmlinuz',str(work/'kernel'),'-extract','/live/initrd.img',str(work/'initrd')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 original=(work/'initrd').read_bytes();order=helper.cpio_file(original,'scripts/init-bottom/ORDER')
 overlay=work/'overlay';overlay.mkdir();payload=overlay/'settings-payload';payload.mkdir()
 for package in ('linuxbr-desktop','linuxbr-system','linuxbr-drive-manager'):
  shutil.copytree(ROOT/'packages'/package/'files',payload,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 def write(name,data):
  target=overlay/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(data);target.chmod(0o755)
 write('scripts/init-bottom/settings-test','''#!/bin/sh
case "$1" in prereqs) exit 0;; esac
cp -a /settings-payload/. "$rootmnt/"
chroot "$rootmnt" /usr/bin/python3 /usr/lib/linuxbr-desktop/plasma-layout.py
cp /settings-control.service "$rootmnt/etc/systemd/system/settings-control.service"
cp /settings-control.py "$rootmnt/opt/settings-control.py"
mkdir -p "$rootmnt/etc/systemd/system/multi-user.target.wants"
ln -s ../settings-control.service "$rootmnt/etc/systemd/system/multi-user.target.wants/settings-control.service"
''')
 write('scripts/init-bottom/ORDER',order.decode()+'\n/scripts/init-bottom/settings-test "$@"\n')
 write('settings-control.service','''[Unit]
After=systemd-user-sessions.service
[Service]
ExecStart=/usr/bin/python3 /opt/settings-control.py
TimeoutStartSec=1200
''')
 write('settings-control.py','''import subprocess,time
from pathlib import Path
c=Path('/mnt/control');c.mkdir(exist_ok=True)
subprocess.run(['mount','-t','9p','-o','trans=virtio,version=9p2000.L','control',str(c)],check=True)
for i in range(1200):
 command=c/'command.sh'
 if command.exists():
  text=command.read_text();command.unlink()
  try:
   p=subprocess.run(['bash','-c',text],capture_output=True,text=True,timeout=45)
   (c/'output.txt').write_text(p.stdout+p.stderr+'\\nEXIT='+str(p.returncode))
  except Exception as e:(c/'output.txt').write_text(str(e))
 if (c/'done').exists():break
 time.sleep(1)
subprocess.run(['systemctl','poweroff','--force','--force'])
''')
 names=['.']+[str(x.relative_to(overlay)) for x in sorted(overlay.rglob('*'))]
 archive=subprocess.run(['cpio','--null','-o','-H','newc','--owner=0:0'],cwd=overlay,input=('\0'.join(names)+'\0').encode(),capture_output=True,check=True).stdout
 (work/'test.initrd').write_bytes(original+b'\0'*((-len(original))%4)+archive)
 command=['qemu-system-x86_64','-enable-kvm','-cpu','host','-m','4096','-smp','2','-display','none','-monitor','none','-serial','stdio','-no-reboot','-nic','none','-kernel',str(work/'kernel'),'-initrd',str(work/'test.initrd'),'-append','boot=live components noswap noprompt console=ttyS0 plymouth.enable=0','-drive',f'file={iso},format=raw,media=cdrom,readonly=on','-qmp',f'unix:{work}/qmp.sock,server=on,wait=off','-virtfs',f'local,path={control},mount_tag=control,security_model=none,id=control']
 with (art/'serial.log').open('w') as log:
  p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);p.wait(timeout=1300)
finally:
 if p and p.poll() is None:p.terminate();p.wait(timeout=10)
 for item in control.iterdir():
  if item.suffix in ('.png','.txt'):shutil.copy2(item,art/item.name)
 shutil.rmtree(work)
