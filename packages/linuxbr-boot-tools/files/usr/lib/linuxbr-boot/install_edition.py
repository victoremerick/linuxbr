"""Finalize a selected edition inside the installer's mounted target."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

DESKTOP_PACKAGES={'linuxbr-desktop-edition','linuxbr-desktop','linuxbr-system','linuxbr-drive-manager',
 'linuxbr-device-manager','linuxbr-file-properties','linuxbr-sddm-theme','task-kde-desktop',
 'kde-plasma-desktop','kde-standard','kde-full','plasma-desktop','plasma-workspace',
 'plasma-workspace-wayland','kwin-wayland','kwin-x11','systemsettings','plasma-discover',
 'plasma-discover-backend-flatpak','plasma-discover-backend-fwupd','plasma-nm','plasma-pa',
 'plasma-integration','plasma-browser-integration','plasma-dataengines-addons','plasma-widgets-addons',
 'kdeconnect','powerdevil','bluedevil','print-manager','skanpage','kcalc','kate','kolourpaint',
 'gwenview','okular','ark','vlc','firefox-esr','firefox-esr-l10n-pt-br','chromium','chromium-sandbox',
 'chromium-l10n','libreoffice-writer','libreoffice-calc','libreoffice-impress','libreoffice-draw',
 'libreoffice-qt6','libreoffice-help-pt-br','kup-backup','filelight','kde-spectacle','dolphin'}
PROTECTED={'linuxbr-release','linuxbr-server','linuxbr-boot-tools','linuxbr-boot-theme','linuxbr-branding',
 'apt','dpkg','sudo','polkitd','sddm','network-manager','firewalld','bash','coreutils','initramfs-tools','systemd','libc6'}


def run(argv):
    result=subprocess.run(argv,env={**os.environ,'LC_ALL':'C.UTF-8','DEBIAN_FRONTEND':'noninteractive'},text=True,capture_output=True,timeout=600)
    if result.returncode:raise RuntimeError(result.stderr.strip() or result.stdout[-3000:])
    return result.stdout


def configure(selected):
    if selected not in ('desktop','server'):raise ValueError('Edição desconhecida.')
    if os.geteuid()!=0:raise PermissionError('A configuração da edição exige autenticação administrativa.')
    if not Path('/var/lib/linuxbr/installer-edition-authorized').is_file():raise ValueError('Esta ação só pode ser executada pelo instalador no sistema de destino.')
    installed={}
    for line in run(['dpkg-query','-W','-f=${binary:Package}\t${db:Status-Status}\t${Essential}\n']).splitlines():
        parts=line.split('\t')
        if len(parts)==3 and parts[1]=='installed':installed[parts[0].split(':')[0]]=parts[2]=='yes'
    if selected=='server' and 'linuxbr-server' not in installed:raise ValueError('O pacote da edição Servidor não está disponível na mídia.')
    remove=sorted(DESKTOP_PACKAGES.intersection(installed) if selected=='server' else {'linuxbr-server'}.intersection(installed))
    protected=PROTECTED if selected=='server' else PROTECTED-{'linuxbr-server'}
    protected|={name for name,essential in installed.items() if essential}
    plan=run(['apt-get','-s','remove','--',*remove]) if remove else ''
    removed=set(re.findall(r'^Remv ([a-z0-9][a-z0-9+.:\-]*)',plan,re.M))
    if any(name.split(':')[0] in protected or name.startswith(('linux-image','grub','libpam')) for name in removed):
        raise ValueError('A seleção afetaria componentes necessários para iniciar ou autenticar no sistema.')
    report=Path('/var/lib/linuxbr/installation');report.mkdir(parents=True,exist_ok=True)
    (report/'edition-plan.txt').write_text(plan)
    if remove:run(['apt-get','-y','remove','--',*remove])
    edition=Path('/etc/linuxbr/edition');edition.parent.mkdir(parents=True,exist_ok=True);edition.write_text(selected+'\n')
    for config in [Path('/etc/default/grub'),*Path('/etc/default/grub.d').glob('*.cfg')]:
        if config.is_file():
            raw=config.read_text();clean=re.sub(r'\blinuxbr\.(?:edition|mode)=[A-Za-z-]+\s*|\bsystemd.unit=linuxbr-safe.target\s*','',raw)
            if clean!=raw:config.write_text(clean)
    run(['update-grub'])
    (report/'edition.json').write_text(json.dumps(dict(edition=selected,removed=sorted(removed)),ensure_ascii=False,indent=2)+'\n')
    Path('/var/lib/linuxbr/installer-edition-authorized').unlink()
    return dict(edition=selected,removed=sorted(removed))


if __name__=='__main__':
    try:print(json.dumps(configure(sys.argv[1]),ensure_ascii=False))
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
