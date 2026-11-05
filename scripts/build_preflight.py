#!/usr/bin/env python3
"""Check available workspace space before starting an ISO build."""
import argparse
import os
from pathlib import Path
import shutil

GIB = 1024 ** 3


def check(path, minimum_gib=32):
    value = str(minimum_gib)
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 1024:
        raise ValueError('O mínimo de espaço precisa ser um número inteiro entre 1 e 1024 GiB.')
    directory = Path(path).resolve(strict=True)
    free = shutil.disk_usage(directory).free
    minimum = int(value) * GIB
    if free < minimum:
        raise ValueError(f'Espaço insuficiente para compilar: {free/GIB:.1f} GiB livres em {directory}; '
                         f'mínimo exigido: {int(value)} GiB. Libere espaço ou use outro volume antes de tentar novamente.')
    return dict(path=str(directory), free_bytes=free, minimum_bytes=minimum)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=Path.cwd())
    parser.add_argument('--minimum-gib', default=os.environ.get('LINUXBR_MIN_BUILD_FREE_GIB', '32'))
    args = parser.parse_args()
    try:
        result = check(args.path, args.minimum_gib)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error)+'\n')
    print(f'Espaço para compilação: {result["free_bytes"]/GIB:.1f} GiB livres; '
          f'mínimo: {result["minimum_bytes"]/GIB:.0f} GiB.')


if __name__ == '__main__':
    main()
