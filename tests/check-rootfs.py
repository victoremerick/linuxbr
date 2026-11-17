#!/usr/bin/env python3
"""Read-only checks for an assembled live or installed root filesystem."""
import argparse
import configparser
import json
from pathlib import Path
import shlex
import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from credential_policy import reject_seeded_credentials

parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
parser.add_argument('--mode', choices=['live', 'installed'], default='live')
parser.add_argument('--edition', choices=['desktop', 'vm-server'], default='desktop')
parser.add_argument('--installer-only', action='store_true')
args = parser.parse_args()
root = args.root
version = (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip()

def read(name):
    return (root / name.lstrip('/')).read_text()

def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)


def desktop_installer():
    settings = yaml.safe_load(read('etc/calamares/settings.conf'))
    require(settings['branding'] == 'linuxbr', 'branding Calamares')
    show = settings['sequence'][0]['show']
    require(show == ['welcome', 'linuxbr_installation', 'partition', 'summary'],
            'instalação Desktop em duas etapas: termos, disco e resumo')
    jobs = settings['sequence'][1]['exec']
    required = ('partition', 'unpackfs', 'bootloader', 'linuxbr_initial_setup', 'umount')
    for module in required:
        require(module in jobs, 'módulo Calamares: ' + module)
    require([jobs.index(name) for name in required] == sorted(jobs.index(name) for name in required),
            'ordem das operações de instalação no disco')
    require(jobs.index('linuxbr_initial_setup') + 1 == jobs.index('umount'),
            'marcador de primeiro boot gravado antes de desmontar o disco')
    require(not {'users', 'locale', 'localecfg', 'keyboard', 'networkcfg'}.intersection(jobs),
            'conta, idioma, teclado e rede reservados para o primeiro boot')
    require(all(settings.get(option) is True for option in (
        'prompt-install', 'disable-cancel-during-exec', 'hide-back-and-next-during-exec')),
        'confirmação do disco e bloqueio de cancelamento durante a instalação')
    for path in ('etc/calamares/modules/linuxbr_installation/libcalamares_viewmodule_linuxbr_installation.so',
                 'etc/calamares/modules/linuxbr_initial_setup/main.py', 'usr/lib/linuxbr-installer/preflight.py'):
        require((root / path).is_file(), 'integração da instalação e primeiro boot: ' + path)
    require(read('etc/calamares/modules/linuxbr_edition/media-edition').strip() == 'desktop',
            'instalador dedicado ao Desktop')
    require('Instalar Linux BR' in read('usr/share/applications/calamares-install-linuxbr.desktop'), 'atalho')
    operations = yaml.safe_load(read('etc/calamares/modules/packages.conf'))['operations']
    require(any('linuxbr-calamares-settings' in op.get('remove', []) for op in operations),
            'remoção do instalador no destino')


if args.installer_only:
    require(args.edition == 'desktop' and args.mode == 'live', 'validação isolada do instalador Desktop')
    desktop_installer()
    print('PASS: pacote do instalador Desktop e transição para a configuração inicial.')
    sys.exit(0)

