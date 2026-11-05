"""Environment preferences and narrowly named scheduled tasks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid
from store_sources import atomic_write


def config():return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))


def environment(scope):
    path=Path('/etc/environment') if scope=='system' else config()/'linuxbr/environment.json'
    raw=path.read_bytes() if path.exists() else b'';values={}
    if scope=='user':
        try:values=json.loads(raw) if raw else {}
        except ValueError:raise ValueError('O arquivo de variáveis do usuário não contém um objeto válido.') from None
    else:
        for line in raw.decode('utf-8').splitlines():
            match=re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$',line.strip())
            if match:
                tokens=shlex.split(match[2],comments=False);values[match[1]]=tokens[0] if len(tokens)==1 else match[2]
    if not isinstance(values,dict):raise ValueError('Configuração de variáveis inválida.')
    return dict(values=values,sha256=hashlib.sha256(raw).hexdigest(),path=str(path))


def checked_variables(values):
    if not isinstance(values,dict) or len(values)>512:raise ValueError('Lista de variáveis inválida.')
    for key,value in values.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',key) or not isinstance(value,str) or len(value)>8192 or any(c in value for c in '\r\n\x00'):raise ValueError('Nome ou valor de variável inválido.')
    return values


def save_environment(scope,values,expected):
    if scope not in ('user','system'):raise ValueError('Alcance inválido.')
    if scope=='system' and os.geteuid()!=0:raise PermissionError('Alterar variáveis do computador exige autorização administrativa.')
    current=environment(scope)
    if current['sha256']!=expected:raise ValueError('As variáveis foram alteradas por outro processo. Recarregue antes de aplicar.')
    checked_variables(values);path=Path(current['path'])
    if path.is_symlink():raise ValueError('O arquivo de variáveis não pode ser um link simbólico.')
    if scope=='user':
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);atomic_write(path,json.dumps(values,ensure_ascii=False,indent=2).encode(),0o600)
        hook=config()/'plasma-workspace/env/linuxbr-variables.sh';hook.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        atomic_write(hook,('#!/bin/sh\n'+''.join('export '+key+'='+shlex.quote(value)+'\n' for key,value in sorted(values.items()))).encode(),0o700)
    else:
        raw=path.read_bytes() if path.exists() else b''
        backup=Path('/var/backups/linuxbr-settings');backup.mkdir(parents=True,exist_ok=True,mode=0o700);destination=backup/('environment.'+expected+'.bak')
        if not destination.exists():
            with destination.open('xb') as stream:stream.write(raw)
            destination.chmod(0o600)
        comments=[line for line in raw.decode().splitlines() if not re.match(r'^\s*[A-Za-z_][A-Za-z0-9_]*=',line)]
        content='\n'.join(comments)+('\n' if comments else '')
        for key,value in sorted(values.items()):content+=key+'="'+value.replace('\\','\\\\').replace('"','\\"')+'"\n'
        atomic_write(path,content.encode())
    return dict(status='PASS',message='Variáveis salvas. As novas sessões receberão os valores. Abra uma nova sessão para aplicar a todos os aplicativos.')


def task_locations(scope):
    if scope=='system':return Path('/etc/systemd/system'),Path('/var/lib/linuxbr/tasks')
    if scope=='user':return config()/'systemd/user',Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'linuxbr/tasks'
    raise ValueError('Alcance inválido.')


def systemctl(scope,*args):
    return subprocess.run(['/usr/bin/systemctl',*(['--user'] if scope=='user' else []),*args],capture_output=True,text=True,timeout=30)


def unit_argument(value):
    if not isinstance(value,str) or any(c in value for c in '\r\n\x00'):raise ValueError('Argumento de tarefa inválido.')
    return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('%','%%').replace('$','$$')+'"'


def create_task(scope,name,argv,calendar):
    if scope=='system' and os.geteuid()!=0:raise PermissionError('Uma tarefa do computador exige autorização administrativa.')
    if not isinstance(name,str) or not 1<=len(name)<=160 or any(ord(c)<32 for c in name):raise ValueError('Nome de tarefa inválido.')
    if not isinstance(argv,list) or not argv or len(argv)>100 or not all(isinstance(a,str) and len(a)<=8192 for a in argv):raise ValueError('Comando inválido.')
    if not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file() or not os.access(argv[0],os.X_OK):raise ValueError('Selecione o caminho absoluto de um programa executável instalado.')
    if not isinstance(calendar,str) or not re.fullmatch(r'[A-Za-z0-9*: /,+.=-]{1,120}',calendar):raise ValueError('Agendamento inválido.')
    probe=subprocess.run(['/usr/bin/systemd-analyze','calendar',calendar],capture_output=True,text=True,timeout=5)
    if probe.returncode:raise ValueError('O agendamento não foi reconhecido pelo sistema.')
    units,records=task_locations(scope);units.mkdir(parents=True,exist_ok=True);records.mkdir(parents=True,exist_ok=True,mode=0o755 if scope=='system' else 0o700)
    identifier=str(uuid.uuid4());prefix='linuxbr-task-'+identifier;description=name.replace('%','%%')
    service='[Unit]\nDescription='+description+'\n\n[Service]\nType=oneshot\nExecStart='+' '.join(unit_argument(a) for a in argv)+'\n'
    timer='[Unit]\nDescription='+description+'\n\n[Timer]\nOnCalendar='+calendar+'\nPersistent=true\nUnit='+prefix+'.service\n\n[Install]\nWantedBy=timers.target\n'
    paths=[units/(prefix+'.service'),units/(prefix+'.timer')]
    for path,text in zip(paths,[service,timer]):
        with path.open('x') as stream:stream.write(text)
    record=dict(id=identifier,name=name,argv=argv,calendar=calendar,scope=scope)
    target=records/(identifier+'.json')
    try:
        reload=systemctl(scope,'daemon-reload')
        if reload.returncode:raise ValueError(reload.stderr.strip())
        result=systemctl(scope,'enable','--now',prefix+'.timer')
        if result.returncode:raise ValueError(result.stderr.strip())
        atomic_write(target,json.dumps(record,ensure_ascii=False).encode());target.chmod(0o644 if scope=='system' else 0o600)
    except Exception:
        systemctl(scope,'disable','--now',prefix+'.timer')
        for path in paths:path.unlink(missing_ok=True)
        systemctl(scope,'daemon-reload');raise
    return record


def tasks(scope):
    _,records=task_locations(scope);rows=[]
    for path in sorted(records.glob('*.json')):
        try:
            identifier=str(uuid.UUID(path.stem));value=json.loads(path.read_text())
            if value['id']!=identifier or value['scope']!=scope:continue
            name='linuxbr-task-'+identifier+'.timer';enabled=systemctl(scope,'is-enabled',name)
            value['enabled']=enabled.stdout.strip();next_time=systemctl(scope,'show',name,'--property=NextElapseUSecRealtime','--value');value['next']=next_time.stdout.strip();rows.append(value)
        except (OSError,ValueError,KeyError):continue
    return rows


def task_action(scope,identifier,action):
    if scope=='system' and os.geteuid()!=0:raise PermissionError('Esta tarefa exige autorização administrativa.')
    identifier=str(uuid.UUID(identifier));units,records=task_locations(scope);path=records/(identifier+'.json')
    if path.is_symlink() or not path.is_file():raise ValueError('Tarefa não encontrada.')
    value=json.loads(path.read_text())
    if value['id']!=identifier or value['scope']!=scope:raise ValueError('Registro de tarefa inválido.')
    prefix='linuxbr-task-'+identifier
    if action=='run':result=systemctl(scope,'start','--no-block',prefix+'.service')
    elif action=='enable':result=systemctl(scope,'enable','--now',prefix+'.timer')
    elif action=='disable':result=systemctl(scope,'disable','--now',prefix+'.timer')
    elif action=='remove':
        result=systemctl(scope,'disable','--now',prefix+'.timer')
        if result.returncode:raise ValueError(result.stderr)
        for suffix in ('.service','.timer'):
            target=units/(prefix+suffix)
            if target.is_symlink():raise ValueError('Unidade inválida.')
            target.unlink(missing_ok=True)
        path.unlink();result=systemctl(scope,'daemon-reload')
    else:raise ValueError('Ação inválida.')
    if result.returncode:raise ValueError(result.stderr.strip())
    return dict(status='PASS',message='Solicitação aplicada ao agendador. Uma execução iniciada pode continuar até concluir.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:raise SystemExit(2)
    try:
        raw=sys.stdin.buffer.read(131073)
        if len(raw)>131072:raise ValueError('Pedido muito grande.')
        request=json.loads(raw);action=request['action'];scope=request['scope']
        if scope=='user' and os.geteuid()==0:raise ValueError('Abra tarefas pessoais na conta normal.')
        if action=='environment':result=save_environment(scope,request['values'],request['sha256'])
        elif action=='create-task':result=create_task(scope,request['name'],request['argv'],request['calendar'])
        elif action=='task':result=task_action(scope,request['id'],request['operation'])
        else:raise ValueError('Ação desconhecida.')
        print(json.dumps(result,ensure_ascii=False))
    except Exception as error:print(str(error),file=sys.stderr);raise SystemExit(1)
