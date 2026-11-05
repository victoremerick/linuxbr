"""Validated creation of locally managed services."""
import json
import hashlib
import fcntl
import os
from pathlib import Path
import pwd
import grp
import re
import subprocess
import sys
import tempfile

PROTECTED={'dbus.service','dbus-broker.service','systemd-logind.service','systemd-udevd.service',
           'systemd-journald.service','systemd-oomd.service','polkit.service','sddm.service',
           'display-manager.service','NetworkManager.service','firewalld.service',
           'systemd-resolved.service','accounts-daemon.service','user@.service'}


def guarded(unit):
    return unit in PROTECTED or unit.startswith(('systemd-','user@','plasma-','dbus-','polkit-'))


def override_record(scope,unit):
    info=details(scope,unit)
    if guarded(unit) or guarded(info.get('Id','')):raise ValueError('Componente essencial protegido.')
    if info.get('LoadState')!='loaded':raise ValueError('Selecione um serviço instalado e carregado.')
    if info.get('Id')!=unit:raise ValueError('Selecione o nome principal do serviço, em vez de um alias.')
    base=Path('/etc/systemd/system') if scope=='system' else Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'systemd/user'
    target=base/(unit+'.d')/'90-linuxbr.conf'
    if target.parent.is_symlink() or target.is_symlink():raise ValueError('Caminho de personalização inválido.')
    raw=target.read_bytes() if target.exists() else b''
    if len(raw)>16384:raise ValueError('Personalização muito grande.')
    return dict(path=str(target),content=raw.decode(),sha256=hashlib.sha256(raw).hexdigest(),details=info)


def override_render(spec):
    allowed={'restart','restart_seconds','memory_mib','cpu_percent','tasks_max','no_new_privileges'}
    if not isinstance(spec,dict) or set(spec)-allowed:raise ValueError('Campos de personalização inválidos.')
    lines=['# LinuxBR-Override: '+json.dumps(spec,sort_keys=True),'[Service]']
    restart=spec.get('restart','')
    if restart not in ('','no','on-failure'):raise ValueError('Política de reinício inválida.')
    if restart:lines.append('Restart='+restart)
    for key,directive,maximum,suffix in [('restart_seconds','RestartSec',3600,'s'),('memory_mib','MemoryMax',1048576,'M'),('cpu_percent','CPUQuota',102400,'%'),('tasks_max','TasksMax',1048576,'')]:
        value=spec.get(key,0)
        if type(value) is not int or not 0<=value<=maximum:raise ValueError('Limite inválido.')
        if value:lines.append(directive+'='+str(value)+suffix)
    if spec.get('no_new_privileges') is True:lines.append('NoNewPrivileges=yes')
    elif spec.get('no_new_privileges') not in (False,None):raise ValueError('Isolamento inválido.')
    return '\n'.join(lines)+'\n'


def override_apply(scope,unit,expected,spec=None,restore=False):
    authorize_scope(scope)
    record=override_record(scope,unit);target=Path(record['path']);target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target.parent/'.linuxbr.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        record=override_record(scope,unit)
        if record['sha256']!=expected:raise ValueError('Personalização alterada; abra novamente.')
        old=record['content'].encode();backup=target.with_name('.90-linuxbr.previous')
        if restore:
            if backup.is_symlink() or not backup.is_file():raise ValueError('Não há personalização anterior.')
            content=backup.read_bytes()
            if content:
                marker='# LinuxBR-Override: '
                first=content.decode().splitlines()[0]
                if not first.startswith(marker) or override_render(json.loads(first[len(marker):])).encode()!=content:raise ValueError('Backup não reconhecido.')
        else:content=override_render(spec).encode()
        if old:
            marker='# LinuxBR-Override: '
            first=old.decode().splitlines()[0]
            if not first.startswith(marker) or override_render(json.loads(first[len(marker):])).encode()!=old:raise ValueError('Personalização externa preservada; revise pelo editor apropriado.')
        replace_file(backup,old)
        try:
            if content:replace_file(target,content)
            else:target.unlink(missing_ok=True)
            ctl(scope,'daemon-reload')
            after=details(scope,unit)
            if after.get('LoadState')!='loaded':raise RuntimeError('Personalização recusada pelo sistema.')
        except Exception:
            if old:replace_file(target,old)
            else:target.unlink(missing_ok=True)
            ctl(scope,'daemon-reload');raise
    return dict(message='Personalização salva; o arquivo do pacote foi preservado. Reinicie o serviço para aplicar ao processo atual. Outras personalizações podem ter prioridade.',unit=unit)


