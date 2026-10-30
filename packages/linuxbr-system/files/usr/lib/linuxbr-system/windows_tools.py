"""Optional Windows tools installed in the current account only."""
import os
import json
import subprocess
import sys

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='scan' and os.geteuid()!=0:
        from windows_runner import discover_programs
        try:
            print(json.dumps(discover_programs(sys.argv[2]),ensure_ascii=False))
        except (OSError,ValueError,TypeError) as error:
            print(str(error),file=sys.stderr);raise SystemExit(1)
        raise SystemExit(0)
    if os.geteuid()==0 or sys.argv[1:]!=['bottles']:
        raise SystemExit('Abra Bottles pela ferramenta Programas Windows e jogos, sem sudo.')
    print('Instalando Bottles para este usuário, a partir do Flathub.\n'
          'O download inclui os componentes necessários e pode ocupar vários GB.',flush=True)
    try:
        subprocess.run(['flatpak','remote-add','--user','--if-not-exists','flathub',
                        'https://dl.flathub.org/repo/flathub.flatpakrepo'],check=True)
        subprocess.run(['flatpak','install','--user','--noninteractive','flathub','com.usebottles.bottles'],check=True)
    except (OSError,subprocess.CalledProcessError):
        raise SystemExit('Não foi possível instalar Bottles. Confira a conexão e o espaço livre; depois tente novamente.')
    print('Bottles instalado. Abrindo…',flush=True)
    subprocess.run(['flatpak','run','com.usebottles.bottles'],check=False)
