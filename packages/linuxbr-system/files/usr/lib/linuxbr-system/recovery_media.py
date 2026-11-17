"""Prepare a verified Linux BR image and offline guide on an existing Ventoy drive."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

IMAGE = re.compile(r'linuxbr[-a-zA-Z0-9_.~+]{0,140}\.iso', re.I)
SHA256 = re.compile(r'[a-fA-F0-9]{64}')


def ventoy_volumes(disks):
    result = []
    for disk in disks:
        if disk['type'] != 'disk' or disk.get('ro') or not (disk.get('rm') or disk.get('tran') == 'usb'):
            continue
        partitions = disk.get('children', [])
        ready = any(item.get('partn') == 2 and item.get('label') == 'VTOYEFI'
                    and item.get('fstype') == 'vfat' for item in partitions)
        if not ready:
            continue
        for volume in partitions:
            if volume.get('partn') != 1 or volume.get('ro'):
                continue
            for mount in volume.get('mountpoints') or []:
                if mount and Path(mount).is_absolute() and mount != '/' and not mount.startswith(('/boot', '/home')):
                    result.append((mount, volume['path']))
    return result


def destinations():
    try:
        lines = subprocess.check_output(['/usr/bin/lsblk', '--json', '--paths', '--output',
                                         'PATH,TYPE,FSTYPE,LABEL,MOUNTPOINTS,TRAN,RM,PARTN,RO'],
                                        timeout=6, text=True, errors='replace', stderr=subprocess.DEVNULL)
        return ventoy_volumes(json.loads(lines)['blockdevices'])
    except (OSError, subprocess.SubprocessError):
        return []


def edition_release():
    lines = Path('/etc/os-release').read_text(encoding='utf-8').splitlines()
    versions = [line.split('=', 1)[1].strip('"') for line in lines if line.startswith('PRETTY_NAME=')]
    return versions[0][:120] if versions else 'Linux BR'


def prepare(image, expected, drive):
    if not IMAGE.fullmatch(image.name) or not SHA256.fullmatch(expected):
        raise ValueError('Selecione uma ISO do Linux BR e informe o SHA-256 publicado na versão.')
    mount = drive.resolve(strict=True)
    if str(mount) not in dict(destinations()) or not os.path.ismount(mount) or (mount / '.ventoyignore').exists():
        raise ValueError('Escolha a partição principal montada de um pendrive Ventoy disponível para boot.')
    expected = expected.lower()
    release = edition_release()
    with image.open('rb') as source:
        source.seek(16 * 2048 + 1)
        if source.read(5) != b'CD001':
            raise ValueError('O arquivo selecionado não é uma imagem ISO 9660.')
        size = os.fstat(source.fileno()).st_size
        if shutil.disk_usage(mount).free < size + 2 * 1024 ** 2:
            raise ValueError('O pendrive não tem espaço livre para esta imagem.')
        source.seek(0)
        destination = Path(tempfile.mkdtemp(prefix='LinuxBR-Recuperacao-', dir=mount))
        temporary = destination / (image.name + '.parcial')
        guide = destination / 'LEIA-ME.txt'
        checksum = destination / 'SHA256SUMS'
        try:
            with temporary.open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 ** 2)
                target.flush()
                os.fsync(target.fileno())
            with temporary.open('rb') as target:
                if hashlib.file_digest(target, 'sha256').hexdigest() != expected:
                    raise ValueError('O SHA-256 da cópia não corresponde ao publicado para a imagem.')
            guide.write_text(
                f'Linux BR · mídia de recuperação\nPreparada em {datetime.now():%d/%m/%Y %H:%M}\n'
                f'Sistema de origem: {release}\nImagem de recuperação: {image.name}\n\n'
                '1. Ejete o pendrive ao terminar e conecte-o ao equipamento desligado.\n'
                '2. No menu de boot do equipamento, escolha o pendrive no mesmo modo BIOS ou UEFI da instalação.\n'
                '3. No menu Ventoy, escolha a imagem da pasta LinuxBR-Recuperacao.\n'
                '4. Inicie em modo Live. Abra Recuperação para acessar o terminal, os discos, as cópias '
                'e os pontos de restauração.\n'
                '5. Para reinstalar, primeiro copie e confira os arquivos em outro disco.\n',
                encoding='utf-8')
            checksum.write_text(f'{expected}  {image.name}\n', encoding='ascii')
            temporary.rename(destination / image.name)
            return destination
        except (OSError, ValueError):
            for path in (temporary, guide, checksum):
                path.unlink(missing_ok=True)
            destination.rmdir()
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('drive', type=Path)
    args = parser.parse_args()
    try:
        folder = prepare(args.image, args.sha256, args.drive)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'{error}\n')
    print(f'Mídia preparada em {folder}\nEjete o pendrive depois de conferir os arquivos.')


if __name__ == '__main__':
    main()
