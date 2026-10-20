#!/usr/bin/env python3
"""Read-only checks for an assembled live or installed root filesystem."""
import argparse
import configparser
from pathlib import Path
import shlex
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
parser.add_argument('--mode', choices=['live', 'installed'], default='live')
args = parser.parse_args()
root = args.root
version = (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip()

def read(name):
    return (root / name.lstrip('/')).read_text()

def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)

release = dict(line.split('=', 1) for line in read('etc/os-release').splitlines() if '=' in line)
release = {key: shlex.split(value)[0] for key, value in release.items()}
require(release.get('ID') == 'linuxbr', 'ID do sistema')
require(release.get('ID_LIKE') == 'debian', 'compatibilidade declarada Debian')
require(release.get('VERSION_ID') == version, 'versao')
require('trixie' == release.get('VERSION_CODENAME'), 'codename Debian')
require('Linux BR' in read('etc/issue'), 'banner')
about_config = configparser.ConfigParser(interpolation=None)
about_config.read_string(read('etc/xdg/kcm-about-distrorc'))
require(about_config.get('General', 'LogoPath') == '/usr/share/linuxbr/identity/symbol-color.svg', 'logo das propriedades do sistema')
require(not about_config.has_option('General', 'Version'), 'versao das propriedades deve vir de os-release')
require(about_config.getboolean('General', 'UseOSReleaseVersion'), 'versao completa nas propriedades')

require('Current=linuxbr' in read('etc/sddm.conf.d/90-linuxbr.conf'), 'tema SDDM')
require((root / 'usr/share/sddm/themes/linuxbr/Main.qml').is_file(), 'QML SDDM')
require((root / 'usr/share/linuxbr/wallpaper.svg').is_file(), 'wallpaper do branding')
wallpaper = '/usr/share/wallpapers/LinuxBR-graphite/contents/images/3840x2160.png'
require((root / wallpaper.lstrip('/')).is_file(), 'wallpaper padrao grafite 4K')
require(wallpaper in read('usr/bin/linuxbr-set-wallpaper'), 'selecao do wallpaper padrao grafite 4K')
require((root / 'usr/share/icons/hicolor/scalable/apps/linuxbr.svg').is_file(), 'icone')
require('linuxbr-set-wallpaper' in read('etc/xdg/autostart/linuxbr-wallpaper.desktop'), 'defaults KDE')
sddm_theme = configparser.ConfigParser(interpolation=None)
sddm_theme.read_string(read('usr/share/sddm/themes/linuxbr/theme.conf'))
sddm_background = sddm_theme.get('General', 'background', fallback='(ausente)')
require(sddm_background == wallpaper,
        f'fundo SDDM grafite 4K: esperado {wallpaper!r}; encontrado {sddm_background!r}')
require('LookAndFeelPackage=org.linuxbr.desktop' in read('etc/skel/.config/kdeglobals'), 'tema inicial KDE')
require((root / 'usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/layouts/org.kde.plasma.desktop-layout.js').is_file(), 'layout inicial KDE')
require((root / 'boot/grub/themes/linuxbr/background.png').is_file(), 'imagem GRUB')
require('GRUB_THEME="/boot/grub/themes/linuxbr/theme.txt"' in read('etc/default/grub.d/91-linuxbr-theme.cfg'), 'tema GRUB')
require((root / 'usr/share/plymouth/themes/linuxbr/logo.png').is_file(), 'imagem Plymouth')
plymouth_config = configparser.ConfigParser(interpolation=None)
plymouth_config.read_string(read('etc/plymouth/plymouthd.conf'))
require(plymouth_config.get('Daemon', 'Theme', fallback='') == 'linuxbr', 'tema Plymouth ativo')
status = read('var/lib/dpkg/status')
require(any('Package: dolphin\n' in stanza and 'Status: install ok installed' in stanza
            and any(line.startswith('Version: ') and '+linuxbr' in line for line in stanza.splitlines())
            for stanza in status.split('\n\n')), 'Dolphin com cartoes Linux BR instalado')
packages = ['linuxbr-release', 'linuxbr-branding', 'linuxbr-desktop', 'linuxbr-sddm-theme', 'linuxbr-boot-theme', 'linuxbr-drive-manager', 'linuxbr-system', 'linuxbr-device-manager']
if args.mode == 'live':
    packages.append('linuxbr-calamares-settings')
for package in packages:
    require(any(f'Package: {package}\n' in stanza and 'Status: install ok installed' in stanza
                for stanza in status.split('\n\n')), f'pacote instalado: {package}')
