"""Regenerate an installed GRUB menu with backup and rollback."""
import hashlib
import json
import os
from pathlib import Path
import sys
from boot_backend import MENU,STATE,atomic,run


def repair(request):
    if os.geteuid()!=0:raise PermissionError('Autenticação administrativa necessária.')
    if request.get('action')!='repair-menu':raise ValueError('Operação desconhecida.')
    if Path('/run/live/medium').exists():raise ValueError('Este comando atua somente no sistema instalado em execução.')
    if MENU.is_symlink() or not MENU.is_file():raise ValueError('Menu GRUB não disponível ou indireto.')
    old=MENU.read_bytes()
    if request.get('sha256') is not None and request['sha256']!=hashlib.sha256(old).hexdigest():raise ValueError('O menu mudou. Atualize a tela antes de continuar.')
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    import fcntl
    descriptor=os.open(STATE/'lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if MENU.read_bytes()!=old:raise ValueError('Outra operação alterou o menu.')
        atomic(STATE/'menu-before-repair.cfg',old)
        try:
            run('update-grub');run('grub-script-check',str(MENU))
            if b'linuxbr-options' not in MENU.read_bytes():raise RuntimeError('As entradas de recuperação não foram geradas.')
        except Exception:atomic(MENU,old);raise
    return dict(ok=True,backup=str(STATE/'menu-before-repair.cfg'))


if __name__=='__main__':
    try:print(json.dumps(repair(json.load(sys.stdin))))
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
