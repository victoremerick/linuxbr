"""Actual AD enrollment and PAM authentication, inside disposable VM only."""
import json
import subprocess
import sys
import time
from pathlib import Path
assert 'linuxbr.domain-test=1' in Path('/proc/cmdline').read_text()
sys.path.insert(0,'/opt/domain-test')
import accounts_backend as backend

def run(*args, secret=None, success=True):
    p=subprocess.run(args,input=(secret+'\n') if secret else None,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1800 if args[:2] == ('python3','/opt/domain-test/graphical.py') else 90)
    if success and p.returncode: raise RuntimeError('Command failed: '+args[0]+' '+p.stdout)
    return p

def pam(user,password,success=True):
    return run('pamtester','sddm',user,'authenticate','acct_mgmt','open_session','close_session',secret=password,success=success)

admin=Path('/opt/domain-test/admin.secret').read_text().strip()
password=Path('/opt/domain-test/user.secret').read_text().strip()
local=Path('/opt/domain-test/local.secret').read_text().strip()
domain='lab.example.test'
pam('localadmin',local)
assert 'sudo' in run('id','-nG','localadmin').stdout.split()
print('PASS Local administrative login before enrollment',flush=True)
assert backend.execute(dict(action='discover',domain=domain))
print('PASS Discover test Active Directory',flush=True)
backend.execute(dict(action='join',domain=domain,username='Administrator',password=admin))
assert any(r['configured'] and r['name']==domain for r in backend.execute(dict(action='realms')))
print('PASS Join using production backend and SSSD',flush=True)
for _ in range(30):
    if run('getent','passwd','employee@'+domain,success=False).returncode==0: break
    time.sleep(2)
else: raise RuntimeError('Domain user resolution failed')
print('PASS NSS domain user resolution',flush=True)
assert 'sudo' not in run('id','-nG','employee@'+domain).stdout.split()
print('PASS Domain user has no local administrator group',flush=True)
default=pam('employee@'+domain,password,success=False)
print('DEFAULT_AD_POLICY_LOGIN=' + ('accepted' if default.returncode == 0 else 'denied'),flush=True)
if default.returncode:
    print(default.stdout,flush=True)
    diagnostics=run('journalctl','-b','-u','sssd','--no-pager','-n','30',success=False)
    print(diagnostics.stdout,flush=True)
# Explicitly authorize only the disposable employee in this laboratory.
# No production configuration is changed to bypass domain access policy.
run('realm','permit','employee@'+domain)
pam('employee@'+domain,password)
home=run('getent','passwd','employee@'+domain).stdout.strip().split(':')[5]
assert Path(home).is_dir()
print('PASS SDDM PAM login with explicit user permission and home creation',flush=True)
assert pam('employee@'+domain,'invalid-password',success=False).returncode != 0
print('PASS Incorrect domain password rejected',flush=True)
pam('localadmin',local)
assert 'sudo' in run('id','-nG','localadmin').stdout.split()
print('PASS Local administrative login retained while joined',flush=True)
if Path('/opt/domain-test/graphical.py').exists():
    print(run('python3','/opt/domain-test/graphical.py').stdout, flush=True)
backend.execute(dict(action='leave',domain=domain,username='Administrator',password=admin))
assert not any(r['configured'] and r['name']==domain for r in backend.execute(dict(action='realms')))
print('PASS Leave using production backend',flush=True)
assert pam('employee@'+domain,password,success=False).returncode != 0
print('PASS Corporate login rejected after leaving',flush=True)
pam('localadmin',local)
assert 'sudo' in run('id','-nG','localadmin').stdout.split()
print('PASS Local administrative login retained after leaving',flush=True)
print('LINUXBR_DOMAIN_PASS',flush=True)