def authorize_scope(scope):
    if scope not in ('user','system'):raise ValueError('Alcance inválido.')
    if (scope=='system') != (os.geteuid()==0):
        raise PermissionError('Use autorização administrativa para serviços do computador e sua conta para serviços pessoais.')


def control(scope, unit, action):
    authorize_scope(scope)
    if action not in ('start','stop','restart','enable','disable','reload','mask','unmask'):
        raise ValueError('Ação de serviço inválida.')
    before=details(scope,unit)
    if guarded(unit) or guarded(before.get('Id','')):
        raise ValueError('Este componente essencial é protegido. Use a página específica de configuração.')
    if action=='reload' and before.get('CanReload')!='yes':raise ValueError('Este serviço não oferece recarregamento sem reinício.')
    ctl(scope,action,'--',unit)
    after=details(scope,unit)
    if action in ('start','restart') and after.get('ActiveState') not in ('active','activating'):
        if after.get('Result')!='success':raise RuntimeError('O serviço terminou com falha. Consulte seus eventos.')
    if action=='stop' and after.get('ActiveState') not in ('inactive','failed'):
        raise RuntimeError('O serviço ainda está ativo; uma dependência pode tê-lo reativado.')
    if action=='enable' and after.get('UnitFileState') not in ('enabled','enabled-runtime'):
        raise RuntimeError('O serviço não confirmou habilitação automática.')
    if action=='disable' and after.get('UnitFileState') in ('enabled','enabled-runtime'):
        raise RuntimeError('O serviço continua habilitado.')
    if action=='mask' and after.get('LoadState')!='masked':raise RuntimeError('O bloqueio não foi confirmado.')
    if action=='unmask' and after.get('LoadState')=='masked':raise RuntimeError('O serviço continua bloqueado.')
    return dict(unit=unit,details=after,message='Operação concluída. Estado: '+after.get('ActiveState','')+'. Inicialização: '+after.get('UnitFileState','')+'. Dependências, sockets e tarefas podem iniciar unidades desabilitadas.')


