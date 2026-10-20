"""Privileged entry point: only allowlisted Debian hardware packages, never arbitrary commands."""
import os
from pathlib import Path
import subprocess
import sys
# Python is invoked with -I. Import only the root-owned installed directory.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hardware import FIRMWARE_PACKAGES, B43_PACKAGES, discover, resolve_candidates, firmware_catalog
from proprietary import NVIDIA_PACKAGES, nvidia_options

def install_args(args):
    if args==['--refresh']:
        return ['/usr/bin/apt-get','-o','APT::Update::Error-Mode=any','update']
    if len(args)!=1 or args[0] not in {*FIRMWARE_PACKAGES,'linux-image-amd64','nvidia-detect',*NVIDIA_PACKAGES}:
        raise ValueError('Escolha exatamente um pacote de hardware permitido.')
    return ['/usr/bin/apt-get','--no-remove','install','-y',args[0]]

def main(args):
    command=install_args(args)
    if os.geteuid()!=0:raise ValueError('É necessária autorização administrativa pelo polkit.')
    identity=Path('/etc/os-release').read_text()
    if not any(line in ('ID=debian','ID="debian"','ID=linuxbr','ID="linuxbr"') for line in identity.splitlines()):
        raise ValueError('Instalação suportada somente no Linux BR/Debian.')
    # No repository changes, shell interpolation or user-controlled environment.
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LC_ALL':'C.UTF-8','DEBIAN_FRONTEND':'noninteractive'}
    if args[0] in B43_PACKAGES:
        os.environ.clear();os.environ.update(env)
        rows,_=discover()
        resolve_candidates(rows)
        option=next(r for r in firmware_catalog(rows) if r['package']==args[0])
        if not option['related'] or not option['action']:
            raise ValueError('Instalação Broadcom não permitida: ' + option['status'])
    if args[0] in NVIDIA_PACKAGES:
        os.environ.clear();os.environ.update(env)
        rows,_=discover()
        option=next((r for r in nvidia_options(rows) if r['package']==args[0]),None)
        if not option or not option.get('action'):
            raise ValueError(option['status'] if option else 'Driver não recomendado para este hardware.')
        command += option['prerequisites']
    return subprocess.call(command,env=env,cwd='/')

if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1:]))
    except (ValueError,OSError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
