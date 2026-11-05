#!/usr/bin/env python3
"""Reject conflicting file ownership before installing a local package set."""
import argparse
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


def check(directory):
    owners={};packages=sorted(Path(directory).glob('*.deb'))
    if not packages:raise ValueError('Nenhum pacote encontrado.')
    for package in packages:
        with subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(package)],stdout=subprocess.PIPE) as process:
            try:
                with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
                    for member in archive:
                        if member.isdir():continue
                        name=str(PurePosixPath(member.name))
                        if name in owners:
                            raise ValueError(f'Arquivo duplicado: {name}: {owners[name]} e {package.name}')
                        owners[name]=package.name
            except BaseException:
                process.kill();process.wait();raise
            if process.wait()!=0:raise ValueError(f'Não foi possível ler {package.name}.')
    print(f'PASS: {len(packages)} pacotes, {len(owners)} arquivos, sem propriedade duplicada.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    try:check(args.directory)
    except (OSError,ValueError,tarfile.TarError) as error:parser.exit(1,f'FAIL: {error}\n')
