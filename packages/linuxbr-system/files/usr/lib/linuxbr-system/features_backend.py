"""Optional component plans, guarded service changes and reversible records."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

FEATURES={
 'windows':dict(name='Compatibilidade Windows',icon='application-x-ms-dos-executable',packages=['wine','wine64','winetricks'],units=[],impact='Remover o Wine impede abrir programas Windows. Ambientes e arquivos pessoais são preservados.'),
 'virtualization':dict(name='Máquinas virtuais',icon='computer',packages=['libvirt-daemon-system','libvirt-clients','libvirt-daemon-driver-qemu','qemu-system-x86','qemu-system-modules-spice','qemu-utils','qemu-block-extra','virt-manager','virtinst','virt-viewer','ovmf','swtpm','swtpm-tools'],units=['libvirtd.service','libvirtd.socket','libvirtd-ro.socket','libvirtd-admin.socket','virtlogd.socket','virtlockd.socket'],impact='Desativar impede iniciar e gerenciar máquinas virtuais. Máquinas em execução devem ser desligadas antes.'),
 'sharing':dict(name='Compartilhamento de arquivos',icon='folder-network',packages=['samba','kdenetwork-filesharing'],units=['smbd.service','nmbd.service'],impact='Desativar encerra o acesso de outros computadores às pastas compartilhadas.'),
 'remote':dict(name='Acesso remoto gráfico',icon='preferences-desktop-remote-desktop',packages=['krdp','krfb','krdc'],units=[],impact='A remoção desativa os aplicativos de acesso remoto gráfico. SSH é administrado separadamente.'),
 'ssh':dict(name='Administração SSH',icon='utilities-terminal',packages=['openssh-server'],units=['ssh.service','ssh.socket'],manual=True,impact='Permite administração remota por terminal. Instalar o servidor pode iniciar o SSH; configure contas e regras de firewall antes de liberar acesso. Feche as conexões SSH antes de desativar ou remover.'),
 'printing':dict(name='Impressão e digitalização',icon='printer',packages=['cups','cups-browsed','print-manager','skanpage'],units=['cups.service','cups.socket','cups.path','cups-browsed.service'],impact='Desativar impede imprimir. Aguarde os trabalhos em andamento antes de alterar.'),
 'bluetooth':dict(name='Bluetooth',icon='preferences-system-bluetooth',packages=['bluez','bluedevil'],units=['bluetooth.service'],impact='Dispositivos Bluetooth, incluindo teclado, mouse e fones, serão desconectados.'),
 'development':dict(name='Ferramentas de desenvolvimento',icon='applications-development',packages=['build-essential','git','cmake','pkg-config'],units=[],impact='Ferramentas de compilação não consomem memória quando estão fechadas. Remover libera espaço de pacotes, sem apagar projetos.')}
PROFILES={'Essencial':['printing'],'Pessoal':['printing','bluetooth','sharing'],'Jogos':['printing','bluetooth','windows'],'Desenvolvimento':['printing','bluetooth','development','virtualization']}
STATE=Path('/var/lib/linuxbr/features')


def run(argv,timeout=40,check=True):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,env={**os.environ,'LC_ALL':'C.UTF-8','DEBIAN_FRONTEND':'noninteractive'})
    if check and result.returncode:raise ValueError(result.stderr.strip() or result.stdout.strip() or 'A operação não foi concluída.')
    return result


def unit_state(unit):
    result=run(['/usr/bin/systemctl','show','--property=LoadState,UnitFileState,ActiveState','--',unit])
    return dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)


def inventory():
    result=run(['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${db:Status-Status}\t${Installed-Size}\n'],check=False)
    installed={}
    for line in result.stdout.splitlines():
        fields=line.split('\t')
        if len(fields)==3 and fields[1]=='installed':
            installed.setdefault(fields[0].split(':')[0],[]).append((fields[0],int(fields[2] or 0)*1024))
    rows=[]
    for key,value in FEATURES.items():
        states={unit:unit_state(unit) for unit in value['units']}
        states={unit:state for unit,state in states.items() if state['LoadState']!='not-found'}
        records=[item for package in value['packages'] for item in installed.get(package,[])]
        rows.append(dict(id=key,**value,installed=[name for name,_ in records],size=sum(size for _,size in records),states=states))
    return rows


def protected_package(name):
    return name.startswith(('linuxbr-','linux-image','linux-headers','grub','systemd','libc6','libpam','plasma-workspace','plasma-desktop','task-kde-desktop')) or name in {'apt','dpkg','sudo','polkitd','sddm','network-manager','firewalld','cryptsetup','cryptsetup-initramfs','initramfs-tools','bash','coreutils'}


def package_plan(feature,action):
    if feature not in FEATURES or action not in ('install','remove'):raise ValueError('Recurso ou operação inválidos.')
    packages=FEATURES[feature]['packages']
    if action=='remove':
        packages=next(row['installed'] for row in inventory() if row['id']==feature)
    if not packages:raise ValueError('Não há pacotes instalados deste recurso para remover.')
    result=run(['/usr/bin/apt-get','--simulate','--no-install-recommends',action,'--',*packages],timeout=60)
    changes=[]
    for line in result.stdout.splitlines():
        match=re.match(r'^(Inst|Remv) ([a-z0-9][a-z0-9+.:\-]*)',line)
        if match:changes.append(dict(action=match[1],package=match[2]))
    removed=[r['package'].split(':')[0] for r in changes if r['action']=='Remv']
    if action=='remove' and any(r['action']=='Inst' for r in changes):
        raise ValueError('A remoção exigiria instalar ou substituir outros componentes. Revise as dependências na Loja; nenhum pacote foi alterado.')
    if action=='install' and removed:raise ValueError('A instalação exigiria remover programas. Revise os conflitos na Loja.')
    if any(protected_package(p) for p in removed):raise ValueError('A remoção afetaria componentes essenciais. Este recurso pode ser desativado sem remover seus pacotes.')
    essential=run(['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${Essential}\t${Priority}\n'],check=False).stdout
    protected={line.split('\t')[0].split(':')[0] for line in essential.splitlines() if '\tyes\t' in line or line.endswith('\trequired')}
    if protected.intersection(removed):raise ValueError('A operação removeria pacotes essenciais.')
    status=Path('/var/lib/dpkg/status').read_bytes()
    digest=hashlib.sha256(status+result.stdout.encode()).hexdigest()
    return dict(feature=feature,action=action,packages=packages,changes=changes,details=result.stdout,sha256=digest)


def ensure_idle(feature):
    if feature=='ssh':
        sessions=run(['/usr/bin/ss','-Hntp','state','established'],check=False)
        if 'sshd' in sessions.stdout:raise ValueError('Há conexões SSH ativas. Encerre essas conexões antes de desativar ou remover o servidor.')
    if feature=='virtualization':
        if Path('/usr/bin/virsh').exists():
            result=run(['/usr/bin/virsh','-c','qemu:///system','list','--state-running','--name'],check=False)
            if result.returncode==0 and result.stdout.strip():raise ValueError('Desligue as máquinas virtuais antes de alterar este recurso.')
        processes=run(['/usr/bin/pgrep','-f','(^|/)qemu-system-'],check=False)
        if processes.returncode==0:raise ValueError('Há uma máquina virtual em execução neste computador.')
    if feature=='printing' and Path('/usr/bin/lpstat').exists():
        jobs=run(['/usr/bin/lpstat','-W','not-completed','-o'],check=False)
        if jobs.returncode==0 and jobs.stdout.strip():raise ValueError('Conclua ou cancele os trabalhos de impressão antes de alterar.')
    if feature=='windows':
        result=run(['/usr/bin/pgrep','-x','wineserver(32|64)?'],check=False)
        if result.returncode==0:raise ValueError('Feche os programas Windows antes de remover a compatibilidade.')


def store_record(record):
    from services_backend import replace_file
    STATE.mkdir(parents=True,mode=0o700,exist_ok=True)
    replace_file(STATE/'last.json',json.dumps(record,ensure_ascii=False).encode())


def restore_units(states):
    for unit,old in states.items():
        if old['LoadState']=='masked' or old['UnitFileState'].startswith('masked'):
            run(['/usr/bin/systemctl','unmask','--',unit])
            run(['/usr/bin/systemctl','mask',*(['--runtime'] if old['UnitFileState']=='masked-runtime' else []),'--',unit])
        else:
            run(['/usr/bin/systemctl','unmask','--',unit])
            if old['UnitFileState'] in ('enabled','enabled-runtime'):run(['/usr/bin/systemctl','enable',*(['--runtime'] if old['UnitFileState']=='enabled-runtime' else []),'--',unit])
            elif old['UnitFileState']=='disabled':run(['/usr/bin/systemctl','disable','--',unit])
    for unit,old in states.items():
        run(['/usr/bin/systemctl','start' if old['ActiveState']=='active' else 'stop','--',unit])


def set_services(selection):
    if not isinstance(selection,dict) or not selection or set(selection)-FEATURES.keys() or any(type(v) is not bool for v in selection.values()):raise ValueError('Seleção inválida.')
    before={}
    for feature,enable in selection.items():
        if not enable:ensure_idle(feature)
        for unit in FEATURES[feature]['units']:
            state=unit_state(unit)
            if state['LoadState']!='not-found':before[unit]=state
    if not before:raise ValueError('Este recurso não possui serviços instalados controlados por esta página. Use instalar ou remover pacotes.')
    record=dict(kind='services',created=time.time(),selection=selection,before=before,status='applying')
    store_record(record)
    try:
        for feature,enable in selection.items():
            units=[u for u in FEATURES[feature]['units'] if u in before]
            if not units:continue
            if enable:
                run(['/usr/bin/systemctl','unmask','--',*units])
                for unit in units:
                    if before[unit]['UnitFileState']!='static':run(['/usr/bin/systemctl','enable','--',unit])
                run(['/usr/bin/systemctl','start','--',*units])
            else:
                run(['/usr/bin/systemctl','mask','--now','--',*units])
                if any(unit_state(u)['ActiveState']=='active' or unit_state(u)['LoadState']!='masked' for u in units):raise ValueError('Um componente não confirmou a desativação.')
        record['status']='complete';store_record(record)
    except Exception:
        try:restore_units(before);record['status']='rolled-back'
        except Exception as rollback:record['status']='rollback-failed';record['rollback_error']=str(rollback)
        store_record(record);raise
    return dict(message='Serviços alterados. A reversão está disponível para a última operação. Pacotes e dados pessoais foram preservados.')


def apply(request):
    if os.geteuid()!=0:raise PermissionError('Esta alteração exige autorização administrativa.')
    STATE.mkdir(parents=True,mode=0o700,exist_ok=True)
    with (STATE/'operation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        action=request.get('action')
        if action=='services':return set_services(request['selection'])
        if action=='undo':
            record=json.loads((STATE/'last.json').read_text())
            if record['kind']!='services' or record['status']!='complete':raise ValueError('Não há alteração de serviços disponível para reversão.')
            for feature in record['selection']:ensure_idle(feature)
            restore_units(record['before']);record['status']='restored';store_record(record)
            return dict(message='Estado anterior dos serviços restaurado.')
        if action in ('install','remove'):
            plan=package_plan(request['feature'],action)
            if plan['sha256']!=request['sha256']:raise ValueError('O plano de pacotes mudou. Revise a prévia novamente.')
            ensure_idle(request['feature'])
            record=dict(kind='packages',created=time.time(),plan=plan,status='applying');store_record(record)
            result=run(['/usr/bin/apt-get','-y','--no-install-recommends',*(['--no-remove'] if action=='install' else []),action,'--',*plan['packages']],timeout=1800,check=False)
            record.update(status='complete' if result.returncode==0 else 'failed',output=result.stdout+result.stderr);store_record(record)
            if result.returncode:raise ValueError('O gerenciador não concluiu a operação. Consulte a Loja e o registro de recursos.\n'+record['output'][-5000:])
            return dict(message='Pacotes alterados. Configurações e dados pessoais não foram purgados. Para reinstalar, use Instalar recurso; versões antigas podem não estar disponíveis.')
        raise ValueError('Operação desconhecida.')


if __name__=='__main__':
    try:
        raw=sys.stdin.buffer.read(32769)
        if len(raw)>32768:raise ValueError('Solicitação muito grande.')
        print(json.dumps(apply(json.loads(raw)),ensure_ascii=False))
    except Exception as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
