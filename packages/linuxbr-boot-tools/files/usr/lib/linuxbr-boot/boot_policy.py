"""Boot mode policy shared by system and user generators."""
from pathlib import Path
import os
import sys

MODES={'safe','safe-network','safe-terminal','recovery'}
SYSTEM_ALLOWED={
 'dbus.service','dbus-broker.service','dbus.socket','polkit.service','systemd-logind.service','live-config.service',
 'sddm.service','display-manager.service','accounts-daemon.service','firewalld.service',
 'apparmor.service','auditd.service','keyboard-setup.service','console-setup.service',
 'kmod-static-nodes.service','ldconfig.service','linuxbr-safe-prepare.service','linuxbr-boot-consume.service','linuxbr-boot-broker.service',
 'systemd-journald.service','systemd-journal-flush.service','systemd-journal-catalog-update.service',
 'systemd-journald.socket','systemd-journald-dev-log.socket','systemd-journald-audit.socket',
 'systemd-udevd.service','systemd-udev-trigger.service','systemd-udev-load-credentials.service',
 'systemd-udevd-control.socket','systemd-udevd-kernel.socket','systemd-modules-load.service',
 'systemd-sysctl.service','systemd-sysusers.service','systemd-random-seed.service',
 'systemd-tmpfiles-setup.service','systemd-tmpfiles-setup-dev.service','systemd-tmpfiles-setup-dev-early.service',
 'systemd-remount-fs.service','systemd-fsck-root.service','systemd-machine-id-commit.service',
 'systemd-binfmt.service','systemd-hwdb-update.service','systemd-update-done.service',
 'systemd-pcrmachine.service','systemd-pcrphase-sysinit.service','systemd-pcrphase.service',
 'systemd-tpm2-setup-early.service','systemd-tpm2-setup.service','systemd-hibernate-clear.service',
 'systemd-user-sessions.service','systemd-vconsole-setup.service','systemd-hostnamed.service',
 'systemd-timedated.service','systemd-localed.service','systemd-rfkill.service','systemd-rfkill.socket',
 'systemd-ask-password-console.service','systemd-ask-password-console.path',
 'systemd-ask-password-plymouth.service','systemd-ask-password-plymouth.path',
 'plymouth-start.service','plymouth-read-write.service','plymouth-quit.service','plymouth-quit-wait.service',
 'systemd-poweroff.service','systemd-reboot.service','systemd-halt.service','systemd-exit.service'}
TEMPLATES={'user@','user-runtime-dir@','getty@','serial-getty@','systemd-fsck@','systemd-cryptsetup@','systemd-integritysetup@','systemd-veritysetup@','modprobe@','systemd-journald@','systemd-journald-varlink@'}
NETWORK={'NetworkManager.service','NetworkManager-dispatcher.service','wpa_supplicant.service','systemd-resolved.service'}
USER_ALLOWED={'dbus.service','dbus-broker.service','dbus.socket','dconf.service','gvfs-daemon.service','systemd-exit.service','systemd-tmpfiles-setup.service'}


def mode(commandline=None):
    text=Path('/proc/cmdline').read_text() if commandline is None else commandline
    choices=[value.split('=',1)[1] for value in text.split() if value.startswith('linuxbr.mode=')]
    return choices[-1] if choices and choices[-1] in MODES else None


def server_edition(commandline=None,configuration=Path('/etc/linuxbr/edition')):
    text=Path('/proc/cmdline').read_text() if commandline is None else commandline
    choices=[value.split('=',1)[1] for value in text.split() if value.startswith('linuxbr.edition=')]
    if choices:return choices[-1]=='server'
    try:return configuration.read_text().strip()=='server'
    except FileNotFoundError:return False


def minimal_login(output):
    override=output/'sddm.service.d';override.mkdir(parents=True,exist_ok=True)
    (override/'90-linuxbr-safe.conf').write_text('[Unit]\nRequires=linuxbr-safe-prepare.service\nAfter=linuxbr-safe-prepare.service\n[Service]\nBindReadOnlyPaths=/run/linuxbr-safe/sddm.conf:/etc/sddm.conf\n')


def allowed(name,selected,user=False):
    if user:return name in USER_ALLOWED
    if name in SYSTEM_ALLOWED:return selected!='safe-terminal' or name not in {'sddm.service','display-manager.service'}
    if any(name.startswith(prefix) for prefix in TEMPLATES):return True
    if selected=='safe-network' and (name in NETWORK or name.startswith('wpa_supplicant@')):return True
    return False


def generate(normal,early,late,user=False,commandline=None,search_paths=None):
    selected=mode(commandline)
    if not selected:
        if not user:
            import basic_video
            if basic_video.selected(commandline):basic_video.login_override(Path(early))
            elif server_edition(commandline):minimal_login(Path(early))
        return []
    output=Path(early);output.mkdir(parents=True,exist_ok=True)
    if search_paths is None:
        suffix='user' if user else 'system'
        search_paths=[Path(p)/'systemd'/suffix for p in ['/usr/lib','/usr/local/lib','/lib','/etc','/run']]
        if user:
            roots=[os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')),os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')),os.environ.get('XDG_RUNTIME_DIR','/nonexistent')]
            roots+=os.environ.get('XDG_CONFIG_DIRS','/etc/xdg').split(':')+os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':')
            search_paths+=[Path(root)/'systemd/user' for root in roots if root.startswith('/')]
    names=set()
    for directory in search_paths:
        if directory.is_dir():
            for path in directory.iterdir():
                if path.name.endswith(('.service','.socket','.timer','.path')):names.add(path.name)
    blocked=[]
    for name in sorted(names):
        if not allowed(name,selected,user):
            target=output/name
            if not target.exists() and not target.is_symlink():target.symlink_to('/dev/null')
            blocked.append(name)
    if user:
        # Prevent graphical applications generated from XDG autostart entries.
        target=output/'xdg-desktop-autostart.target'
        if not target.is_symlink():target.symlink_to('/dev/null')
    else:
        wants=output/'linuxbr-safe.target.wants';wants.mkdir(exist_ok=True)
        for name in ['systemd-logind.service','systemd-user-sessions.service','dbus.service','polkit.service','firewalld.service','linuxbr-safe-prepare.service','linuxbr-boot-consume.service',*(['live-config.service'] if 'boot=live' in (Path('/proc/cmdline').read_text() if commandline is None else commandline).split() else []),*(['NetworkManager.service'] if selected=='safe-network' else []),*(['getty@tty1.service'] if selected=='safe-terminal' else ['sddm.service'])]:
            target=wants/name
            if not target.is_symlink():target.symlink_to('/usr/lib/systemd/system/'+('getty@.service' if name=='getty@tty1.service' else name))
        if selected=='safe-terminal':
            target=wants/'plymouth-quit.service'
            if not target.is_symlink():target.symlink_to('/usr/lib/systemd/system/plymouth-quit.service')
        else:
            minimal_login(output)
    return blocked


if __name__=='__main__':
    generate(*sys.argv[1:4],user=os.environ.get('LINUXBR_USER_GENERATOR')=='1')
