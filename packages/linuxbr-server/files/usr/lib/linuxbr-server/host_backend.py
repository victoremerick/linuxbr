"""Small authenticated host operations for the minimal server session."""
import grp
import json
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path


def restricted():
    choices=[part.split('=',1)[1] for part in Path('/proc/cmdline').read_text().split() if part.startswith('linuxbr.mode=')]
    return bool(choices and choices[-1] in {'safe','safe-network','safe-terminal','recovery'})


def run(argv, data=None):
    result=subprocess.run(argv,input=data,text=True,capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError(result.stderr.strip() or 'Não foi possível concluir a operação.')
    return result.stdout.strip()


def username(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}',value):
        raise ValueError('Use um nome de usuário com até 31 letras minúsculas, números, hífen ou sublinhado.')
    return value


def password(value):
    if not isinstance(value,str) or not 12<=len(value)<=256 or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Use uma senha com 12 a 256 caracteres, sem caracteres de controle.')
    return value


def state():
    administrators=set(grp.getgrnam('sudo').gr_mem)
    users=[dict(name=p.pw_name,full=p.pw_gecos.split(',')[0],home=p.pw_dir,admin=p.pw_name in administrators)
           for p in pwd.getpwall() if 1000<=p.pw_uid<65534 and p.pw_shell not in ('/usr/sbin/nologin','/bin/false')]
    timing=run(['timedatectl','show','--property=Timezone','--property=NTP','--property=NTPSynchronized'])
    return dict(hostname=run(['hostnamectl','--static']),users=users,time=dict(line.split('=',1) for line in timing.splitlines() if '=' in line),
                ssh_active=subprocess.run(['systemctl','is-active','--quiet','ssh.service']).returncode==0,
                ssh_installed=subprocess.run(['systemctl','cat','ssh.service'],capture_output=True).returncode==0,restricted=restricted())


def apply(request):
    if os.geteuid()!=0:raise PermissionError('A alteração exige autenticação administrativa.')
    action=request.get('action')
    if action=='hostname':
        name=request.get('hostname','')
        if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?',name):
            raise ValueError('Informe um nome de computador de 1 a 63 letras, números ou hífens.')
        run(['hostnamectl','set-hostname',name])
        if run(['hostnamectl','--static'])!=name:raise RuntimeError('O nome aplicado não corresponde ao solicitado.')
    elif action in ('create-user','password'):
        name=username(request.get('username'));secret=password(request.get('password'))
        if action=='create-user':
            try:pwd.getpwnam(name)
            except KeyError:pass
            else:raise ValueError('Já existe uma conta com esse nome.')
            full=request.get('full','')
            if not isinstance(full,str) or len(full)>100 or any(ord(c)<32 or c in ':,' for c in full):raise ValueError('Nome completo inválido.')
            if not isinstance(request.get('admin',False),bool):raise ValueError('Tipo de conta inválido.')
            run(['adduser','--disabled-password','--gecos',full,'--',name])
        else:
            account=pwd.getpwnam(name)
            if not 1000<=account.pw_uid<65534:raise ValueError('Selecione uma conta pessoal; contas de sistema são protegidas.')
        # Credentials travel only over the subprocess input pipe.
        run(['chpasswd'],name+':'+secret+'\n')
        if action=='create-user' and request.get('admin'):run(['usermod','-a','-G','sudo','--',name])
    elif action=='time':
        zone=request.get('timezone','');ntp=request.get('ntp')
        if not isinstance(zone,str) or zone not in run(['timedatectl','list-timezones']).splitlines():raise ValueError('Fuso horário inválido.')
        if not isinstance(ntp,bool):raise ValueError('Escolha a sincronização de horário.')
        limited=restricted()
        if limited and ntp:raise ValueError('A sincronização de horário pela rede está bloqueada neste modo. O ajuste manual continua disponível.')
        manual=request.get('manual','')
        if not ntp and manual:
            from datetime import datetime
            datetime.strptime(manual,'%Y-%m-%d %H:%M:%S')
        run(['timedatectl','set-timezone',zone])
        if not limited:run(['timedatectl','set-ntp','true' if ntp else 'false'])
        if not ntp and manual:
            run(['timedatectl','set-time',manual])
    elif action=='ssh':
        if restricted():raise ValueError('A administração remota está bloqueada neste modo. Volte à inicialização normal para alterar o SSH.')
        enabled=request.get('enabled')
        if not isinstance(enabled,bool):raise ValueError('Escolha habilitar ou desabilitar o SSH.')
        run(['systemctl','enable' if enabled else 'disable','--now','ssh.service'])
        actual=subprocess.run(['systemctl','is-active','--quiet','ssh.service']).returncode==0
        if actual!=enabled:raise RuntimeError('O estado do SSH não corresponde à alteração solicitada.')
    else:raise ValueError('Operação desconhecida.')
    return state()


if __name__=='__main__':
    try:
        payload=sys.stdin.buffer.read(8193)
        if len(payload)>8192:raise ValueError('Solicitação muito grande.')
        request=json.loads(payload)
        result=state() if request.get('action')=='state' else apply(request)
        print(json.dumps(dict(ok=True,data=result),ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));sys.exit(1)