release = dict(line.split('=', 1) for line in read('etc/os-release').splitlines() if '=' in line)
release = {key: shlex.split(value)[0] for key, value in release.items()}
require(release.get('ID') == 'linuxbr', 'ID do sistema')
require(release.get('ID_LIKE') == 'debian', 'compatibilidade declarada Debian')
require(release.get('VERSION_ID') == version, 'versao')
require('trixie' == release.get('VERSION_CODENAME'), 'codename Debian')
require('Linux BR' in read('etc/issue'), 'banner')
if args.edition == 'vm-server':
    status = read('var/lib/dpkg/status')
    installed = {stanza.splitlines()[0].removeprefix('Package: ') for stanza in status.split('\n\n')
                 if stanza.startswith('Package: ') and '\nStatus: install ok installed\n' in stanza}
    required = {'linuxbr-release', 'linuxbr-server', 'linuxbr-boot-tools', 'libvirt-daemon-system',
                'qemu-system-x86', 'qemu-utils', 'virtinst', 'ovmf', 'swtpm'}
    if args.mode == 'live':
        required.update(('calamares', 'linuxbr-calamares-settings'))
        installer = 'etc/calamares/modules/linuxbr_edition/media-edition'
        require((root / installer).is_file() and read(installer).strip() == 'virtualization',
                'instalador dedicado ao VM Server')
        settings = yaml.safe_load(read('etc/calamares/settings.conf'))
        require(not any('packagechooser' in stage.get('show', []) for stage in settings['sequence']),
                'instalador sem escolha de edição')
        require('Instalar Linux BR VM Server' in read('usr/share/applications/calamares-install-linuxbr.desktop'),
                'identidade do instalador VM Server')
    require(required <= installed, 'pacotes VM Server ausentes: ' + ', '.join(sorted(required - installed)))
    desktop = {'linuxbr-system', 'linuxbr-desktop', 'linuxbr-desktop-edition', 'plasma-desktop',
               'plasma-workspace', 'task-kde-desktop', 'chromium', 'wine', 'libreoffice-writer'}
    require(not desktop.intersection(installed), 'pacotes Desktop presentes na mídia VM Server')
    require(read('etc/linuxbr/edition').strip() == 'virtualization', 'perfil VM Server')
    for path in ('usr/bin/linuxbr-minimal-session', 'usr/bin/linuxbr-server-terminal', 'usr/bin/terminal',
                 'usr/lib/linuxbr-server/virtualization_backend.py'):
        require((root / path).is_file(), 'componente VM Server: ' + path)
    print(f'PASS: composição do Linux BR VM Server {version}; o boot exige ensaio da ISO.')
    sys.exit(0)
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
try:
    reject_seeded_credentials(root)
except ValueError as error:
    require(False, str(error))
for path in ('usr/bin/linuxbr-credentials', 'usr/lib/linuxbr-system/credentials.py',
             'etc/xdg/autostart/linuxbr-credentials.desktop',
             'usr/share/applications/linuxbr-credentials.desktop'):
    require((root / path).is_file(), 'cofre de credenciais: '+path)
require(read('var/lib/linuxbr/credential-session-policy-v1').strip() == 'pam-dbus',
        'cofre inicializado depois da autenticação PAM')
for unit, target in (('gnome-keyring-daemon.service', 'graphical-session-pre.target'),
                     ('gnome-keyring-daemon.socket', 'sockets.target')):
    require(not (root / 'etc/systemd/user' / (target + '.wants') / unit).is_symlink(),
            'cofre sem inicialização global antecipada: ' + unit)
    require('disable ' + unit in read('usr/lib/systemd/user-preset/50-linuxbr-credentials.preset'),
            'política padrão de credenciais: ' + unit)
for path in ('usr/bin/linuxbr-welcome', 'usr/bin/linuxbr-task-manager', 'usr/lib/linuxbr-system/welcome.py',
             'usr/share/applications/linuxbr-welcome.desktop',
             'usr/share/applications/linuxbr-task-manager.desktop',
             'etc/xdg/autostart/linuxbr-welcome.desktop',
             'usr/share/hunspell/pt_BR.dic'):
    require((root / path).is_file(), 'experiência brasileira: ' + path)
require('Meta+I' in read('etc/skel/.config/kglobalshortcutsrc'), 'atalho inicial da Central')
require('[Module-kded_plasma-welcome]\nautoload=false' in read('etc/skel/.config/kded5rc'), 'primeiros passos sem assistente KDE duplicado')
if args.mode == 'live':
    require('LANG=pt_BR.UTF-8' in read('etc/default/locale').replace('"', ''), 'locale brasileiro na imagem')
