#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path
import yaml
work = Path(sys.argv[1])
original = work / 'original-calamares'
subprocess.run(['dpkg-deb', '-x', str(next((work / 'upstream').glob('calamares-settings-debian_*.deb'))), str(original)], check=True)
modified = work / 'work/linuxbr-calamares-settings'
a = yaml.safe_load((original / 'etc/calamares/settings.conf').read_text())
b = yaml.safe_load((modified / 'etc/calamares/settings.conf').read_text())
assert a['sequence'] == b['sequence'], 'Installation sequence changed'
for path in (original / 'usr/share/calamares/helpers').iterdir():
    assert path.read_bytes() == (modified / path.relative_to(original)).read_bytes(), path
for package in (work / 'debs').glob('*.deb'):
    subprocess.run(['dpkg-deb', '--info', str(package)], check=True, stdout=subprocess.DEVNULL)
assert 'linuxbr-calamares-settings' in (modified / 'DEBIAN/preinst').read_text()
assert 'linuxbr-calamares-settings' in (modified / 'DEBIAN/postrm').read_text()
assert not (modified / 'usr/share/applications/calamares-install-debian.desktop').exists()
assert 'linuxbr-calamares-settings' in (modified / 'etc/calamares/modules/packages.conf').read_text()
print('PASS: pacotes, sequencia Calamares e helpers preservados')

branding = yaml.safe_load((modified / 'etc/calamares/branding/linuxbr/branding.desc').read_text())
assert branding['sidebar'] == 'none'
assert branding['images']['productWelcome'] == 'logo.svg'
assert (modified / 'etc/calamares/branding/linuxbr/logo.svg').read_bytes() == (work / 'work/linuxbr-branding/usr/share/linuxbr/identity/symbol-color.svg').read_bytes()
locale = yaml.safe_load((modified / 'etc/calamares/modules/locale.conf').read_text())
assert (locale['region'], locale['zone']) == ('America', 'Sao_Paulo')
assert locale['geoip']['style'] == 'none' and locale['useSystemTimezone'] is False
keyboard = yaml.safe_load((modified / 'etc/calamares/modules/keyboard.conf').read_text())
assert keyboard['guessLayout'] is False and keyboard['configure']['kwin'] is True
assert 'anchors.centerIn: parent' in (modified / 'etc/calamares/branding/linuxbr/show.qml').read_text()
print('PASS: fuso, teclado e logo centralizada do instalador')

drive = work / 'work/linuxbr-drive-manager'
assert (drive / 'usr/bin/linuxbr-drive-manager').stat().st_mode & 0o111
assert (drive / 'usr/lib/linuxbr-drive-manager/app.py').is_file()
assert (drive / 'usr/share/applications/linuxbr-drive-manager.desktop').is_file()
assert 'python3-pyqt6' in (drive / 'DEBIAN/control').read_text()
print('PASS: pacote Drive Manager e entrada no menu')

quit_override = (work / 'work/linuxbr-boot-theme/etc/systemd/system/plymouth-quit.service.d/linuxbr.conf').read_text()
assert 'ExecStart=-/usr/bin/plymouth quit\n' in quit_override
assert '--retain-splash' not in quit_override
print('PASS: Plymouth libera o terminal antes de iniciar SDDM')

assert (drive / 'usr/lib/linuxbr-drive-manager/linuxbr-places-sync').stat().st_mode & 0o111
assert list((drive / 'usr/lib').glob('*/qt6/plugins/kf6/kio/kio_linuxbr.so'))
assert 'Architecture: all' not in (drive / 'DEBIAN/control').read_text()
assert (drive / 'usr/lib/systemd/user/linuxbr-drive-manager.service').is_file()
assert (drive / 'usr/share/dbus-1/services/org.linuxbr.DriveManager1.service').is_file()
assert (work / 'work/linuxbr-system/usr/bin/linuxbr-system').stat().st_mode & 0o111
print('PASS: Central, serviço de sessão e plugin KIO nativo empacotados')

