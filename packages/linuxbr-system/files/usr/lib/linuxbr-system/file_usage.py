"""List visible processes using a local item or its mounted filesystem."""
import argparse
from pathlib import Path
import re
import subprocess


def visible_processes(path):
    path = Path(path).resolve(strict=True)
    # Match all processes on a volume only when the item is itself a mount point.
    mount = subprocess.run(['/usr/bin/findmnt', '--noheadings', '--mountpoint', str(path)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    args = ['-m', '-M'] if mount.returncode == 0 else []
    usage = subprocess.run(['/usr/bin/fuser', '-I', *args, str(path)], capture_output=True,
                           text=True, timeout=10)
    if usage.returncode not in (0, 1):
        raise OSError('Não foi possível consultar os processos.')
    pids = {int(value) for value in usage.stdout.split() if re.fullmatch(r'[0-9]+', value)}
    records = []
    for pid in sorted(pids):
        try:
            name = (Path('/proc') / str(pid) / 'comm').read_text(errors='replace')
            name = ''.join(char for char in name.strip() if char.isprintable())
        except OSError:
            name = ''
        records.append((pid, name or 'Nome indisponível'))
    return mount.returncode == 0, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('item')
    args = parser.parse_args()
    try:
        volume, processes = visible_processes(args.item)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Consulta não concluída. {error}')
        return 1
    print('Escopo: unidade montada.' if volume else 'Escopo: arquivo ou pasta selecionada.')
    if processes:
        print('PID       Processo')
        for pid, name in processes:
            print(f'{pid:<9} {name}')
    else:
        print('Nenhum processo visível foi encontrado.')
    print('Sua conta pode não ter permissão para consultar todos os processos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
