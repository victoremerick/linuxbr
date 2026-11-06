#!/usr/bin/env python3
"""Build local .debs from project assets and explicit Debian input packages."""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageOps
from release_info import release_info
from credential_policy import reject_seeded_credentials

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text().strip()
RELEASE = release_info(ROOT)
DISPLAY_VERSION = RELEASE['display_version']

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def write(root, path, text, executable=False):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    target.chmod(0o755 if executable else 0o644)

def control(root, name, depends='', extra='', architecture='all'):
    write(root, 'DEBIAN/control', f'''Package: {name}
Version: {VERSION}
Architecture: {architecture}
Maintainer: Linux BR
Section: misc
Priority: optional
{f'Depends: {depends}' if depends else ''}
{extra}Description: Linux BR distribution settings
 Distribution-specific configuration for Linux BR {DISPLAY_VERSION}.
'''.replace('\n\n', '\n'))

def load(path):
    return yaml.safe_load(path.read_text())

def dump(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def optional_metadata(text):
    optional={'print-manager','bluedevil','krdc','krfb','krdp','python3-libvirt','libvirt-daemon-system','libvirt-clients','qemu-system-x86','qemu-system-modules-spice','qemu-utils','virtinst','virt-viewer','virt-manager','ovmf','swtpm','swtpm-tools','kdenetwork-filesharing','samba'}
    lines=[];recommended=[]
    for line in text.splitlines():
        if line.startswith('Recommends: '):
            recommended.extend(line.removeprefix('Recommends: ').split(', '));continue
        if line.startswith('Depends: '):
            dependencies=line.removeprefix('Depends: ').split(', ')
            moved=[dep for dep in dependencies if dep.split(' ',1)[0] in optional]
            recommended.extend(moved)
            line='Depends: '+', '.join(dep for dep in dependencies if dep not in moved)
        lines.append(line)
    if recommended:
        index=next(i for i,line in enumerate(lines) if line.startswith('Description:'))
        lines.insert(index,'Recommends: '+', '.join(dict.fromkeys(recommended)))
    return '\n'.join(lines)+'\n'


def build(output, work, calamares_deb, breeze_deb):
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    names = ['linuxbr-release', 'linuxbr-branding', 'linuxbr-desktop', 'linuxbr-desktop-edition', 'linuxbr-server',
             'linuxbr-calamares-settings', 'linuxbr-sddm-theme', 'linuxbr-boot-theme', 'linuxbr-boot-tools', 'linuxbr-drive-manager', 'linuxbr-system', 'linuxbr-device-manager', 'linuxbr-file-properties']
    roots = {name: work / name for name in names}
    for name, root in roots.items():
        root.mkdir()  # Never silently reuse an old package tree.
        source = ROOT / 'packages' / name / 'files'
        if source.exists():
            shutil.copytree(source, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        reject_seeded_credentials(root)
    # Executable launchers must retain their mode even when edited on Windows.
    for command in ('linuxbr-welcome','linuxbr-task-manager','linuxbr-windows','linuxbr-webapps','linuxbr-webapps-host','linuxbr-store','linuxbr-run','linuxbr-quick-access','linuxbr-file-tools','linuxbr-action','linuxbr-session-actions','linuxbr-recovery','linuxbr-setup','linuxbr-migration','linuxbr-maintenance','linuxbr-desktop-flows','linuxbr-credentials'):
        (roots['linuxbr-system'] / 'usr/bin' / command).chmod(0o755)
    extensions = roots['linuxbr-system'] / 'usr/share/chromium/extensions'
    timers = roots['linuxbr-system'] / 'usr/lib/systemd/user/timers.target.wants'
    timers.mkdir(parents=True,exist_ok=True)
    (timers/'linuxbr-webapp-catalog.timer').symlink_to('../linuxbr-webapp-catalog.timer')
    (roots['linuxbr-system'] / 'usr/bin/linuxbr-virtual-machines').chmod(0o755)
    extensions.mkdir(parents=True, exist_ok=True)
    (extensions / 'linuxbr-webapps').symlink_to('/usr/share/linuxbr/webapps', target_is_directory=True)
    release = roots['linuxbr-release']
    # Store payload outside the diverted paths; dpkg owns only our source files.
    for path in ['etc/issue', 'etc/linuxbr-release']:
        if path == 'etc/issue':
            dest = release / 'usr/share/linuxbr/release/issue'
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(release / path, dest)
    write(release, 'usr/share/linuxbr/release-info.json', json.dumps(RELEASE,ensure_ascii=False,indent=2)+'\n')
    write(release, 'usr/share/linuxbr/release/issue', f'Linux BR {DISPLAY_VERSION} (base Debian 13) ' + r'\n \l' + '\n')
    write(release, 'etc/linuxbr-release', f'NAME="Linux BR"\nVERSION="{DISPLAY_VERSION}"\nVERSION_ID="{VERSION}"\nBASE="Debian 13 (trixie)"\n')
    write(release, 'usr/share/linuxbr/release/os-release', f'''NAME="Linux BR"
PRETTY_NAME="Linux BR {DISPLAY_VERSION}"
ID=linuxbr
ID_LIKE=debian
VERSION_ID="{VERSION}"
VERSION="{DISPLAY_VERSION} (base Debian 13)"
VERSION_CODENAME=trixie
DEBIAN_CODENAME=trixie
LOGO=linuxbr
''')
    shutil.copyfile(release / 'usr/share/linuxbr/release/issue', release / 'usr/share/linuxbr/release/issue.net')
    release_components = ['linuxbr-branding', 'linuxbr-desktop', 'linuxbr-sddm-theme',
                          'linuxbr-boot-theme', 'linuxbr-drive-manager', 'linuxbr-system',
                          'linuxbr-device-manager', 'linuxbr-file-properties']
    control(roots['linuxbr-desktop-edition'],'linuxbr-desktop-edition',', '.join(
        f'{name} (= {VERSION})' for name in release_components))
    control(release, 'linuxbr-release', f'base-files, linuxbr-branding (= {VERSION}), linuxbr-boot-theme (= {VERSION}), linuxbr-desktop-edition (= {VERSION}) | linuxbr-server (= {VERSION})')
    server=roots['linuxbr-server']
    shared=('administration.py','administration_backend.py','services_backend.py','services_dialogs.py',
            'store_sources.py','features_backend.py','features_page.py','network_details.py','network_details_page.py',
            'firewall.py','firewall_backend.py','virtualization.py','virtualization_backend.py','virtualization_preferences.py',
            'virtualization_state.py','virtualization_transfer.py','vm_firmware.py',
            'migration.py','migration_backend.py','visual_style.py','keyboard_controls.py')
    for filename in shared:
        destination=server/'usr/lib/linuxbr-server'/filename;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(roots['linuxbr-system']/'usr/lib/linuxbr-system'/filename,destination)
    control(server,'linuxbr-server',f'linuxbr-branding (= {VERSION}), linuxbr-boot-theme (= {VERSION}), linuxbr-boot-tools (= {VERSION}), python3-pyqt6, python3-dbus, python3-gi, python3-libvirt, python3-cryptography, accountsservice, adduser, passwd, sudo, systemd-timesyncd | time-daemon, network-manager, network-manager-gnome, iproute2, firewalld, partitionmanager, synaptic, rsync, timeshift, breeze-icon-theme, xdg-utils, libvirt-clients, virt-viewer, qemu-utils, python3-virt-firmware, gpg')
    write(server,'DEBIAN/triggers','interest-noawait /usr/share/OVMF\n')
    write(server,'DEBIAN/postinst','''#!/bin/sh
set -eu
if [ "$1" = configure ] || [ "$1" = triggered ]; then
    if [ -f /usr/share/OVMF/OVMF_VARS_4M.ms.fd ]; then
        /usr/bin/python3 /usr/lib/linuxbr-server/vm_firmware.py --prepare
    fi
fi
''',True)
    paths = '/usr/lib/os-release /etc/os-release /etc/issue /etc/issue.net'
    write(release, 'DEBIAN/postinst', f'''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    for path in {paths}; do
        owner=$(dpkg-divert --listpackage "$path")
        # live-build protects its generated metadata during bootstrap. Take
        # over only that exact temporary diversion, inside a live-build chroot.
        if [ "$path" = /etc/os-release ] && [ "$owner" = LOCAL ] &&
           [ -e /.live-build ] &&
           [ "$(dpkg-divert --truename "$path")" = /etc/os-release.debootstrap ]; then
            if [ -e "$path.debian" ] || [ -L "$path.debian" ]; then
                echo "Backup preexistente: $path.debian" >&2
                exit 1
            fi
            dpkg-divert --local --remove --no-rename \
                --divert /etc/os-release.debootstrap "$path"
            owner=
        fi
        if [ -z "$owner" ]; then
            # Preserve essential files without an interval where they are absent.
            [ ! -e "$path.debian" ] && [ ! -L "$path.debian" ]
            cp -a "$path" "$path.debian"
            dpkg-divert --package linuxbr-release --add --no-rename --divert "$path.debian" "$path"
        elif [ "$owner" != linuxbr-release ]; then
            echo "Diversion conflitante: $path ($owner)" >&2
            exit 1
        fi
        case "$path" in
            */os-release) source=os-release ;;
            *) source=${{path##*/}} ;;
        esac
        cp --remove-destination "/usr/share/linuxbr/release/$source" "$path"
    done
fi
''', True)
    write(release, 'DEBIAN/postrm', f'''#!/bin/sh
set -eu
case "$1" in
remove|purge)
    for path in {paths}; do
        if [ "$(dpkg-divert --listpackage "$path")" = linuxbr-release ]; then
            rm -f "$path"
            dpkg-divert --package linuxbr-release --remove --rename --divert "$path.debian" "$path"
        fi
    done
    ;;
esac
''', True)
    control(roots['linuxbr-system'], 'linuxbr-system', 'chromium, chromium-sandbox, python3, python3-cryptography, libnotify-bin, python3-pyqt6, python3-gi, libglib2.0-bin, linuxbr-drive-manager, linuxbr-device-manager, systemsettings, kinfocenter, partitionmanager, plasma-discover, print-manager, plasma-nm, bluedevil, konsole, accountsservice, python3-dbus, realmd, adcli, sssd-ad, sssd-tools, libnss-sss, libpam-sss, libpam-modules, libpam-runtime, samba-common-bin, packagekit, polkit-kde-agent-1, krdc, krfb, krdp, flatpak, powerdevil, kde-config-screenlocker, kscreen, libkscreen-bin, plasma-pa, kdeconnect, network-manager-openvpn, network-manager-vpnc, network-manager-openconnect, plasma-discover-backend-flatpak, dpkg, libkf6config-bin, firewalld, iproute2, network-manager, pulseaudio-utils, passwd, kcalc, kate, kolourpaint, kup-backup, bup, rsync, timeshift, icoutils, gnome-keyring, libpam-gnome-keyring, gir1.2-secret-1, seahorse')
    system_control = roots['linuxbr-system'] / 'DEBIAN/control'
    system_control.write_text(system_control.read_text().replace('Depends: ',f'Depends: linuxbr-boot-tools (= {VERSION}), ',1))
    boot=roots['linuxbr-boot-tools']
    firmware=boot/'usr/share/linuxbr/firmware';firmware.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(roots['linuxbr-system']/'usr/share/linuxbr/firmware',firmware)
    for filename in ('host_backend.py','host_page.py'):
        destination=boot/'usr/lib/linuxbr-server'/filename;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(roots['linuxbr-server']/'usr/lib/linuxbr-server'/filename,destination)
    shutil.copy2(roots['linuxbr-system']/'usr/lib/linuxbr-system/desktop_jobs.py',boot/'usr/lib/linuxbr-server/desktop_jobs.py')
    shutil.copy2(roots['linuxbr-system']/'usr/lib/linuxbr-system/desktop_theme.py',boot/'usr/lib/linuxbr-server/desktop_theme.py')
    # Share the terminal adapter with maintenance without requiring Plasma.
    for relative in ('usr/share/linuxbr/bashrc','usr/share/linuxbr/terminal.bash',
                     'usr/lib/linuxbr-drive-manager/terminal.py','usr/lib/linuxbr-drive-manager/windows_commands.py'):
        origin=roots['linuxbr-drive-manager']/relative
        destination=boot/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(origin,destination)
    # Preserve update protection when the full desktop package is removed.
    for relative in ('usr/lib/linuxbr-system/snapshot_service.py','etc/apt/apt.conf.d/80linuxbr-recovery','etc/linuxbr/recovery-policy.json'):
        origin=roots['linuxbr-system']/relative;destination=boot/relative
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.move(origin,destination)
    boot_native=work/'boot-native'
    shutil.copytree(ROOT/'packages/linuxbr-boot-tools/native',boot_native)
    run('cmake','-S',str(boot_native),'-B',str(boot_native/'build'),'-DCMAKE_BUILD_TYPE=Release')
    run('cmake','--build',str(boot_native/'build'),'--parallel','2')
    plugin=boot_native/'build/liblinuxbrbootplugin.so'
    qml=boot/('usr/lib/'+run('dpkg-architecture','-qDEB_HOST_MULTIARCH')+'/qt6/qml/org/linuxbr/boot')
    qml.mkdir(parents=True,exist_ok=True)
    shutil.copy2(plugin,qml/plugin.name);shutil.copy2(boot_native/'qmldir',qml/'qmldir')
    write(boot_native,'debian/control','Source: linuxbr-boot-tools\nSection: utils\nPriority: optional\nMaintainer: Linux BR\n\nPackage: linuxbr-boot-tools\nArchitecture: any\nDescription: Linux BR maintenance integration\n')
    boot_libs=subprocess.check_output(['dpkg-shlibdeps','-O','-e'+str(plugin)],cwd=boot_native,text=True).strip().split('=',1)[1]
    control(boot,'linuxbr-boot-tools','bash, adduser, passwd, sudo, libpam-systemd, dbus-user-session, systemd-timesyncd | time-daemon, timeshift, rsync, python3, python3-dbus, python3-gi, python3-pyqt6, qt6-translations-l10n, grub-common, grub2-common, qml6-module-qtquick, qml6-module-qtquick-controls, qml6-module-qtquick-virtualkeyboard, qml6-module-qtquick-layouts, qml6-module-qtquick-window, qml6-module-qtqml-workerscript, qt6-svg-plugins, init-system-helpers, systemd, polkitd, pkexec, xterm, openbox, x11-xserver-utils, sddm, xserver-xorg, polkit-kde-agent-1, network-manager, network-manager-gnome, firewalld, '+boot_libs,
            extra=f'Breaks: linuxbr-drive-manager (<< {VERSION}), linuxbr-system (<< {VERSION})\nReplaces: linuxbr-drive-manager (<< {VERSION}), linuxbr-system (<< {VERSION})\n',architecture=run('dpkg','--print-architecture'))
    write(boot,'DEBIAN/postinst','''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    deb-systemd-helper enable linuxbr-boot-consume.service >/dev/null
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
    if [ -f /boot/grub/grub.cfg ]; then update-grub; fi
fi
''',True)
    write(boot,'DEBIAN/postrm','''#!/bin/sh
set -eu
if [ "$1" = purge ]; then deb-systemd-helper purge linuxbr-boot-consume.service; fi
if [ "$1" = remove ] || [ "$1" = purge ]; then
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
    if [ -f /boot/grub/grub.cfg ]; then update-grub; fi
fi
''',True)
    system_control.write_text(system_control.read_text().replace('Depends: ', f'Depends: linuxbr-file-properties (= {VERSION}), xdg-utils, kde-cli-tools, plasma-workspace, baloo6, filelight, python3-libvirt, libvirt-daemon-system, libvirt-clients, qemu-system-x86, qemu-system-modules-spice, qemu-utils, virtinst, virt-viewer, virt-manager, ovmf, swtpm, swtpm-tools, ksshaskpass, fwupd, gpg, python3-virt-firmware, '))
    documentation = roots['linuxbr-system'] / 'usr/share/doc/linuxbr-system'
    documentation.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'README.md', documentation / 'README.md')
    for note in (ROOT / 'docs').glob('*.md'):
        if note.name.startswith('CONTINUIDADE-'):
            continue
        destination = documentation / 'docs' / note.name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(note, destination)
    replacements = {
        '/usr/bin/plasma-discover': '#!/bin/sh\nexec /usr/bin/python3 /usr/lib/linuxbr-system/store_redirect.py "$@"\n',
        '/usr/bin/plasma-discover-update': '#!/bin/sh\nexec /usr/bin/linuxbr-store --updates\n',
        '/usr/share/applications/org.kde.discover.desktop': '[Desktop Entry]\nType=Application\nName=Loja Linux BR\nExec=linuxbr-store\nIcon=system-software-install\nNoDisplay=true\n',
    }
    for destination, content in replacements.items():
        write(roots['linuxbr-system'], 'usr/share/linuxbr/store-replacements/'+Path(destination).name, content, destination.startswith('/usr/bin/'))
    store_paths = ' '.join(replacements)
    write(roots['linuxbr-system'], 'DEBIAN/triggers', 'interest-noawait /usr/share/OVMF\n')
    write(roots['linuxbr-system'], 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ] || [ "$1" = triggered ]; then
    if [ -f /usr/share/OVMF/OVMF_VARS_4M.ms.fd ]; then
        /usr/bin/python3 /usr/lib/linuxbr-system/vm_firmware.py --prepare
    fi
fi
if [ "$1" = configure ]; then
    # PAM creates and unlocks the login store before D-Bus initializes secrets.
    # Apply the default once; later administrator choices remain intact.
    credential_policy=/var/lib/linuxbr/credential-session-policy-v1
    if [ ! -e "$credential_policy" ]; then
        systemctl --global disable gnome-keyring-daemon.service gnome-keyring-daemon.socket
        install -d -m 0755 /var/lib/linuxbr
        printf 'pam-dbus\\n' > "$credential_policy"
    fi
    for path in '''+store_paths+'''; do
        owner=$(dpkg-divert --listpackage "$path")
        if [ -z "$owner" ]; then
            [ ! -e "$path.linuxbr-original" ] && [ ! -L "$path.linuxbr-original" ]
            dpkg-divert --package linuxbr-system --add --rename --divert "$path.linuxbr-original" "$path"
        elif [ "$owner" != linuxbr-system ]; then
            echo "Desvio conflitante: $path ($owner)" >&2
            exit 1
        fi
        cp --remove-destination "/usr/share/linuxbr/store-replacements/${path##*/}" "$path"
    done
    update-desktop-database /usr/share/applications || true
    if [ -z "${2:-}" ]; then pam-auth-update --package --enable mkhomedir; fi
fi
''', True)
    write(roots['linuxbr-system'], 'DEBIAN/postrm', '''#!/bin/sh
set -eu
case "$1" in
remove|purge)
    for path in '''+store_paths+'''; do
        if [ "$(dpkg-divert --listpackage "$path")" = linuxbr-system ]; then
            rm -f "$path"
            dpkg-divert --package linuxbr-system --remove --rename --divert "$path.linuxbr-original" "$path"
        fi
    done
    ;;
