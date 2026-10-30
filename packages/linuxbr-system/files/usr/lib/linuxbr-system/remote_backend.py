"""User-session RDP and VNC sharing controls; no remote-client launcher."""
import configparser
import os
from pathlib import Path
import secrets
import subprocess
import sys

RDP_UNIT = 'app-org.kde.krdpserver.service'
VNC_UNIT = 'linuxbr-vnc.service'


def command(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=12).stdout.strip()


def active(unit):
    return subprocess.run(['systemctl','--user','is-active','--quiet',unit],
                          capture_output=True,timeout=4).returncode == 0


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'krfbrc'


def obscure(value):
    """KStringHandler::obscure, used by KRFB for its VNC password field."""
    return ''.join(char if ord(char)<=0x21 else chr(0x1001f-ord(char)) for char in value)


def vnc_settings():
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read(config_path())
    return {'port':cfg.getint('TCP','port',fallback=5900),
            'password':obscure(cfg.get('Security','desktopPassword',fallback='')) if cfg.getboolean('Security','noWallet',fallback=False) else '',
            'active':active(VNC_UNIT)}


def set_vnc(enable,port=5900):
    if not 1024<=int(port)<=65535:raise ValueError('Porta VNC inválida.')
    if not enable:
        command('systemctl','--user','disable','--now',VNC_UNIT)
        return ''
    path=config_path();path.parent.mkdir(parents=True,exist_ok=True)
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read(path)
    if not cfg.has_section('TCP'):cfg.add_section('TCP')
    if not cfg.has_section('Security'):cfg.add_section('Security')
    password=secrets.token_urlsafe(8)[:8]
    cfg.set('TCP','useDefaultPort','false');cfg.set('TCP','port',str(port));cfg.set('TCP','publishService','false')
    cfg.set('Security','noWallet','true');cfg.set('Security','allowUnattendedAccess','false')
    cfg.set('Security','allowDesktopControl','true');cfg.set('Security','desktopPassword',obscure(password))
    # KRFB reads this password at startup. Restrict the file to this user.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:cfg.write(stream)
    finally:os.chmod(path,0o600)
    running=active(VNC_UNIT)
    command('systemctl','--user','enable','--now',VNC_UNIT)
    if running:command('systemctl','--user','restart',VNC_UNIT)
    return password


def rdp_settings():
    try:port=int(command('kreadconfig6','--file','krdpserverrc','--group','General','--key','ListenPort') or '3389')
    except (ValueError,subprocess.SubprocessError,OSError):port=3389
    return {'port':port,'active':active(RDP_UNIT)}


def set_rdp(enable,port=3389):
    if not 1024<=int(port)<=65535:raise ValueError('Porta RDP inválida.')
    if not enable:
        command('systemctl','--user','disable','--now',RDP_UNIT)
        return
    if os.environ.get('XDG_SESSION_TYPE')!='wayland':
        raise ValueError('O servidor RDP integrado requer sessão Plasma Wayland.')
    # The portal authorization and PAM-backed account are the KDE-supported path.
    command('flatpak','permission-set','kde-authorized','remote-desktop','org.kde.krdpserver','yes')
    for key,value in [('ListenPort',str(port)),('SystemUserEnabled','true')]:
        command('kwriteconfig6','--file','krdpserverrc','--group','General','--key',key,value)
    running=active(RDP_UNIT)
    command('systemctl','--user','enable','--now',RDP_UNIT)
    if running:command('systemctl','--user','restart',RDP_UNIT)


if __name__=='__main__':
    try:
        if len(sys.argv)!=4 or sys.argv[1] not in ('rdp','vnc') or sys.argv[2] not in ('enable','disable'):
            raise ValueError('Parâmetros inválidos.')
        port=int(sys.argv[3]);enable=sys.argv[2]=='enable'
        if sys.argv[1]=='rdp':set_rdp(enable,port)
        else:print(set_vnc(enable,port))
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
