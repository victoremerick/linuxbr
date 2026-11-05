"""Ephemeral login configuration; never grants an administrative shell."""
from pathlib import Path
import json
import subprocess
import shutil
from boot_policy import mode,server_edition
import basic_video

selected=mode()
if basic_video.selected() and not selected:
    basic_video.prepare(server=server_edition())
    raise SystemExit(0)
if not selected and not server_edition():raise SystemExit(0)
root=Path('/run/linuxbr-safe');root.mkdir(mode=0o755,exist_ok=True)
sessions=root/'sessions';sessions.mkdir(exist_ok=True)
empty=root/'empty-wayland';empty.mkdir(exist_ok=True)
(sessions/'linuxbr-safe.desktop').write_text('[Desktop Entry]\nName=Linux BR — '+('Manutenção' if selected else 'Servidor')+'\nExec=/usr/bin/linuxbr-minimal-session\nType=Application\nDesktopNames=LinuxBRMinimal;\n')
theme_directory=''
if Path('/run/live/medium').exists():
    theme=root/'themes/linuxbr-minimal'
    shutil.copytree('/usr/share/sddm/themes/linuxbr-minimal',theme,dirs_exist_ok=True)
    arguments=Path('/proc/cmdline').read_text().split()
    custom=any(any(word in argument.lower() for word in ('username=', 'password=', 'passwd=')) for argument in arguments)
    hint='Sessão temporária da mídia oficial: usuário user e senha live.' if not custom else 'Sessão temporária: utilize as credenciais configuradas para esta mídia.'
    with (theme/'theme.conf').open('a') as output:
        output.write('\nliveUser='+('' if custom else 'user')+'\nliveHint='+hint+'\n')
    theme_directory='ThemeDir=/run/linuxbr-safe/themes\n'
(root/'sddm.conf').write_text('[General]\nDisplayServer=x11\n[Theme]\n'+theme_directory+'Current=linuxbr-minimal\n[Autologin]\nUser=\nSession=\nRelogin=false\n[X11]\nSessionDir=/run/linuxbr-safe/sessions\n[Wayland]\nSessionDir=/run/linuxbr-safe/empty-wayland\n[Users]\nRememberLastSession=false\n')
if selected and selected!='safe-network':
    interfaces=json.loads(subprocess.check_output(['/usr/sbin/ip','-json','link','show'],text=True))
    for interface in interfaces:
        if interface['ifname']!='lo':subprocess.run(['/usr/sbin/ip','link','set','dev',interface['ifname'],'down'],check=True)
