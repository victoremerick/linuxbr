"""Rebuild the Plasma application catalog with its menu definition present."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def catalog_environment(source=None, home=None):
    env = dict(os.environ if source is None else source)
    home = Path.home() if home is None else Path(home)
    env.setdefault('XDG_MENU_PREFIX', 'plasma-')
    if not env['XDG_MENU_PREFIX'] or '/' in env['XDG_MENU_PREFIX']:
        raise ValueError('Prefixo do menu inválido; o catálogo foi preservado.')
    directories = env.get('XDG_CONFIG_DIRS', '/etc/xdg').split(':')
    directories.insert(0, env.get('XDG_CONFIG_HOME', str(home / '.config')))
    menu = env['XDG_MENU_PREFIX'] + 'applications.menu'
    if not any((Path(d) / 'menus' / menu).is_file() for d in directories if d):
        raise ValueError('Definição do menu não encontrada; o catálogo foi preservado.')
    data = env.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')
    for directory in [str(home / '.local/share/flatpak/exports/share'),
                      '/var/lib/flatpak/exports/share']:
        if directory not in data:
            data.append(directory)
    env['XDG_DATA_DIRS'] = ':'.join(data)
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conferir ou reconstruir o catálogo de aplicativos do Plasma.')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('Execute na conta da área de trabalho, sem sudo.')
        env = catalog_environment()
        if args.check:
            print('Definição do menu Plasma disponível para reconstrução do catálogo.')
            return 0
        subprocess.run(['kbuildsycoca6', '--noincremental'], env=env, check=True, timeout=45)
        print('Catálogo de aplicativos atualizado. Os atalhos podem ser abertos novamente.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