require((root / 'usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/layouts/org.kde.plasma.desktop-layout.js').is_file(), 'layout inicial KDE')
require((root / 'boot/grub/themes/linuxbr/background.png').is_file(), 'imagem GRUB')
require('GRUB_THEME="/boot/grub/themes/linuxbr/theme.txt"' in read('etc/default/grub.d/91-linuxbr-theme.cfg'), 'tema GRUB')
require((root / 'usr/share/plymouth/themes/linuxbr/logo.png').is_file(), 'imagem Plymouth')
plymouth_config = configparser.ConfigParser(interpolation=None)
plymouth_config.read_string(read('etc/plymouth/plymouthd.conf'))
require(plymouth_config.get('Daemon', 'Theme', fallback='') == 'linuxbr', 'tema Plymouth ativo')
status = read('var/lib/dpkg/status')
for package in ('chromium','chromium-l10n','chromium-sandbox','kup-backup','bup','rsync',
                'gnome-keyring','libpam-gnome-keyring','gir1.2-secret-1','seahorse'):
    require(any(f'Package: {package}\n' in stanza and 'Status: install ok installed' in stanza
                for stanza in status.split('\n\n')), 'aplicativos web: '+package)
for package in ('kwallet6', 'libkf6wallet-data', 'libkf6wallet6', 'libkf6walletbackend6'):
    require(any(f'Package: {package}\n' in stanza and 'Status: install ok installed' in stanza
                and 'Version: 6.13.0-1+linuxbr2\n' in stanza + '\n'
                for stanza in status.split('\n\n')), 'cofre com gravação persistente: ' + package)

metadata=json.loads(read('usr/share/linuxbr/release-info.json'))
require(metadata['version']==version,'metadados da distribuição')
for path in ('usr/bin/linuxbr-recovery','usr/bin/linuxbr-setup','usr/bin/linuxbr-session-actions',
             'usr/lib/linuxbr-system/recovery.py','usr/lib/linuxbr-system/setup_flow.py',
             'usr/lib/linuxbr-system/session_actions.py','usr/lib/linuxbr-system/webapp_icons.py',
             'usr/share/applications/linuxbr-recovery.desktop','usr/share/applications/linuxbr-setup.desktop',
             'usr/share/applications/linuxbr-session-actions.desktop','usr/bin/kup-filedigger'):
    require((root/path).is_file(),'integração da distribuição: '+path)
require('[services][linuxbr-session-actions.desktop]\n_launch=Ctrl+Alt+Del' in read('etc/skel/.config/kglobalshortcutsrc'),
        'Ctrl+Alt+Del na nova conta')
for path in ('usr/bin/linuxbr-store', 'usr/lib/linuxbr-system/store.py',
             'usr/lib/linuxbr-system/store_backend.py', 'usr/share/linuxbr/store/catalog.json',
             'usr/share/applications/linuxbr-store.desktop',
             'usr/bin/linuxbr-webapps','usr/bin/linuxbr-webapps-host',
             'usr/share/linuxbr/webapps/manifest.json','usr/share/linuxbr/webapps/catalog.json',
             'usr/share/linuxbr/webapps/profiles-worker.js',
             'etc/chromium/native-messaging-hosts/org.linuxbr.webapps.json',
             'etc/chromium.d/linuxbr-webapps'):
    require((root/path).is_file(), 'integração Chromium: '+path)
require('x-scheme-handler/https=chromium.desktop;' in read('etc/skel/.config/mimeapps.list'), 'navegador inicial Chromium')
for path in ('etc/skel/.config/kdeglobals','etc/xdg/kdeglobals',
             'usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/defaults'):
    require('BrowserApplication=chromium.desktop' in read(path), 'navegador KDE: '+path)
extension_link=root/'usr/share/chromium/extensions/linuxbr-webapps'
require(extension_link.is_symlink() and str(extension_link.readlink())=='/usr/share/linuxbr/webapps', 'extensão carregada junto à integração KDE')
for package in ('wine','wine64','steam-installer','steam-devices','winetricks','vulkan-tools'):
    require(any(f'Package: {package}\n' in stanza and 'Status: install ok installed' in stanza
                for stanza in status.split('\n\n')), 'compatibilidade Windows: '+package)
for package in ('wine32','libwine','mesa-vulkan-drivers','libvulkan1'):
    require(any(f'Package: {package}\n' in stanza and 'Architecture: i386\n' in stanza
                and 'Status: install ok installed' in stanza for stanza in status.split('\n\n')),
            'compatibilidade 32 bits: '+package)
for path in ('usr/bin/linuxbr-windows','usr/lib/linuxbr-system/windows_compat.py',
             'usr/lib/linuxbr-system/windows_runner.py','usr/lib/linuxbr-system/windows_tools.py',
             'usr/share/applications/linuxbr-windows.desktop'):
    require((root/path).is_file(),'interface Windows: '+path)
