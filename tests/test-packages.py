#!/usr/bin/env python3
import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import yaml
work = Path(sys.argv[1])
original = work / 'original-calamares'
subprocess.run(['dpkg-deb', '-x', str(next((work / 'upstream').glob('calamares-settings-debian_*.deb'))), str(original)], check=True)
modified = work / 'work/linuxbr-calamares-settings'
a = yaml.safe_load((original / 'etc/calamares/settings.conf').read_text())
b = yaml.safe_load((modified / 'etc/calamares/settings.conf').read_text())
expected=a['sequence']
for stage in expected:
    if 'show' in stage and 'welcome' in stage['show']:stage['show'].insert(stage['show'].index('welcome')+1,'packagechooser')
    if 'exec' in stage and 'packages' in stage['exec']:stage['exec'].insert(stage['exec'].index('packages')+1,'linuxbr_edition')
assert expected == b['sequence'], 'Unexpected installation sequence change'
assert '/etc/calamares/modules' in b['modules-search']
chooser=yaml.safe_load((modified/'etc/calamares/modules/packagechooser.conf').read_text())
assert chooser['mode']=='required' and chooser['method']=='legacy' and chooser['default']=='desktop'
assert [item['id'] for item in chooser['items']]==['desktop','server']
assert len({item['screenshot'] for item in chooser['items']})==2
for item in chooser['items']:
    assert (modified/item['screenshot'].lstrip('/')).is_file(),item['screenshot']
assert (modified/'etc/calamares/modules/linuxbr_edition/main.py').is_file()
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
installer_logo=ET.parse(modified/'etc/calamares/branding/linuxbr/logo.svg').getroot()
original_logo=ET.parse(work/'work/linuxbr-branding/usr/share/linuxbr/identity/symbol-color.svg').getroot()
assert installer_logo.get('width')==installer_logo.get('height')=='128'
assert installer_logo.get('viewBox')==original_logo.get('viewBox')
assert [ET.tostring(child) for child in installer_logo]==[ET.tostring(child) for child in original_logo]
locale = yaml.safe_load((modified / 'etc/calamares/modules/locale.conf').read_text())
assert (locale['region'], locale['zone']) == ('America', 'Sao_Paulo')
assert locale['geoip']['style'] == 'none' and locale['useSystemTimezone'] is False
keyboard = yaml.safe_load((modified / 'etc/calamares/modules/keyboard.conf').read_text())
assert keyboard['guessLayout'] is False and keyboard['configure']['kwin'] is True
assert keyboard['useLocale1'] is True
from PyQt6.QtCore import QTranslator
translator=QTranslator()
assert translator.load(str(modified/'usr/share/calamares/lang/calamares_pt_BR.qm'))
assert translator.translate('Config','Set timezone to %1.','@action')=='Definir o fuso horário como %1.'
assert translator.translate('Config','Keyboard model has been set to %1.',
    '@label, %1 is keyboard model, as in Apple Magic Keyboard')=='O modelo de teclado será definido como %1.'
print('PASS: tradução compilada preserva modelo de teclado e fuso horário')
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
assert (work / 'work/linuxbr-system/usr/bin/linuxbr-welcome').stat().st_mode & 0o111
assert (work / 'work/linuxbr-system/usr/lib/linuxbr-system/welcome.py').is_file()
assert (work / 'work/linuxbr-system/etc/xdg/autostart/linuxbr-welcome.desktop').is_file()
assert (work / 'work/linuxbr-system/usr/lib/linuxbr-system/display_page.py').is_file()
assert (work / 'work/linuxbr-system/usr/lib/linuxbr-system/remote_page.py').is_file()
assert (work / 'work/linuxbr-system/usr/lib/linuxbr-system/power_page.py').is_file()
assert (work / 'work/linuxbr-system/usr/lib/linuxbr-system/power_backend.py').is_file()
assert (work / 'work/linuxbr-system/usr/lib/systemd/user/linuxbr-vnc.service').is_file()
assert 'krdp' in (work / 'work/linuxbr-system/DEBIAN/control').read_text()
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
release_control=(work/'work/linuxbr-release/DEBIAN/control').read_text()
edition_control=(work/'work/linuxbr-desktop-edition/DEBIAN/control').read_text()
assert f'linuxbr-desktop-edition (= {version}) | linuxbr-server (= {version})' in release_control
assert f'linuxbr-boot-tools (= {version})' in (work/'work/linuxbr-desktop/DEBIAN/control').read_text()
for name in ('branding','desktop','sddm-theme','boot-theme','drive-manager','system','device-manager','file-properties'):
    assert f'linuxbr-{name} (= {version})' in (release_control if name in ('branding','boot-theme') else edition_control), name
