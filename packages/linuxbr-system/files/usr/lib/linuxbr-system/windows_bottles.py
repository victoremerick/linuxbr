"""Launch a Bottles application as an individual desktop window."""
import argparse
import os
import subprocess


APP_IDS = ('com.usebottles.bottles', 'com.usebottles.bottles.Devel')


def command(app_id, bottle, program=None, prepare=False):
    if app_id not in APP_IDS:
        raise ValueError('Edição do Bottles inválida.')
    for value in (bottle, program):
        if value is not None and (not value.strip() or len(value) > 200 or
                                  any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError('Nome do ambiente ou programa inválido.')
    base = ['flatpak', 'run', '--socket=x11', '--nosocket=wayland',
            '--env=XDG_SESSION_TYPE=x11', '--command=bottles-cli', app_id]
    if prepare:
        return base + ['edit', '-b', bottle, '--params', 'virtual_desktop:false']
    if program is None:
        raise ValueError('Escolha o programa registrado no Bottles.')
    return base + ['run', '-b', bottle, '-p', program]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Integração de janelas do Bottles com a área de trabalho.')
    parser.add_argument('--app-id', choices=APP_IDS, default=APP_IDS[0])
    parser.add_argument('--bottle', required=True)
    parser.add_argument('--program')
    parser.add_argument('--prepare', action='store_true',
                        help='Desativa a área de trabalho virtual. Feche os programas desse ambiente antes.')
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('Abra o programa pela sua conta, sem sudo.')
        if not os.environ.get('DISPLAY'):
            raise ValueError('A sessão precisa disponibilizar X11/Xwayland.')
        return subprocess.run(command(args.app_id, args.bottle, args.program, args.prepare),
                              check=False).returncode
    except (OSError, ValueError) as error:
        print(str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