require(any('Package: dolphin\n' in stanza and 'Status: install ok installed' in stanza
            and any(line.startswith('Version: ') and '+linuxbr' in line for line in stanza.splitlines())
            for stanza in status.split('\n\n')), 'Dolphin com cartoes Linux BR instalado')
packages = ['linuxbr-release', 'linuxbr-branding', 'linuxbr-desktop', 'linuxbr-sddm-theme', 'linuxbr-boot-theme', 'linuxbr-drive-manager', 'linuxbr-system', 'linuxbr-device-manager', 'linuxbr-file-properties']
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
    require(keyboard.get('XKBLAYOUT') == 'br' and keyboard.get('XKBMODEL') == 'pc105', 'teclado brasileiro ABNT2 com cedilha')
    require(yaml.safe_load(read('etc/calamares/modules/plymouthcfg.conf'))['plymouth_theme'] == 'linuxbr', 'tema Plymouth no destino Calamares')
    desktop_installer()
    require(not any('Package: linuxbr-server\n' in stanza and 'Status: install ok installed' in stanza
                    for stanza in status.split('\n\n')), 'mídia Desktop sem pacote de servidor')
    for path in ('usr/lib/systemd/system/linuxbr-initial-setup.service',
                 'usr/lib/linuxbr-system/initial_setup_service.py', 'usr/lib/linuxbr-system/initial_setup.py'):
        require((root / path).is_file(), 'configuração inicial disponível no destino: ' + path)
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

require((root/'usr/lib/linuxbr-system/daily_use.py').is_file(),'orientações de uso diário')
if args.mode=='live':
    require((root/'usr/share/calamares/lang/calamares_pt_BR.qm').is_file(),'tradução local do instalador')
    xorg=read('/etc/X11/xorg.conf.d/00-keyboard.conf')
    require('"XkbModel" "pc105"' in xorg and '"XkbLayout" "br"' in xorg,'ABNT2 no serviço de teclado')
print('PASS: integração de uso diário e teclado')

for path in ('usr/bin/timeshift', 'usr/bin/wrestool',
             'usr/lib/linuxbr-system/snapshot_service.py',
             'usr/lib/linuxbr-system/update_status.py',
             'usr/lib/linuxbr-system/function_icons.py',
             'usr/share/doc/linuxbr-system/README.md',
             'etc/apt/apt.conf.d/80linuxbr-recovery'):
    require((root/path).is_file(), 'integração 0.7: '+path)
require('## Histórico de versões' in read('usr/share/doc/linuxbr-system/README.md'), 'histórico de versões na imagem')
print('PASS: integração da versão 0.7')

for path in ('usr/bin/linuxbr-migration', 'usr/bin/linuxbr-maintenance', 'usr/bin/linuxbr-desktop-flows',
             'usr/lib/linuxbr-system/migration.py', 'usr/lib/linuxbr-system/migration_backend.py',
             'usr/lib/linuxbr-system/maintenance.py', 'usr/lib/linuxbr-system/protection_status.py',
             'usr/lib/linuxbr-system/storage_cleanup.py', 'usr/lib/linuxbr-system/troubleshooting.py',
             'usr/lib/linuxbr-system/desktopflows08.py', 'usr/lib/linuxbr-system/desktopflows08_backend.py',
             'usr/lib/linuxbr-system/store_transactions.py', 'usr/lib/linuxbr-system/windows_recipes.py',
             'usr/lib/linuxbr-file-properties/backend.py'):
    require((root/path).is_file(), 'integração 0.8: '+path)
require(bool(list((root/'usr/lib').glob('*/qt6/plugins/kf6/propertiesdialog/liblinuxbrfileproperties.so'))), 'plugin nativo das propriedades')
require(any(b'_ZN17KPropertiesDialog5applyEv' in library.read_bytes()
            for library in (root/'usr/lib').glob('*/libKF6KIOWidgets.so.6*')), 'KIO com Aplicar nativo nas propriedades')
print('PASS: integração da versão 0.8')
