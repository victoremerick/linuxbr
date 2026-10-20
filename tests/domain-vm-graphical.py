"""Disposable graphical validation control. Never installed in the distribution."""
import os
from pathlib import Path
import subprocess
import time
assert 'linuxbr.domain-test=1' in Path('/proc/cmdline').read_text()
control=Path('/mnt/control')
# Turn off live autologin only in this disposable rootfs, requiring real SDDM auth.
for p in [Path('/etc/sddm.conf'), *Path('/etc/sddm.conf.d').glob('*.conf')]:
    if p.exists():
        text=p.read_text()
        if '[Autologin]' in text:
            p.write_text(text.replace('[Autologin]','[DisabledAutologinForTest]'))
Path('/etc/sddm.conf.d/zz-domain-test.conf').write_text('[Autologin]\nUser=\nSession=\nRelogin=false\n')
subprocess.run(['systemctl','unmask','--runtime','sddm.service'],check=True)
subprocess.run(['systemctl','start','sddm.service'],check=True)
(control/'ready.txt').write_text('SDDM started; awaiting test UI actions\n')
# Private host/guest test channel, restricted to a newly created /tmp directory.
for _ in range(1800):
    command=control/'command.sh'
    if command.exists():
        text=command.read_text();command.unlink()
        p=subprocess.run(['bash','-c',text],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
        (control/'output.txt').write_text(p.stdout+'\nEXIT='+str(p.returncode)+'\n')
    if (control/'done').exists():
        break
    time.sleep(1)
else:
    raise RuntimeError('Graphical validation timed out')
for filename, username in [('domain-session.txt','employee@lab.example.test'),('local-session.txt','localadmin')]:
    evidence=(control/filename).read_text()
    assert all(value in evidence for value in ['Name='+username,'Service=sddm','Desktop=KDE','State=active','plasmashell','kwin_wayland'])
assert (control/'local-session.txt').read_text().splitlines()[-1] == '0', 'Local sudo must succeed'
assert (control/'domain-desktop.png').exists() and (control/'local-desktop.png').exists()
print('PASS Graphical domain and local sessions evidence collected',flush=True)
