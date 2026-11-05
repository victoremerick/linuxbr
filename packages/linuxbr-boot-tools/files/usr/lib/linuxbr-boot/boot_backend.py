"""Authenticated, reversible GRUB selection without disk or partition writes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from grub_modes import MODES

CONFIG=Path('/etc/default/grub.d/91-linuxbr-options.cfg')
MENU=Path('/boot/grub/grub.cfg')
ENV=Path('/boot/grub/grubenv')
STATE=Path('/var/lib/linuxbr/boot')


def run(*argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=120)
    if result.returncode:raise RuntimeError((result.stderr or result.stdout)[-4000:] or 'Operação recusada.')
    return result.stdout


def entry(mode):
    if mode not in MODES:raise ValueError('Modo de inicialização inválido.')
    return 'linuxbr-options>linuxbr-'+mode


def environment():
    if not ENV.is_file():return {}
    return dict(line.split('=',1) for line in run('grub-editenv',str(ENV),'list').splitlines() if '=' in line)


def state():
    text=MENU.read_text() if MENU.is_file() else ''
    configured=CONFIG.read_text() if CONFIG.is_file() else ''
    timeout=re.search(r'^GRUB_TIMEOUT=(\d+)$',configured,re.M)
    selected=re.search(r"^GRUB_DEFAULT='linuxbr-options>linuxbr-([a-z-]+)'$",configured,re.M)
    values=environment()
    return dict(available=all('--id=linuxbr-'+name in text for name in MODES),
                current=Path('/proc/cmdline').read_text().strip(),default=selected.group(1) if selected else None,
                timeout=int(timeout.group(1)) if timeout else None,next=values.get('next_entry',''),
                config_sha256=hashlib.sha256(configured.encode()).hexdigest(),live=Path('/run/live/medium').exists())


def atomic(path,content,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as handle:
            os.fchmod(handle.fileno(),mode);handle.write(content);handle.flush();os.fsync(handle.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def configure(request):
    if os.geteuid()!=0:raise PermissionError('Autenticação administrativa necessária.')
    action=request.get('action');selected=request.get('mode','normal');identifier=entry(selected)
    if action not in {'once','persistent','cancel','restore'}:raise ValueError('Ação inválida.')
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor=os.open(STATE/'lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        current=state()
        if current['live']:raise ValueError('Na mídia live, escolha o modo no menu da própria mídia.')
        if not current['available']:raise ValueError('As entradas avançadas ainda não estão disponíveis neste carregador.')
        if CONFIG.is_symlink() or MENU.is_symlink():raise ValueError('Configuração indireta não suportada.')
        if action=='cancel':
            if current['next'].startswith('linuxbr-options>linuxbr-'):
                run('grub-editenv',str(ENV),'unset','next_entry')
            return state()
        if action=='once':
            if current['next'] and not current['next'].startswith('linuxbr-options>linuxbr-'):
                raise ValueError('Outro sistema já está selecionado para a próxima inicialização.')
            run('grub-editenv',str(ENV),'set','next_entry='+identifier)
            if environment().get('next_entry')!=identifier:raise RuntimeError('Seleção temporária não foi confirmada.')
            return state()
        if request.get('expected_sha256')!=current['config_sha256']:
            raise ValueError('A configuração mudou. Atualize a tela antes de salvar.')
        before=CONFIG.read_bytes() if CONFIG.exists() else None
        previous=STATE/'previous.json'
        if action=='restore':
            backup=json.loads(previous.read_text());content=backup['content']
            if content is not None and (not isinstance(content,str) or len(content)>8192):raise ValueError('Backup inválido.')
        else:
            seconds=request.get('timeout')
            if type(seconds) is not int or not 3<=seconds<=120:raise ValueError('Use um tempo de menu entre 3 e 120 segundos.')
            content="GRUB_TIMEOUT_STYLE=menu\nGRUB_TIMEOUT="+str(seconds)+"\nGRUB_DEFAULT='"+identifier+"'\n"
        old_menu=MENU.read_bytes()
        atomic(previous,json.dumps(dict(content=None if before is None else before.decode())).encode())
        try:
            if content is None:CONFIG.unlink(missing_ok=True)
            else:atomic(CONFIG,content.encode(),0o644)
            run('update-grub');run('grub-script-check',str(MENU))
            if not state()['available']:raise RuntimeError('Entradas avançadas ausentes após atualização.')
        except Exception:
            if before is None:CONFIG.unlink(missing_ok=True)
            else:atomic(CONFIG,before,0o644)
            atomic(MENU,old_menu,0o600)
            raise
        return state()


def consume():
    if os.geteuid()!=0:raise PermissionError('Autenticação administrativa necessária.')
    # Some filesystems prevent GRUB from clearing its environment. Clear only our selection.
    if environment().get('next_entry','').startswith('linuxbr-options>linuxbr-'):
        run('grub-editenv',str(ENV),'unset','next_entry')


if __name__=='__main__':
    try:
        result=consume() if sys.argv[1:]==['--consume'] else state() if sys.argv[1:]==['--status'] else configure(json.load(sys.stdin))
        print(json.dumps(result,ensure_ascii=False))
    except Exception as error:
        print(str(error),file=sys.stderr);sys.exit(1)
