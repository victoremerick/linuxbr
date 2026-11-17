#!/usr/bin/env python3
"""Check GRUB in the squashfs copied to disk by Calamares."""

import argparse
from pathlib import Path
import subprocess


REQUIRED = {
    'grub2-common': ('usr/sbin/grub-install',),
    'grub-efi-amd64-bin': ('usr/lib/grub/x86_64-efi/modinfo.sh', 'usr/lib/grub/x86_64-efi/normal.mod'),
    'grub-pc-bin': ('usr/lib/grub/i386-pc/modinfo.sh', 'usr/lib/grub/i386-pc/normal.mod'),
    'grub-efi-amd64-signed': ('usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed',),
    'shim-signed': ('usr/lib/shim/shimx64.efi.signed',),
    'efibootmgr': ('usr/bin/efibootmgr',),
}


def missing(image):
    failures = []
    for package, paths in REQUIRED.items():
        for path in paths:
            check = subprocess.run(['unsquashfs', '-cat', str(image), path],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if check.returncode:
                failures.append(f'/{path} ({package})')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('squashfs', type=Path)
    args = parser.parse_args()
    if not args.squashfs.is_file():
        parser.exit(1, f'FAIL: squashfs da sessão Live ausente: {args.squashfs}\n')
    failures = missing(args.squashfs)
    if failures:
        parser.exit(1, 'FAIL: arquivos necessários para instalar o GRUB ausentes no squashfs:\n'
                    + '\n'.join(failures) + '\n')
    print('PASS: módulos BIOS/UEFI do GRUB, cadeia EFI assinada e ferramentas no squashfs da instalação.')


if __name__ == '__main__':
    main()