assert 'linuxbr-calamares-settings' not in release_control
assert f'linuxbr-file-properties (= {version})' in (work/'work/linuxbr-system/DEBIAN/control').read_text()
for name in ('kio6','libkf6kiocore6','libkf6kiogui6','libkf6kiowidgets6','libkf6kiofilewidgets6'):
    assert name+' (>= 6.13.0-6+linuxbr0.9.1)' in (work/'work/linuxbr-file-properties/DEBIAN/control').read_text()
assert 'dolphin (>= 4:25.04.3-1+deb13u1+linuxbr2)' in (work/'work/linuxbr-drive-manager/DEBIAN/control').read_text()
print('PASS: atualização da edição seleciona os componentes exatos e o KIO com Aplicar')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_info import release_info
display_version=release_info(Path(__file__).resolve().parents[1])['display_version']
assert branding['strings']['shortVersion'] == version.split('~')[0]
assert f'Linux BR {display_version}' in (work / 'work/linuxbr-release/usr/share/linuxbr/release/issue').read_text()
assert f'VERSION_ID="{version}"' in (work / 'work/linuxbr-release/etc/linuxbr-release').read_text()
assert f'Linux BR {display_version}' in (modified / 'usr/share/applications/calamares-install-linuxbr.desktop').read_text()
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
assert (work/'work/linuxbr-boot-tools/usr/lib/linuxbr-drive-manager/terminal.py').is_file()
print('PASS: perfil interativo, configuracao de terminal e KIO FUSE empacotados')

# Window theme payload must survive packaging alongside the desktop defaults.
desktop = work / 'work/linuxbr-desktop'
assert not (desktop / 'etc/xdg/plasmanotifyrc').exists(), 'plasma-workspace possui esse arquivo'
assert (desktop / 'etc/skel/.config/plasmanotifyrc').is_file()
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

owners={}
for package in (work/'work').iterdir():
    if not (package/'DEBIAN/control').is_file():continue
    for path in package.rglob('*'):
        relative=path.relative_to(package)
        if relative.parts[0]=='DEBIAN' or not (path.is_file() or path.is_symlink()):continue
        assert str(relative) not in owners, f'Arquivo duplicado: {relative}: {owners.get(str(relative))} e {package.name}'
        owners[str(relative)]=package.name
assert owners['etc/xdg/dolphinrc']=='linuxbr-drive-manager'
for path in ['usr/share/linuxbr/bashrc','usr/lib/linuxbr-system/snapshot_service.py',
             'etc/apt/apt.conf.d/80linuxbr-recovery','etc/linuxbr/recovery-policy.json',
             'usr/share/linuxbr/firmware/certificates.json']:
    assert owners[path]=='linuxbr-boot-tools',path
server_control=(work/'work/linuxbr-server/DEBIAN/control').read_text()
server_depends=next(line for line in server_control.splitlines() if line.startswith('Depends:'))
assert 'linuxbr-boot-tools' in server_depends
assert all(name not in server_depends for name in ['linuxbr-system','linuxbr-desktop','plasma-desktop','plasma-workspace'])
assert (work/'work/linuxbr-boot-tools/usr/lib/linuxbr-server/desktop_theme.py').is_file()
assert 'vm_firmware.py --prepare' in (work/'work/linuxbr-server/DEBIAN/postinst').read_text()
system=work/'work/linuxbr-system'
for name in ['linuxbr-recovery','linuxbr-setup']:
    assert (system/'usr/bin'/name).stat().st_mode & 0o111
for dependency in ['kup-backup','bup','rsync']:
    assert dependency in (system/'DEBIAN/control').read_text()
print('PASS: propriedade única dos arquivos e dependências de backup da 0.5')