def remove(scope,unit,expected):
    authorize_scope(scope);target=location(scope,unit)
    fd=os.open(target.parent/'.linuxbr-service.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        record=read_definition(scope,unit)
        if record['sha256']!=expected:raise ValueError('O serviço mudou. Reabra a operação.')
        state=details(scope,unit)
        if state.get('ActiveState') not in ('inactive','failed') or state.get('UnitFileState') not in ('disabled','static') or state.get('TriggeredBy'):
            raise ValueError('Pare e desabilite o serviço e seus acionadores antes de remover.')
        backup=target.parent/'.linuxbr-service-backups'
        if backup.is_symlink():raise ValueError('Diretório de backup inválido.')
        backup.mkdir(mode=0o700,exist_ok=True)
        replace_file(backup/(unit+'.removed'),record['content'].encode())
        target.unlink()
        try:ctl(scope,'daemon-reload')
        except Exception:
            replace_file(target,record['content'].encode());ctl(scope,'daemon-reload');raise
        if state.get('ActiveState')=='failed':
            subprocess.run(['/usr/bin/systemctl',*(['--user'] if scope=='user' else []),'reset-failed','--',unit],capture_output=True,text=True,timeout=15)
            if details(scope,unit).get('ActiveState')=='failed':raise RuntimeError('A definição foi removida, mas o marcador de falha não foi limpo. Atualize a lista e consulte o estado do gerenciador.')
    return dict(unit=unit,message='Serviço removido. Uma cópia da definição foi preservada na pasta de backups.')


def text(value, limit=4096):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Texto inválido na configuração do serviço.')
    return value


def quoted(value, command=False):
    value = text(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if command:
        value = value.replace('$', '$$')
    return '"' + value + '"'


def render(scope, spec, validate_runtime=True):
    if scope not in ('user', 'system') or not isinstance(spec, dict):
        raise ValueError('Configuração inválida.')
    name = spec.get('name', '')
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name):
        raise ValueError('Use letras minúsculas, números e hífens no identificador.')
    argv = spec.get('argv')
    if not isinstance(argv, list) or not 1 <= len(argv) <= 100:
        raise ValueError('Informe um programa e seus argumentos.')
    for argument in argv:
        text(argument)
    executable = Path(argv[0])
    if not executable.is_absolute() or (validate_runtime and (not executable.is_file() or not os.access(executable, os.X_OK))):
        raise ValueError('Selecione um programa executável com caminho absoluto.')
    directory = text(spec.get('directory', ''))
    if directory and (directory != directory.strip() or not Path(directory).is_absolute() or (validate_runtime and not Path(directory).is_dir())):
        raise ValueError('A pasta de trabalho deve existir e ter caminho absoluto.')
    restart = spec.get('restart', 'no')
    if restart not in ('no', 'on-failure'):
        raise ValueError('Política de reinício inválida.')
    delay = spec.get('restart_seconds', 10)
    if type(delay) is not int or not 1 <= delay <= 3600:
        raise ValueError('Intervalo de reinício inválido.')
    timing={}
    for key,default,minimum,maximum in [('restart_burst',3,1,20),('restart_window',300,30,3600),('stop_seconds',30,1,3600),('start_seconds',90,1,3600),('start_delay',0,0,300)]:
        value=spec.get(key,default)
        if type(value) is not int or not minimum<=value<=maximum:raise ValueError('Tempo ou limite de tentativas inválido.')
        timing[key]=value
    if timing['start_delay']>=timing['start_seconds']:raise ValueError('O tempo máximo para iniciar deve superar o atraso inicial.')
    mask=spec.get('umask','0077')
    if not isinstance(mask,str) or not re.fullmatch(r'0?[0-7]{3}',mask):raise ValueError('Permissão padrão inválida: use três ou quatro dígitos octais.')
    description = text(spec.get('description', name), 160)
    unit = 'linuxbr-custom-' + name + '.service'
    dependencies=[]
    for key, directive in [('requires','Requires'),('after','After'),('wants','Wants')]:
        values=spec.get(key,[])
        if not isinstance(values,list) or len(values)>32:
            raise ValueError('Lista de dependências inválida.')
        for value in values:
            if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_@:.\-]+\.(service|target|socket|mount)',value) or value==unit:
                raise ValueError('Dependência inválida ou referência ao próprio serviço.')
        if values:dependencies.append(directive+'='+' '.join(dict.fromkeys(values)))
    lines = ['[Unit]', 'Description=' + description.strip().replace('%', '%%'),
             *dependencies, 'StartLimitIntervalSec='+str(timing['restart_window']), 'StartLimitBurst='+str(timing['restart_burst']), '', '[Service]',
             'Type=exec', 'ExecStart=' + ' '.join(quoted(a, True) for a in argv),
             'Restart=' + restart, 'RestartSec=' + str(delay),
             'TimeoutStopSec='+str(timing['stop_seconds']), 'UMask='+mask]
    if 'start_seconds' in spec or timing['start_delay']:lines.append('TimeoutStartSec='+str(timing['start_seconds']))
    if timing['start_delay']:lines.append('ExecStartPre=/usr/bin/sleep '+str(timing['start_delay']))
    if directory:
        lines.append('WorkingDirectory=' + directory.replace('%', '%%'))
    if scope == 'system':
        user = text(spec.get('user', ''), 128)
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*\$?', user):
            raise ValueError('Informe a conta que executará o serviço.')
        if validate_runtime:
            try:pwd.getpwnam(user)
            except KeyError:raise ValueError('A conta de execução não existe neste computador.') from None
        lines.append('User=' + user)
        group=text(spec.get('group',''),128)
        if group:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*\$?',group):raise ValueError('Grupo de execução inválido.')
            if validate_runtime:
                try:grp.getgrnam(group)
                except KeyError:raise ValueError('O grupo de execução não existe neste computador.') from None
            lines.append('Group='+group)
    for key,directive,maximum,suffix in [('memory_mib','MemoryMax',1048576,'M'),('cpu_percent','CPUQuota',102400,'%'),('tasks_max','TasksMax',1048576,'')]:
        value=spec.get(key,0)
        if type(value) is not int or not 0<=value<=maximum:
            raise ValueError('Limite de recursos inválido.')
        if value:lines.append(directive+'='+str(value)+suffix)
    isolation=spec.get('isolation',False)
    if type(isolation) is not bool:raise ValueError('Opção de isolamento inválida.')
    if isolation:
        if scope!='system':raise ValueError('O isolamento de arquivos exige um serviço do computador.')
        lines+=['NoNewPrivileges=yes','PrivateTmp=yes','ProtectSystem=strict','ProtectHome=yes','PrivateDevices=yes','ProtectKernelTunables=yes','ProtectControlGroups=yes','RestrictSUIDSGID=yes']
    private_network=spec.get('private_network',False)
    if type(private_network) is not bool or private_network and scope!='system':raise ValueError('A rede isolada exige um serviço do computador.')
    if private_network:lines.append('PrivateNetwork=yes')
    environment = spec.get('environment', {})
    if not isinstance(environment, dict) or len(environment) > 128:
        raise ValueError('Variáveis de ambiente inválidas.')
    for key, value in environment.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError('Nome de variável inválido.')
        lines.append('Environment=' + quoted(key + '=' + text(value)))
    lines += ['', '[Install]', 'WantedBy=' + ('default.target' if scope == 'user' else 'multi-user.target'), '']
    metadata = '# LinuxBR-Definition: ' + json.dumps(spec, ensure_ascii=True, sort_keys=True)
    return unit, metadata + '\n' + '\n'.join(lines)


