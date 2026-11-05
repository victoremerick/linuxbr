"""Temporary software-rendered X11 login for the basic video boot entry."""
from pathlib import Path


def selected(commandline=None):
    text=Path('/proc/cmdline').read_text() if commandline is None else commandline
    return 'linuxbr.video=basic' in text.split()


def login_override(output):
    override=output/'sddm.service.d';override.mkdir(parents=True,exist_ok=True)
    (override/'90-linuxbr-basic-video.conf').write_text(
        '[Unit]\nRequires=linuxbr-safe-prepare.service\nAfter=linuxbr-safe-prepare.service\n'
        '[Service]\nBindReadOnlyPaths=/run/linuxbr-basic/sddm.conf:/etc/sddm.conf\n'
        'Environment=QT_QUICK_BACKEND=software LIBGL_ALWAYS_SOFTWARE=1\n')


def prepare(root=Path('/run/linuxbr-basic'),framebuffer=Path('/dev/fb0'),server=False,drm=Path('/dev/dri')):
    root.mkdir(mode=0o755,parents=True,exist_ok=True)
    sessions=root/'sessions';sessions.mkdir(exist_ok=True)
    empty=root/'empty-wayland';empty.mkdir(exist_ok=True)
    driver='modesetting' if drm.exists() or not framebuffer.exists() else 'fbdev'
    options=' Option "fbdev" "/dev/fb0"\n' if driver=='fbdev' else ' Option "AccelMethod" "none"\n'
    (root/'xorg.conf').write_text(
        'Section "ServerFlags"\n Option "AutoAddGPU" "false"\nEndSection\n'
        'Section "Device"\n Identifier "LinuxBRBasic"\n Driver "'+driver+'"\n'+options+'EndSection\n')
    executable='/usr/bin/linuxbr-minimal-session' if server else '/usr/bin/startplasma-x11'
    (sessions/'linuxbr-basic.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=Linux BR — Vídeo básico\n'
        'Exec=/usr/bin/env LIBGL_ALWAYS_SOFTWARE=1 QT_QUICK_BACKEND=software KWIN_COMPOSE=N '+executable+'\n'
        'DesktopNames='+('LinuxBRMinimal' if server else 'KDE')+';\n')
    (root/'sddm.conf').write_text(
        '[General]\nDisplayServer=x11\n[Theme]\nCurrent='+('linuxbr-minimal' if server else 'linuxbr')+'\n'
        '[Autologin]\nUser=\nSession=\nRelogin=false\n[X11]\n'
        'ServerArguments=-nolisten tcp -config '+str(root/'xorg.conf')+'\nSessionDir='+str(sessions)+'\n'
        '[Wayland]\nSessionDir='+str(empty)+'\n[Users]\nRememberLastSession=false\n')
    return driver
