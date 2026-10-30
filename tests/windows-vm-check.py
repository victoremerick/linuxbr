import os,pathlib,subprocess,sys,json
root=pathlib.Path.home()/'windows-qa'
# Reuse only display/session variables from this user's Plasma process.
pid=subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','plasmashell'],text=True).splitlines()[0]
allowed={'DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS'}
for entry in pathlib.Path('/proc',pid,'environ').read_bytes().split(b'\0'):
 key,sep,value=entry.partition(b'=')
 if sep and key.decode() in allowed:os.environ[key.decode()]=value.decode()
sys.path.insert(0,'/usr/lib/linuxbr-system')
import windows_runner as runner
identifier=runner.create_environment('Validação Windows Linux BR 0.4.2')
results=[]
for filename,expected in [('smoke64.exe','linuxbr-windows-64-ok.txt'),('smoke32.exe','linuxbr-windows-32-ok.txt')]:
 code=runner.run(identifier,'run',str(root/filename))
 ok=code==0 and (root/expected).exists()
 results.append({'file':filename,'exit':code,'windows_api_file':ok})
 print(json.dumps(results[-1]),flush=True)
code=runner.run(identifier,'run',str(root/'smoke.msi'))
payload=list((runner.environment_path(identifier)/'prefix/drive_c/users').glob('*/AppData/Local/LinuxBRCompatibilityTest/windows-payload.txt'))
results.append({'file':'smoke.msi','exit':code,'payload_installed':bool(payload)})
(root/'results.json').write_text(json.dumps({'environment':identifier,'tests':results},indent=2))
print(json.dumps(results[-1]),flush=True)
assert all(r['exit']==0 and (r.get('windows_api_file') or r.get('payload_installed')) for r in results)
print('PASS: EXE x86, EXE x64 e MSI executados no Wine instalado.',flush=True)
