#!/usr/bin/env python3
"""Build local .debs from project assets and explicit Debian input packages."""
import argparse
import hashlib
import math
import shutil
import subprocess
from pathlib import Path
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text().strip()

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
 Distribution-specific configuration for Linux BR {VERSION} Alpha.
'''.replace('\n\n', '\n'))

def load(path):
    return yaml.safe_load(path.read_text())

def dump(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

def build(output, work, calamares_deb, breeze_deb):
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    names = ['linuxbr-release', 'linuxbr-branding', 'linuxbr-desktop',
             'linuxbr-calamares-settings', 'linuxbr-sddm-theme', 'linuxbr-boot-theme', 'linuxbr-drive-manager', 'linuxbr-system', 'linuxbr-device-manager']
    roots = {name: work / name for name in names}
    for name, root in roots.items():
        root.mkdir()  # Never silently reuse an old package tree.
        source = ROOT / 'packages' / name / 'files'
        if source.exists():
            shutil.copytree(source, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    release = roots['linuxbr-release']
    # Store payload outside the diverted paths; dpkg owns only our source files.
    for path in ['etc/issue', 'etc/linuxbr-release']:
        if path == 'etc/issue':
            dest = release / 'usr/share/linuxbr/release/issue'
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(release / path, dest)
    write(release, 'usr/share/linuxbr/release/issue', f'Linux BR {VERSION} Alpha (base Debian 13) ' + r'\n \l' + '\n')
    write(release, 'etc/linuxbr-release', f'NAME="Linux BR"\nVERSION="{VERSION} Alpha"\nVERSION_ID="{VERSION}"\nBASE="Debian 13 (trixie)"\n')
    write(release, 'usr/share/linuxbr/release/os-release', f'''NAME="Linux BR"
PRETTY_NAME="Linux BR {VERSION} Alpha"
ID=linuxbr
ID_LIKE=debian
VERSION_ID="{VERSION}"
VERSION="{VERSION} Alpha (base Debian 13)"
VERSION_CODENAME=trixie
DEBIAN_CODENAME=trixie
LOGO=linuxbr
''')
    shutil.copyfile(release / 'usr/share/linuxbr/release/issue', release / 'usr/share/linuxbr/release/issue.net')
    control(release, 'linuxbr-release', 'base-files, linuxbr-branding')
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
    control(roots['linuxbr-system'], 'linuxbr-system', 'linuxbr-drive-manager, linuxbr-device-manager, systemsettings, kinfocenter, partitionmanager, plasma-discover, print-manager, plasma-nm, bluedevil, konsole, accountsservice, python3-dbus, realmd, adcli, sssd-ad, sssd-tools, libnss-sss, libpam-sss, libpam-modules, libpam-runtime, samba-common-bin, packagekit, polkit-kde-agent-1, krdc, krfb, powerdevil, kde-config-screenlocker, kscreen, plasma-pa, kdeconnect, network-manager-openvpn, network-manager-vpnc, network-manager-openconnect, plasma-discover-backend-flatpak, dpkg, libkf6config-bin, firewalld, iproute2, network-manager, pulseaudio-utils, passwd')
    write(roots['linuxbr-system'], 'DEBIAN/postinst', """#!/bin/sh
set -eu
if [ "$1" = configure ] && [ -z "${2:-}" ]; then
    pam-auth-update --package --enable mkhomedir
fi
""", True)
    control(roots['linuxbr-device-manager'], 'linuxbr-device-manager', 'python3, python3-pyqt6, pciutils, usbutils, kmod, apt, pkexec, polkitd, polkit-kde-agent-1, nvidia-detect, mokutil')
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
    control(drive, 'linuxbr-drive-manager', 'bash, konsole, kio-fuse, python3, python3-pyqt6, python3-dbus, python3-gi, gir1.2-glib-2.0, udisks2, e2fsprogs, dosfstools, ntfs-3g, exfatprogs, polkit-kde-agent-1, dolphin, qt6-svg-plugins, kio-extras, linuxbr-branding, ' + libraries,
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
    control(roots['linuxbr-desktop'], 'linuxbr-desktop', 'linuxbr-branding, plasma-workspace, plasma-desktop, kde-style-breeze, kde-style-breeze-qt5, breeze-gtk-theme, kde-config-gtk-style, libkf6config-bin, plasma-integration, libreoffice-qt6, dolphin, firefox-esr, systemsettings, plasma-discover, plasma-discover-backend-flatpak, okular, kwin-common, python3-dbus, plasma-nm, bluedevil, plasma-pa, powerdevil, qml6-module-org-kde-bluezqt, ' + style_libraries, architecture=subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip())
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
    data = load(settings); data['branding'] = 'linuxbr'; dump(settings, data)
    branding = cala / 'etc/calamares/branding'
    shutil.rmtree(branding / 'debian')
    shutil.copytree(ROOT / 'packages/linuxbr-calamares-settings/branding', branding / 'linuxbr')
    desc = branding / 'linuxbr/branding.desc'
    data = load(desc)
    data['strings'].update(version=f'{VERSION} Alpha', shortVersion=VERSION,
                           versionedName=f'Linux BR {VERSION} Alpha', shortVersionedName=f'Linux BR {VERSION} Alpha')
    dump(desc, data)
    shutil.copyfile(roots['linuxbr-branding'] / 'usr/share/linuxbr/identity/symbol-color.svg', branding / 'linuxbr/logo.svg')
    write(cala, 'etc/calamares/modules/locale.conf',
          'region: America\nzone: Sao_Paulo\nuseSystemTimezone: false\ngeoip:\n  style: none\n')
    write(cala, 'etc/calamares/modules/keyboard.conf',
          'guessLayout: false\nwriteEtcDefaultKeyboard: true\nconfigure:\n  kwin: true\n')
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
    launcher.write_text('\n'.join(f'Comment=Instalar Linux BR {VERSION} Alpha no computador' if line.startswith('Comment=') else line for line in launcher.read_text().splitlines()) + '\n')
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
    control(sddm, 'linuxbr-sddm-theme', deps + ', sddm, linuxbr-branding')
    write(sddm, 'etc/sddm.conf.d/90-linuxbr.conf', '[Theme]\nCurrent=linuxbr\n')
    manifest = []
    for deb in [calamares_deb, breeze_deb]:
        manifest.append(f'{hashlib.sha256(deb.read_bytes()).hexdigest()}  {deb.name}')
    for name, root in roots.items():
        conffiles = sorted('/' + str(p.relative_to(root)) for p in (root / 'etc').rglob('*') if p.is_file())
        write(root, 'DEBIAN/conffiles', '\n'.join(conffiles) + ('\n' if conffiles else ''))
        for path in root.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
        run('dpkg-deb', '--root-owner-group', '--build', str(root), str(output / f"{name}_{VERSION}_{run('dpkg', '--print-architecture') if name in ('linuxbr-drive-manager', 'linuxbr-desktop') else 'all'}.deb"))
    (output / 'UPSTREAM-SHA256SUMS').write_text('\n'.join(manifest) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--calamares-deb', type=Path, required=True)
    parser.add_argument('--breeze-deb', type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.work, args.calamares_deb, args.breeze_deb)