if args.mode == 'live':
    branding = yaml.safe_load(read('etc/calamares/branding/linuxbr/branding.desc'))
    require(branding['sidebar'] == 'none' and branding['images']['productWelcome'] == 'logo.svg', 'instalador sem passos duplicados e com logo')
    locale = yaml.safe_load(read('etc/calamares/modules/locale.conf'))
    require(locale['region'] == 'America' and locale['zone'] == 'Sao_Paulo' and locale['geoip']['style'] == 'none', 'fuso inicial Brasil')
    keyboard = {}
    for line in read('etc/default/keyboard').splitlines():
        tokens = shlex.split(line, comments=True)
        if tokens and '=' in tokens[0]:
            key, value = tokens[0].split('=', 1)
            keyboard[key] = value
    require(keyboard.get('XKBLAYOUT') == 'br' and keyboard.get('XKBMODEL') == 'abnt2', 'teclado brasileiro ABNT2 com cedilha')
    require(yaml.safe_load(read('etc/calamares/modules/plymouthcfg.conf'))['plymouth_theme'] == 'linuxbr', 'tema Plymouth no destino Calamares')
    settings = yaml.safe_load(read('etc/calamares/settings.conf'))
    require(settings['branding'] == 'linuxbr', 'branding Calamares')
    for module in ['partition', 'unpackfs', 'users', 'bootloader', 'umount']:
        require(module in settings['sequence'][1]['exec'], 'modulo Calamares: ' + module)
    require('Instalar Linux BR' in read('usr/share/applications/calamares-install-linuxbr.desktop'), 'atalho')
    operations = yaml.safe_load(read('etc/calamares/modules/packages.conf'))['operations']
    require(any('linuxbr-calamares-settings' in op.get('remove', []) for op in operations), 'remocao do instalador no destino')
else:
    require(not (root / 'usr/share/applications/calamares-install-linuxbr.desktop').exists(), 'atalho Live removido')

require('Theme=org.linuxbr.desktop' in read('etc/xdg/ksplashrc'), 'splash Plasma Linux BR')
require((root / 'usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/splash/Splash.qml').is_file(), 'animacao de entrada Linux BR')
require('ExecStart=-/usr/bin/plymouth quit\n' in read('etc/systemd/system/plymouth-quit.service.d/linuxbr.conf') and '--retain-splash' not in read('etc/systemd/system/plymouth-quit.service.d/linuxbr.conf'), 'Plymouth libera terminal antes do SDDM')
require('ShowStatus=no' in read('etc/systemd/system.conf.d/90-linuxbr-quiet.conf'), 'status systemd oculto')



for path in ['usr/bin/nvidia-detect', 'usr/bin/mokutil',
             'usr/share/applications/linuxbr-computer.desktop',
             'usr/share/linuxbr/dolphin-computer.directory', 'usr/bin/linuxbr-device-manager',
             'usr/share/polkit-1/actions/org.linuxbr.devices.policy',
             'usr/lib/linuxbr-device-manager/install-firmware', 'usr/bin/linuxbr-system', 'usr/bin/linuxbr-drive-service',
             'usr/lib/systemd/user/linuxbr-drive-manager.service',
             'usr/share/dbus-1/services/org.linuxbr.DriveManager1.service',
             'etc/xdg/autostart/linuxbr-drive-manager-service.desktop',
             'usr/lib/linuxbr-drive-manager/linuxbr-places-sync']:
    require((root / path).is_file(), 'Central e serviço: ' + path)
require(bool(list((root / 'usr/lib').glob('*/qt6/plugins/kf6/kio/kio_linuxbr.so'))), 'protocolo Dolphin linuxbr')



for path in ('usr/bin/linuxbr-drive-properties',
             'usr/lib/linuxbr-drive-manager/capacity.py',
             'usr/lib/linuxbr-drive-manager/properties.py',
             'usr/share/linuxbr/drive-capacity/disk-000.svg',
             'usr/share/linuxbr/drive-capacity/disk-100.svg',
             'usr/share/linuxbr/drive-capacity/usb-050.svg',
             'usr/share/kio/servicemenus/linuxbr-drive-properties.desktop'):
    require((root / path).is_file(), 'capacidade e propriedades: ' + path)

for path in ('usr/bin/linuxbr-terminal-settings', 'usr/lib/linuxbr-drive-manager/terminal.py',
             'usr/share/linuxbr/terminal.bash', 'usr/share/linuxbr/bashrc',
             'usr/share/konsole/LinuxBR.profile', 'etc/xdg/konsolerc'):
    require((root / path).is_file(), 'terminal por unidades: ' + path)
require('Name=Explorador de arquivos' in (root / 'usr/share/applications/org.kde.dolphin.desktop').read_text(),
        'nome Explorador de arquivos')

print(f'PASS: identidade e configuracoes {args.mode} Linux BR {version}; nao valida boot ou GUI.')