def ctl(scope, *args):
    result = subprocess.run(['/usr/bin/systemctl', *(['--user'] if scope == 'user' else []), *args],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Não foi possível atualizar o gerenciador de serviços.')
    return result.stdout


def create(scope, spec):
    if scope == 'system' and os.geteuid() != 0:
        raise PermissionError('Criar serviços do computador exige autorização administrativa.')
    if scope == 'user' and os.geteuid() == 0:
        raise PermissionError('Crie serviços pessoais na sua conta normal.')
    unit, content = render(scope, spec)
    base = (Path('/etc/systemd/system') if scope == 'system' else
            Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'systemd/user')
    base.mkdir(parents=True, exist_ok=True)
    destination = base / unit
    if destination.exists() or destination.is_symlink():
        raise ValueError('Já existe um serviço com esse identificador.')
    properties = ctl(scope, 'show', '--property=LoadState', '--', unit)
    if properties.strip() != 'LoadState=not-found':
        raise ValueError('O identificador já está registrado no sistema.')
    with tempfile.TemporaryDirectory(prefix='linuxbr-service-') as temporary:
        candidate = Path(temporary) / unit
        candidate.write_text(content, encoding='utf-8')
        probe = subprocess.run(['/usr/bin/systemd-analyze', *(['--user'] if scope == 'user' else []),
                                'verify', str(candidate)], capture_output=True, text=True, timeout=15)
        if probe.returncode:
            raise ValueError('A validação do serviço falhou: ' + probe.stderr.strip())
    # Exclusive creation protects existing units, including dangling symbolic links.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        ctl(scope, 'daemon-reload')
        if ctl(scope, 'show', '--property=LoadState', '--', unit).strip() != 'LoadState=loaded':
            raise RuntimeError('O serviço não foi carregado corretamente.')
    except Exception:
        destination.unlink(missing_ok=True)
        ctl(scope, 'daemon-reload')
        raise
    return {'unit': unit, 'message': 'Serviço criado, parado e sem início automático. Use os controles para habilitar ou iniciar.'}


def details(scope, unit):
    if not isinstance(unit, str) or not re.fullmatch(r'[A-Za-z0-9_@:.\\-]+\.service', unit):
        raise ValueError('Serviço inválido.')
    keys = ['Id', 'Description', 'LoadState', 'ActiveState', 'SubState', 'UnitFileState',
            'MainPID', 'User', 'FragmentPath', 'DropInPaths', 'WorkingDirectory',
            'MemoryCurrent', 'CPUUsageNSec', 'NRestarts', 'Result', 'ExecMainStatus',
            'ActiveEnterTimestamp', 'Restart', 'Requires', 'Wants', 'After', 'TriggeredBy', 'CanReload', 'RequiredBy', 'WantedBy','MemoryMax','CPUQuotaPerSecUSec','TasksMax','NoNewPrivileges','Group','DynamicUser','TimeoutStartUSec','TimeoutStopUSec','StartLimitBurst','StartLimitIntervalUSec','PrivateNetwork','UMask']
    raw = ctl(scope, 'show', '--property=' + ','.join(keys), '--', unit)
    data=dict(line.split('=', 1) for line in raw.splitlines() if '=' in line);data['Scope']=scope
    path=data.get('FragmentPath','')
    if path.startswith('/'):
        result=subprocess.run(['dpkg-query','-S','--',path],capture_output=True,text=True,timeout=10)
        if result.returncode==0 and ': ' in result.stdout:
            package=result.stdout.splitlines()[0].split(': ',1)[0];data['Package']=package
            metadata=subprocess.run(['dpkg-query','-W','-f=${Maintainer}','--',package],capture_output=True,text=True,timeout=10)
            if metadata.returncode==0:data['Maintainer']=metadata.stdout[:512].strip()
    data['Protection']='Protegido' if guarded(unit) or guarded(data.get('Id','')) else 'Operações administrativas disponíveis'
    return data


def linger_state(username):
    account=pwd.getpwnam(username)
    if not 1000<=account.pw_uid<65534:raise ValueError('Selecione uma conta pessoal.')
    result=subprocess.run(['loginctl','show-user','--property=Linger','--value','--',account.pw_name],capture_output=True,text=True,timeout=15)
    if result.returncode:raise RuntimeError('Não foi possível consultar a execução sem login desta conta.')
    value=result.stdout.strip()
    if value not in ('yes','no'):raise RuntimeError('O sistema não informou um estado válido.')
    return dict(username=account.pw_name,enabled=value=='yes')


def set_linger(request):
    if os.geteuid()!=0:raise PermissionError('Esta configuração exige autorização administrativa.')
    username=request.get('username');enabled=request.get('enabled');expected=request.get('expected')
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*\$?',username) or type(enabled) is not bool or type(expected) is not bool:raise ValueError('Configuração de execução sem login inválida.')
    descriptor=os.open('/run/linuxbr-user-linger.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if linger_state(username)['enabled']!=expected:raise ValueError('O estado da conta mudou; abra a configuração novamente.')
        command=subprocess.run(['loginctl','enable-linger' if enabled else 'disable-linger','--',username],capture_output=True,text=True,timeout=20)
        if command.returncode:raise RuntimeError(command.stderr.strip() or 'A alteração foi recusada.')
        actual=linger_state(username)
        if actual['enabled']!=enabled:raise RuntimeError('O sistema não confirmou a alteração.')
    return actual


def inventory(scope):
    units = json.loads(ctl(scope, 'list-units', '--all', '--type=service', '--output=json', '--no-pager'))
    files = json.loads(ctl(scope, 'list-unit-files', '--type=service', '--output=json', '--no-pager'))
    rows = {row['unit']: dict(row) for row in units}
    for item in files:
        name = item['unit_file']
        row = rows.setdefault(name, dict(unit=name, active='not-loaded', description=''))
        row['enabled'] = item['state']
    return sorted(rows.values(), key=lambda row: row['unit'].casefold())


def location(scope, unit):
    if scope not in ('user', 'system') or not re.fullmatch(r'linuxbr-custom-[a-z][a-z0-9-]{0,63}\.service', unit):
        raise ValueError('Selecione um serviço criado pelo gerenciador Linux BR.')
    base = (Path('/etc/systemd/system') if scope == 'system' else
            Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'systemd/user')
    return base / unit


def read_definition(scope, unit):
    path = location(scope, unit)
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('O arquivo do serviço não é uma definição local regular.')
    raw = path.read_bytes()
    if len(raw) > 65536:
        raise ValueError('Definição muito grande.')
    prefix = '# LinuxBR-Definition: '
    first = raw.decode('utf-8').splitlines()[0]
    if not first.startswith(prefix):
        raise ValueError('Este serviço não possui uma definição editável pelo formulário.')
    spec = json.loads(first[len(prefix):])
    name, generated = render(scope, spec, validate_runtime=False)
    if name != unit or generated.encode('utf-8') != raw:
        raise ValueError('O arquivo foi editado externamente. Preserve e revise essas alterações antes de usar o formulário.')
    return dict(spec=spec, sha256=hashlib.sha256(raw).hexdigest(), content=raw.decode())


def replace_file(path, content):
    fd, temporary = tempfile.mkstemp(prefix='.linuxbr-service-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def revise(scope, unit, expected, spec=None, restore=False):
    if scope == 'system' and os.geteuid() != 0:
        raise PermissionError('Alterar serviços do computador exige autorização administrativa.')
    if scope == 'user' and os.geteuid() == 0:
        raise PermissionError('Use a conta normal para serviços pessoais.')
    path = location(scope, unit)
    lock_fd = os.open(path.parent / '.linuxbr-service.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = read_definition(scope, unit)
        if current['sha256'] != expected:
            raise ValueError('O serviço mudou. Reabra o formulário antes de salvar.')
        backup_dir = path.parent / '.linuxbr-service-backups'
        if backup_dir.is_symlink():
            raise ValueError('Diretório de backup inválido.')
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        backup = backup_dir / unit
        if restore:
            if backup.is_symlink() or not backup.is_file():
                raise ValueError('Não há configuração anterior disponível.')
            restored = backup.read_text(encoding='utf-8')
            prefix = '# LinuxBR-Definition: '
            first = restored.splitlines()[0]
            if not first.startswith(prefix):
                raise ValueError('Backup inválido.')
            spec = json.loads(first[len(prefix):])
        name, content = render(scope, spec)
        if name != unit:
            raise ValueError('O identificador não pode ser alterado durante a edição.')
        with tempfile.TemporaryDirectory(prefix='linuxbr-service-') as temporary:
            candidate = Path(temporary) / unit
            candidate.write_text(content, encoding='utf-8')
            probe = subprocess.run(['/usr/bin/systemd-analyze', *(['--user'] if scope == 'user' else []),
                                    'verify', str(candidate)], capture_output=True, text=True, timeout=15)
            if probe.returncode:
                raise ValueError('A configuração não passou na validação: ' + probe.stderr.strip())
        old = current['content'].encode('utf-8')
        replace_file(backup, old)
        try:
            replace_file(path, content.encode('utf-8'))
            ctl(scope, 'daemon-reload')
            if details(scope, unit)['LoadState'] != 'loaded':
                raise RuntimeError('O serviço não foi carregado após a alteração.')
        except Exception:
            replace_file(path, old)
            ctl(scope, 'daemon-reload')
            raise
    return dict(unit=unit, message='Configuração salva. Reinicie o serviço quando desejar aplicar ao processo em execução.')


def dispatch(request):
    scope = request['scope']
    action = request.get('action', 'create')
    if action=='linger':return set_linger(request)
    if action=='override-read':return override_record(scope,request['unit'])
    if action in ('override','override-restore'):return override_apply(scope,request['unit'],request['sha256'],request.get('spec'),action=='override-restore')
    if action=='control':return control(scope,request['unit'],request['operation'])
    if action=='remove':return remove(scope,request['unit'],request['sha256'])
    if action == 'create':
        return create(scope, request['spec'])
    if action == 'read':
        return read_definition(scope, request['unit'])
    if action in ('edit', 'restore'):
        return revise(scope, request['unit'], request['sha256'], request.get('spec'), action == 'restore')
    raise ValueError('Operação desconhecida.')


if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError('Configuração muito grande.')
        request = json.loads(raw)
        print(json.dumps(dispatch(request), ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