devices = work / 'work/linuxbr-device-manager'
assert (devices / 'usr/bin/linuxbr-device-manager').stat().st_mode & 0o111
assert (devices / 'usr/lib/linuxbr-device-manager/install-firmware').stat().st_mode & 0o111
assert '-I /usr/lib/linuxbr-device-manager/firmware_admin.py' in (devices / 'usr/lib/linuxbr-device-manager/install-firmware').read_text()
import xml.etree.ElementTree as ET
policy = ET.parse(devices / 'usr/share/polkit-1/actions/org.linuxbr.devices.policy').getroot()
action = policy.find('action')
assert action.find('defaults/allow_active').text == 'auth_admin'
assert action.find('defaults/allow_inactive').text == 'no'
assert action.find('annotate').text == '/usr/lib/linuxbr-device-manager/install-firmware'
assert 'linuxbr-device-manager' in (work / 'work/linuxbr-system/DEBIAN/control').read_text()
print('PASS: dispositivos, helper isolado, política polkit e integração da Central')

version = (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip()
assert branding['strings']['shortVersion'] == version
assert f'Linux BR {version} Alpha' in (work / 'work/linuxbr-release/usr/share/linuxbr/release/issue').read_text()
assert f'VERSION_ID="{version}"' in (work / 'work/linuxbr-release/etc/linuxbr-release').read_text()
assert f'Linux BR {version} Alpha' in (modified / 'usr/share/applications/calamares-install-linuxbr.desktop').read_text()
print('PASS: versão única no release, banner e instalador')

assert 'nvidia-detect' in (devices / 'DEBIAN/control').read_text()
assert 'mokutil' in (devices / 'DEBIAN/control').read_text()
assert (devices / 'usr/lib/linuxbr-device-manager/proprietary.py').is_file()
assert 'HomeUrl=linuxbr:/' in (drive / 'etc/xdg/dolphinrc').read_text()
assert (drive / 'usr/share/applications/linuxbr-computer.desktop').is_file()
assert 'GroupedSorting=true' in (drive / 'usr/share/linuxbr/dolphin-computer.directory').read_text()
print('PASS: detector NVIDIA e visão Este computador no Dolphin')

identity = work / 'work/linuxbr-branding'
about_config = (identity / 'usr/share/linuxbr/kcm-about-distrorc').read_text()
assert 'LogoPath=/usr/share/linuxbr/identity/symbol-color.svg' in about_config
assert 'UseOSReleaseVersion=true' in about_config
assert not any(line.startswith('Version=') for line in about_config.splitlines())
for script in ['postinst', 'postrm']:
    assert 'dpkg-divert --package linuxbr-branding' in (identity / 'DEBIAN' / script).read_text()
assert (work / 'work/linuxbr-system/usr/lib/linuxbr-system/about.py').is_file()
print('PASS: propriedades Linux BR e protecao da configuracao KDE')

assert 'kio-fuse' in (drive / 'DEBIAN/control').read_text()
assert 'DefaultProfile=LinuxBR.profile' in (drive / 'etc/xdg/konsolerc').read_text()
assert '--rcfile /usr/share/linuxbr/bashrc -i' in (drive / 'usr/share/konsole/LinuxBR.profile').read_text()
assert (drive / 'usr/bin/linuxbr-terminal-settings').stat().st_mode & 0o111
assert (drive / 'usr/lib/linuxbr-drive-manager/terminal.py').is_file()
print('PASS: perfil interativo, configuracao de terminal e KIO FUSE empacotados')

# Window theme payload must survive packaging alongside the desktop defaults.
desktop = work / 'work/linuxbr-desktop'
for relative in ['etc/xdg/breezerc', 'etc/xdg/kwinrc', 'etc/xdg/gtk-3.0/settings.ini',
                 'etc/xdg/gtk-4.0/settings.ini', 'usr/bin/linuxbr-apply-theme',
                 'usr/share/themes/LinuxBRClean/gtk-3.0/gtk.css',
                 'usr/share/themes/LinuxBRClean/gtk-4.0/gtk.css']:
    assert (desktop / relative).is_file(), relative
assert 'breeze-gtk-theme' in (desktop / 'DEBIAN/control').read_text()
print('PASS: tema global de janelas e aplicação por usuário empacotados')

assert list(desktop.glob('usr/lib/*/qt6/plugins/styles/liblinuxbrclean.so'))
assert (desktop / 'usr/lib/linuxbr-desktop/plasma-layout.py').is_file()
assert (desktop / 'DEBIAN/triggers').is_file()
print('PASS: estilo nativo e manutenção dos layouts Plasma empacotados')
