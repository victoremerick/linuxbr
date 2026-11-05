#!/usr/bin/env python3
"""Build an immutable, signed APT repository from reviewed local packages."""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import gzip
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit


def run(*argv, **kwargs):
    return subprocess.check_output(argv, **kwargs)


def build(packages, output, fingerprint, base_url=None):
    if not re.fullmatch(r'[A-Fa-f0-9]{40,64}', fingerprint):
        raise ValueError('Informe a impressão digital completa da chave de assinatura.')
    if base_url:
        url=urlsplit(base_url)
        if (url.scheme!='https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in base_url)):
            raise ValueError('Use um endereço HTTPS sem credenciais, consulta ou fragmento.')
    if output.exists():raise ValueError('O diretório de saída já existe; escolha outro para preservar a publicação anterior.')
    inputs=[];identities=set()
    for deb in sorted(packages.glob('*.deb')):
        fields=run('dpkg-deb','-f',str(deb),'Package','Version','Architecture',text=True)
        metadata=dict(line.split(': ',1) for line in fields.splitlines())
        name=metadata['Package'];version=metadata['Version'];arch=metadata['Architecture']
        if not (name.startswith('linuxbr-') or name in ('dolphin','dolphin-data','libdolphinvcs6',
                'kio6','libkf6kiocore6','libkf6kiogui6','libkf6kiowidgets6','libkf6kiofilewidgets6')):
            raise ValueError('Pacote fora do conjunto Linux BR: '+name)
        if arch not in ('amd64','all'):raise ValueError('Arquitetura não suportada: '+arch)
        identity=(name,version,arch)
        if identity in identities:raise ValueError('Pacote duplicado: '+name)
        identities.add(identity);inputs.append((deb,name,version,arch))
    if not inputs:raise ValueError('Nenhum pacote DEB encontrado.')
    output.mkdir(parents=True)
    pool=output/'pool/main';pool.mkdir(parents=True)
    for deb,name,version,arch in inputs:
        filename=f'{name}_{version}_{arch}.deb'
        if '/' in filename or '\n' in filename:raise ValueError('Nome de pacote inválido.')
        shutil.copyfile(deb,pool/filename)
    index=output/'dists/trixie/main/binary-amd64';index.mkdir(parents=True)
    content=run('dpkg-scanpackages','--multiversion','pool',cwd=output)
    (index/'Packages').write_bytes(content)
    (index/'Packages.gz').write_bytes(gzip.compress(content,mtime=0))
    now=datetime.now(timezone.utc)
    release=('Origin: LinuxBR\nLabel: Linux BR\nSuite: trixie\nCodename: trixie\n'
             'Architectures: amd64\nComponents: main\nDescription: Atualizações Linux BR\n'
             f'Date: {format_datetime(now, usegmt=True)}\n'
             f'Valid-Until: {format_datetime(now+timedelta(days=14), usegmt=True)}\nSHA256:\n')
    distribution=output/'dists/trixie'
    for path in sorted(index.iterdir()):
        data=path.read_bytes()
        release+=f' {hashlib.sha256(data).hexdigest()} {len(data)} {path.relative_to(distribution)}\n'
    (distribution/'Release').write_text(release)
    for args in (('--clearsign','--output',str(distribution/'InRelease')),
                 ('--armor','--detach-sign','--output',str(distribution/'Release.gpg'))):
        run('gpg','--batch','--local-user',fingerprint,*args,str(distribution/'Release'))
    public=run('gpg','--batch','--export',fingerprint)
    if not public:raise ValueError('A chave pública não foi encontrada.')
    (output/'linuxbr-archive-keyring.gpg').write_bytes(public)
    if base_url:
        (output/'linuxbr.sources').write_text('Types: deb\nURIs: '+base_url.rstrip('/')+'\n'
            'Suites: trixie\nComponents: main\nArchitectures: amd64\n'
            'Signed-By: /usr/share/keyrings/linuxbr-archive-keyring.gpg\n')
    (output/'linuxbr.pref').write_text('Package: linuxbr-* dolphin dolphin-data libdolphinvcs6 kio6 libkf6kiocore6 libkf6kiogui6 libkf6kiowidgets6 libkf6kiofilewidgets6\n'
                                     'Pin: release o=LinuxBR\nPin-Priority: 600\n')
    return len(inputs)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Preparar repositório APT assinado, sem publicar ou alterar as fontes do sistema.')
    parser.add_argument('--packages',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fingerprint',required=True)
    parser.add_argument('--base-url')
    args=parser.parse_args()
    try:print(f'{build(args.packages,args.output,args.fingerprint,args.base_url)} pacotes publicados no diretório local {args.output}.')
    except (ValueError,OSError,subprocess.CalledProcessError) as error:parser.exit(1,str(error)+'\n')