esac
''', True)
    control(roots['linuxbr-device-manager'], 'linuxbr-device-manager', 'python3, python3-pyqt6, pciutils, usbutils, kmod, apt, pkexec, polkitd, polkit-kde-agent-1, nvidia-detect, mokutil')
    properties_native = work / 'properties-native'
    run('cmake', '-S', str(ROOT / 'packages/linuxbr-file-properties/native'), '-B', str(properties_native), '-DCMAKE_BUILD_TYPE=Release')
    run('cmake', '--build', str(properties_native), '-j2')
    properties = roots['linuxbr-file-properties']
    properties_multiarch = run('dpkg-architecture', '-qDEB_HOST_MULTIARCH')
    properties_plugin = properties / f'usr/lib/{properties_multiarch}/qt6/plugins/kf6/propertiesdialog/liblinuxbrfileproperties.so'
    properties_plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(properties_native / 'kf6/propertiesdialog/liblinuxbrfileproperties.so', properties_plugin)
    write(properties_native, 'debian/control', 'Source: linuxbr-file-properties\nSection: utils\nPriority: optional\nMaintainer: Linux BR\n\nPackage: linuxbr-file-properties\nArchitecture: any\nDescription: Linux BR file properties\n')
    properties_libraries = subprocess.check_output(['dpkg-shlibdeps', '-O', '-e'+str(properties_plugin.resolve())], cwd=properties_native, text=True).strip().split('=', 1)[1]
    kio_dependencies=', '.join(name+' (>= 6.13.0-6+linuxbr0.9.1)' for name in ('kio6','libkf6kiocore6','libkf6kiogui6','libkf6kiowidgets6','libkf6kiofilewidgets6'))
    control(properties, 'linuxbr-file-properties', 'python3, python3-pyqt6, acl, msitools, kup-backup, bup, kdenetwork-filesharing, samba, samba-common-bin, firewalld, '+kio_dependencies+', ' + properties_libraries,
            extra=f'Recommends: linuxbr-system (= {VERSION})\nBreaks: linuxbr-system (<< 0.8.0~beta1)\n', architecture=run('dpkg', '--print-architecture'))
    native = work / 'drive-native'
    run('cmake', '-S', str(ROOT / 'packages/linuxbr-drive-manager/native'), '-B', str(native), '-DCMAKE_BUILD_TYPE=Release')
    run('cmake', '--build', str(native), '-j2')
    drive = roots['linuxbr-drive-manager']
    run('python3', str(ROOT / 'scripts/generate-drive-capacity-icons.py'), str(drive / 'usr/share/linuxbr/drive-capacity'))
    binary = drive / 'usr/lib/linuxbr-drive-manager/linuxbr-places-sync'
    shutil.copy2(native / 'linuxbr-places-sync', binary)
    # Build is currently amd64; keep the multiarch path derived from dpkg.
    multiarch = run('dpkg-architecture', '-qDEB_HOST_MULTIARCH')
    plugin = drive / f'usr/lib/{multiarch}/qt6/plugins/kf6/kio/kio_linuxbr.so'
    plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(native / 'kf6/kio/libkio_linuxbr.so', plugin)
    write(native, 'debian/control', 'Source: linuxbr-drives\nSection: utils\nPriority: optional\nMaintainer: Linux BR\n\nPackage: linuxbr-drive-manager\nArchitecture: any\nDescription: Linux BR drives\n')
    libraries = subprocess.check_output(['dpkg-shlibdeps', '-O', '-e'+str(binary.resolve()), '-e'+str(plugin.resolve())], cwd=native, text=True).strip().split('=', 1)[1]
    control(drive, 'linuxbr-drive-manager', f'linuxbr-boot-tools (= {VERSION}), bash, konsole, kio-fuse, python3, python3-pyqt6, python3-dbus, python3-gi, gir1.2-glib-2.0, udisks2, e2fsprogs, dosfstools, ntfs-3g, exfatprogs, polkit-kde-agent-1, dolphin (>= 4:25.04.3-1+deb13u1+linuxbr2), qt6-svg-plugins, kio-extras, kde-cli-tools, kwalletmanager, linuxbr-branding, ' + libraries,
            architecture=run('dpkg', '--print-architecture'))
    control(roots['linuxbr-branding'], 'linuxbr-branding')
    # desktop-base owns this file and pins both the Debian logo and version.
    # Keep its configuration diverted so upgrades cannot undo our identity.
    write(roots['linuxbr-branding'], 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    path=/etc/xdg/kcm-about-distrorc
    owner=$(dpkg-divert --listpackage "$path")
    if [ -z "$owner" ]; then
        dpkg-divert --package linuxbr-branding --add --rename --divert "$path.debian" "$path"
    elif [ "$owner" != linuxbr-branding ]; then
        echo "Diversion conflitante: $path ($owner)" >&2
        exit 1
    fi
    mkdir -p /etc/xdg
    cp /usr/share/linuxbr/kcm-about-distrorc "$path"
fi
''', True)
    write(roots['linuxbr-branding'], 'DEBIAN/postrm', '''#!/bin/sh
set -eu
case "$1" in
remove|purge)
    path=/etc/xdg/kcm-about-distrorc
    if [ "$(dpkg-divert --listpackage "$path")" = linuxbr-branding ]; then
        rm -f "$path"
        dpkg-divert --package linuxbr-branding --remove --rename --divert "$path.debian" "$path"
    fi
    ;;
esac
''', True)

    style_build = work / 'desktop-style'
    run('cmake', '-S', str(ROOT / 'packages/linuxbr-desktop/native'), '-B', str(style_build), '-DCMAKE_BUILD_TYPE=Release')
    run('cmake', '--build', str(style_build), '-j2')
    multiarch = subprocess.check_output(['dpkg-architecture', '-qDEB_HOST_MULTIARCH'], text=True).strip()
    style_target = roots['linuxbr-desktop'] / ('usr/lib/' + multiarch + '/qt6/plugins/styles/liblinuxbrclean.so')
    style_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(style_build / 'liblinuxbrclean.so', style_target)
    write(style_build, 'debian/control', 'Source: linuxbr-desktop\nSection: x11\nPriority: optional\nMaintainer: Linux BR\n\nPackage: linuxbr-desktop\nArchitecture: any\nDescription: Linux BR style\n')
    style_libraries = subprocess.check_output(['dpkg-shlibdeps', '-O', '-e'+str(style_target.resolve())], cwd=style_build, text=True).strip().split('=', 1)[1]
    control(roots['linuxbr-desktop'], 'linuxbr-desktop', f'linuxbr-boot-tools (= {VERSION}), linuxbr-branding, plasma-workspace, plasma-desktop, kde-style-breeze, kde-style-breeze-qt5, breeze-gtk-theme, kde-config-gtk-style, libkf6config-bin, plasma-integration, libreoffice-qt6, dolphin, firefox-esr, systemsettings, plasma-discover, plasma-discover-backend-flatpak, okular, kwin-common, python3-dbus, plasma-nm, bluedevil, plasma-pa, powerdevil, qml6-module-org-kde-bluezqt, ' + style_libraries, architecture=subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip())
    write(roots['linuxbr-desktop'], 'DEBIAN/postinst', """#!/bin/sh
set -e
case "$1" in configure|triggered) python3 /usr/lib/linuxbr-desktop/plasma-layout.py ;; esac
""", 0o755)
    write(roots['linuxbr-desktop'], 'DEBIAN/prerm', """#!/bin/sh
set -e
case "$1" in remove|deconfigure) python3 /usr/lib/linuxbr-desktop/plasma-layout.py --restore ;; esac
""", 0o755)
    write(roots['linuxbr-desktop'], 'DEBIAN/triggers', 'interest-noawait /usr/share/plasma/plasmoids\n')


    boot = roots['linuxbr-boot-theme']
    control(boot, 'linuxbr-boot-theme', 'plymouth, plymouth-themes, initramfs-tools')
    for script in ['postinst', 'prerm', 'postrm']:
        write(boot, 'DEBIAN/' + script,
              (ROOT / 'packages/linuxbr-boot-theme/maintainer' / script).read_text(), True)
    # Boot-sized derivatives: preserve the vector-rendered 4K source and improve text contrast.
    source = roots['linuxbr-branding'] / 'usr/share/wallpapers/LinuxBR-graphite/contents/images/3840x2160.png'
    with Image.open(source) as image:
        for path, size in [('boot/grub/themes/linuxbr/background.png', (1920, 1080))]:
            preview = ImageOps.contain(image.convert('RGB'), size, Image.Resampling.LANCZOS)
            ImageEnhance.Brightness(preview).enhance(0.85).save(boot / path)
    plymouth = boot / 'usr/share/plymouth/themes/linuxbr'
    run('rsvg-convert', '-w', '128', '-h', '128', '-o', str(plymouth / 'logo.png'),
        str(roots['linuxbr-branding'] / 'usr/share/linuxbr/identity/symbol-color.svg'))
    for frame in range(12):
        image = Image.new('RGBA', (64, 64))
        draw = ImageDraw.Draw(image)
        for dot in range(12):
            angle = dot * math.tau / 12
            x, y = 32 + 23 * math.cos(angle), 32 + 23 * math.sin(angle)
            alpha = 45 + int(210 * ((dot - frame) % 12) / 11)
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(228, 223, 145, alpha))
        image.save(plymouth / f'spinner-{frame}.png')

    cala = roots['linuxbr-calamares-settings']
    run('dpkg-deb', '-R', str(calamares_deb), str(cala))
    upstream = run('dpkg-deb', '-f', str(calamares_deb), 'Version')
    if upstream != '13.0.13-1':
        raise SystemExit(f'Review required for new Calamares settings version: {upstream}')
    deps = run('dpkg-deb', '-f', str(calamares_deb), 'Depends')
    control(cala, 'linuxbr-calamares-settings', deps + ', linuxbr-branding',
            'Conflicts: calamares-settings-debian\nReplaces: calamares-settings-debian\nProvides: calamares-settings-debian\n')
    for filename in ['md5sums']:
        (cala / 'DEBIAN' / filename).unlink(missing_ok=True)
    # Preserve upstream diversion lifecycle, using our owning package name.
    for filename in ['preinst', 'postinst', 'prerm', 'postrm']:
        p = cala / 'DEBIAN' / filename
        if p.exists():
            p.write_text(p.read_text().replace('calamares-settings-debian', 'linuxbr-calamares-settings'))
    settings = cala / 'etc/calamares/settings.conf'
    data = load(settings); data['branding'] = 'linuxbr'
    data['modules-search']=['/etc/calamares/modules',*[path for path in data['modules-search'] if path!='/etc/calamares/modules']]
    for stage in data['sequence']:
        if 'show' in stage and 'welcome' in stage['show']:
            stage['show'].insert(stage['show'].index('welcome')+1,'packagechooser')
        if 'exec' in stage and 'packages' in stage['exec']:
            stage['exec'].insert(stage['exec'].index('packages')+1,'linuxbr_edition')
    dump(settings, data)
    shutil.copytree(ROOT/'packages/linuxbr-calamares-settings/edition',cala/'etc/calamares/modules/linuxbr_edition')
    write(cala,'etc/calamares/modules/packagechooser.conf',yaml.safe_dump(dict(mode='required',method='legacy',default='desktop',
        labels={'step':'Edição','step[pt_BR]':'Edição'},items=[
        dict(id='desktop',name='Linux BR Desktop',description='Área de trabalho completa para uso pessoal: menu Iniciar, Loja, aplicativos e compatibilidade Windows.',screenshot='/etc/calamares/branding/linuxbr/edition-desktop.svg'),
        dict(id='server',name='Linux BR Servidor',description='Console de configuração com terminal, rede, contas, serviços e máquinas virtuais. Não inicia o desktop completo; exige login. O SSH permanece desabilitado até ser habilitado explicitamente.',screenshot='/etc/calamares/branding/linuxbr/edition-server.svg')]),allow_unicode=True,sort_keys=False))
    branding = cala / 'etc/calamares/branding'
    shutil.rmtree(branding / 'debian')
    shutil.copytree(ROOT / 'packages/linuxbr-calamares-settings/branding', branding / 'linuxbr')
    desc = branding / 'linuxbr/branding.desc'
    data = load(desc)
    data['strings'].update(version=DISPLAY_VERSION, shortVersion=RELEASE['base_version'],
                           versionedName=f'Linux BR {DISPLAY_VERSION}', shortVersionedName=f'Linux BR {DISPLAY_VERSION}')
    dump(desc, data)
    shutil.copyfile(roots['linuxbr-branding'] / 'usr/share/linuxbr/identity/symbol-color.svg', branding / 'linuxbr/logo.svg')
    run('python3',str(ROOT/'scripts/prepare-installer-translations.py'),
        str(ROOT/'packages/linuxbr-calamares-settings/translations/calamares_pt_BR.ts'),str(cala))
    installer_logo=branding/'linuxbr/logo.svg'
    installer_logo.write_text(installer_logo.read_text().replace('width="2000" height="2000"','width="128" height="128"'))
    write(cala, 'etc/calamares/modules/locale.conf',
          'region: America\nzone: Sao_Paulo\nuseSystemTimezone: false\ngeoip:\n  style: none\n')
    write(cala, 'etc/calamares/modules/keyboard.conf',
          'guessLayout: false\nuseLocale1: true\nwriteEtcDefaultKeyboard: true\nconfigure:\n  kwin: true\n')
    write(cala, 'etc/calamares/modules/plymouthcfg.conf', 'plymouth_theme: linuxbr\n')
    welcome = cala / 'etc/calamares/modules/welcome.conf'
    data = load(welcome)
    for key in ['showSupportUrl', 'showKnownIssuesUrl', 'showReleaseNotesUrl']:
        data[key] = False
    dump(welcome, data)
    packages = cala / 'etc/calamares/modules/packages.conf'
    data = load(packages)
    for op in data['operations']:
        if 'remove' in op:
            op['remove'] = list(dict.fromkeys('linuxbr-calamares-settings' if p == 'calamares-settings-debian' else p for p in op['remove']))
    dump(packages, data)
    # Keep Debian's wrapper and helpers: partitioning/boot/source setup is unchanged.
    autostart = cala / 'etc/xdg/autostart/calamares-desktop-icon.desktop'
    autostart.write_text(autostart.read_text() + '\nTryExec=/usr/bin/add-calamares-desktop-icon\n')
    wrapper = cala / 'usr/bin/calamares-install-debian'
    wrapper.rename(cala / 'usr/bin/calamares-install-linuxbr')
    desktop = cala / 'usr/share/applications/calamares-install-debian.desktop'
    desktop.unlink()
    shutil.copyfile(ROOT / 'packages/linuxbr-calamares-settings/installer.desktop',
                    cala / 'usr/share/applications/calamares-install-linuxbr.desktop')
    launcher = cala / 'usr/share/applications/calamares-install-linuxbr.desktop'
    launcher.write_text('\n'.join(f'Comment=Instalar Linux BR {DISPLAY_VERSION} no computador' if line.startswith('Comment=') else line for line in launcher.read_text().splitlines()) + '\n')
    write(cala, 'usr/bin/add-calamares-desktop-icon', '''#!/bin/sh
set -eu
# Only expose the installer in a live session, never for installed users.
[ -d /run/live/medium ] || exit 0
desktop=$(xdg-user-dir DESKTOP)
mkdir -p "$desktop"
install -m 0755 /usr/share/applications/calamares-install-linuxbr.desktop "$desktop/"
''', True)

    sddm = roots['linuxbr-sddm-theme']
    extracted = work / 'breeze-upstream'
    run('dpkg-deb', '-x', str(breeze_deb), str(extracted))
    theme = sddm / 'usr/share/sddm/themes/linuxbr'
    shutil.copytree(extracted / 'usr/share/sddm/themes/breeze', theme, symlinks=True)
    run('python3',str(ROOT/'scripts/patch-boot-actions.py'),'sddm',str(theme/'Main.qml'))
    plasma_input=work/'plasma-input';plasma_input.mkdir()
    subprocess.run(['apt-get','download','plasma-workspace-data'],cwd=plasma_input,check=True,capture_output=True)
    plasma_archive=next(plasma_input.glob('plasma-workspace-data_*.deb'))
    plasma_files=work/'plasma-upstream';run('dpkg-deb','-x',str(plasma_archive),str(plasma_files))
    logout=roots['linuxbr-desktop']/'usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/logout'
    shutil.copytree(plasma_files/'usr/share/plasma/look-and-feel/org.kde.breeze.desktop/contents/logout',logout)
    run('python3',str(ROOT/'scripts/patch-boot-actions.py'),'logout',str(logout/'Logout.qml'))
    upstream_license=roots['linuxbr-desktop']/'usr/share/doc/linuxbr-desktop/plasma-workspace-copyright'
    upstream_license.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(plasma_files/'usr/share/doc/plasma-workspace-data/copyright',upstream_license)
    shutil.copyfile(ROOT / 'packages/linuxbr-sddm-theme/theme.conf', theme / 'theme.conf')
    metadata = theme / 'metadata.desktop'
    # Retain upstream authorship/license, remove translated Breeze display names.
    metadata.write_text('\n'.join(line for line in metadata.read_text().splitlines()
                                  if not line.startswith(('Name', 'Description', 'Theme-Id', 'Version=')))
                        + f'\nName=Linux BR\nDescription=Linux BR, baseado no Breeze\nTheme-Id=linuxbr\nVersion={VERSION}\n')
    copyright_path = extracted / 'usr/share/doc/sddm-theme-breeze/copyright'
    dest = sddm / 'usr/share/doc/linuxbr-sddm-theme'
    dest.mkdir(parents=True)
    shutil.copyfile(copyright_path, dest / 'copyright')
    deps = run('dpkg-deb', '-f', str(breeze_deb), 'Depends')
    control(sddm, 'linuxbr-sddm-theme', deps + f', sddm, linuxbr-branding, linuxbr-boot-tools (= {VERSION})')
    write(sddm, 'etc/sddm.conf.d/90-linuxbr.conf', '[Theme]\nCurrent=linuxbr\n')
    manifest = []
    for deb in [calamares_deb, breeze_deb, plasma_archive]:
        manifest.append(f'{hashlib.sha256(deb.read_bytes()).hexdigest()}  {deb.name}')
    for name, root in roots.items():
        # Optional desktop capabilities remain installed by default but removable.
        reject_seeded_credentials(root)
        metadata=root/'DEBIAN/control'
        metadata.write_text(optional_metadata(metadata.read_text()))
        conffiles = sorted('/' + str(p.relative_to(root)) for p in (root / 'etc').rglob('*') if p.is_file())
        write(root, 'DEBIAN/conffiles', '\n'.join(conffiles) + ('\n' if conffiles else ''))
        for path in root.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
            elif path.is_file() and not path.is_symlink():
                with path.open('rb') as stream: executable=stream.read(2)==b'#!'
                if executable:path.chmod(0o755)
        run('dpkg-deb', '--root-owner-group', '--build', str(root), str(output / f"{name}_{VERSION}_{run('dpkg', '--print-architecture') if name in ('linuxbr-drive-manager', 'linuxbr-desktop', 'linuxbr-file-properties','linuxbr-boot-tools') else 'all'}.deb"))
    (output / 'UPSTREAM-SHA256SUMS').write_text('\n'.join(manifest) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--calamares-deb', type=Path, required=True)
    parser.add_argument('--breeze-deb', type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.work, args.calamares_deb, args.breeze_deb)
