"""Serialized native package transactions with explicit scope and local records."""
import argparse
import codecs
import fcntl
import json
import os
from pathlib import Path
import re
import pty
import selectors
import subprocess
import sys
import time
import uuid

LOG_STREAM=None

ACTIONS = {'install', 'update', 'remove'}
DEB_NAME = re.compile(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?')
FLATPAK_ID = re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}(?:/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?')


def root():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'linuxbr/store'


def checked_request(value):
    if not isinstance(value, dict) or value.get('action') not in ACTIONS:
        raise ValueError('Operação de pacote inválida.')
    result = {key: value.get(key, '') for key in ('manager','action','target','scope','origin','name')}
    if result['manager']=='file':result['sha256']=value.get('sha256','')
    if any(not isinstance(value,str) for value in result.values()):
        raise ValueError('Operação de pacote inválida.')
    if result['manager'] == 'deb':
        if result['scope'] != 'system' or not DEB_NAME.fullmatch(result['target']):
            raise ValueError('Pacote DEB ou alcance inválido.')
    elif result['manager'] == 'flatpak':
        if result['scope'] not in ('user','system') or not FLATPAK_ID.fullmatch(result['target']):
            raise ValueError('Aplicativo Flatpak ou alcance inválido.')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', result['origin']):
            raise ValueError('Selecione uma origem Flatpak configurada.')
    elif result['manager']=='file':
        path=Path(result['target'])
        if result['action']!='install' or not path.is_absolute() or '\x00' in str(path) or path.suffix.lower() not in ('.deb','.flatpak','.flatpakref') or not re.fullmatch(r'[a-f0-9]{64}',result['sha256']):raise ValueError('Arquivo de instalação inválido.')
        if result['scope']!=('system' if path.suffix.lower()=='.deb' else 'user'):raise ValueError('Alcance de instalação inválido.')
    else:
        raise ValueError('Gerenciador desconhecido.')
    if len(result['name'])>200 or any(ord(c)<32 for c in result['name']):
        raise ValueError('Nome inválido.')
    return result


def atomic_json(path, value):
    from windows_runner import write_json
    write_json(path, value)


def history():
    result=[]
    for path in (root()/'jobs').glob('*.json'):
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
            checked_request(value['request'])
            if str(uuid.UUID(path.stem))!=path.stem:continue
            result.append(value)
        except (OSError,ValueError,KeyError,TypeError):continue
    return sorted(result,key=lambda item:item.get('started',0),reverse=True)[:100]


def emit(event, **values):
    if LOG_STREAM is not None and event=='output':
        LOG_STREAM.write(values.get('text',''));LOG_STREAM.flush()
    print(json.dumps(dict(event=event,**values),ensure_ascii=False),flush=True)


def flatpak_command(request):
    request=checked_request(request)
    if request['manager']!='flatpak':raise ValueError('A operação exige Flatpak.')
    command=['/usr/bin/flatpak','--'+request['scope'],
             {'install':'install','update':'update','remove':'uninstall'}[request['action']]]
    if request['action']=='install':command.append(request['origin'])
    return command+[request['target']]


def machine_architecture():
    value=subprocess.check_output(['/usr/bin/dpkg','--print-architecture'],text=True,timeout=3).strip()
    if not re.fullmatch(r'[a-z0-9]+',value):raise ValueError('Arquitetura do sistema não identificada.')
    return value


def run_flatpak(request):
    command=flatpak_command(request)
    emit('output',text='Confira permissões, componentes e tamanho apresentados pelo Flatpak. '
         'Use Confirmar etapa ou Recusar quando o gerenciador solicitar.\n')
    run_terminal(command)


def run_terminal(command):
    # Flatpak declines questions automatically when stdin is not a terminal.
    # A private terminal keeps native prompts, with answers forwarded explicitly.
    master,slave=pty.openpty();decoder=codecs.getincrementaldecoder('utf-8')('replace')
    try:
        process=subprocess.Popen(command,stdin=slave,stdout=slave,stderr=slave,start_new_session=True,
            env={**os.environ,'LC_ALL':'C.UTF-8','TERM':'dumb'})
        os.close(slave);slave=None
        with selectors.DefaultSelector() as selector:
            selector.register(master,selectors.EVENT_READ,'output')
            selector.register(sys.stdin.fileno(),selectors.EVENT_READ,'input')
            while master in selector.get_map():
                for key,_ in selector.select():
                    if key.data=='input':
                        answer=os.read(key.fd,4096)
                        if answer:os.write(master,answer)
                        else:
                            selector.unregister(key.fd)
                            os.write(master,b'n\n')
                        continue
                    try:chunk=os.read(master,8192)
                    except OSError:chunk=b''
                    if not chunk:selector.unregister(master);break
                    text=decoder.decode(chunk).replace('\r\n','\n').replace('\r','\n')
                    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
                    if text:emit('output',text=text)
                    for number in re.findall(r'(?<![0-9])([0-9]{1,3})%',text):
                        if int(number)<=100:emit('progress',percentage=int(number))
        code=process.wait()
    finally:
        os.close(master)
        if slave is not None:os.close(slave)
    if code:raise ValueError('O Flatpak não concluiu a operação (código '+str(code)+'). Confira o registro acima.')


class PackageKit:
    """The system daemon owns authorization, package locks and transaction state."""
    SERVICE='org.freedesktop.PackageKit'
    INTERFACE=SERVICE+'.Transaction'

    def __init__(self):
        from gi.repository import Gio,GLib
        self.Gio=Gio;self.GLib=GLib
        self.bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)

    def transaction(self,method,signature,arguments):
        Gio,GLib=self.Gio,self.GLib
        path=self.bus.call_sync(self.SERVICE,'/org/freedesktop/PackageKit',self.SERVICE,
            'CreateTransaction',None,GLib.VariantType.new('(o)'),Gio.DBusCallFlags.NONE,15000,None).unpack()[0]
        proxy=Gio.DBusProxy.new_sync(self.bus,Gio.DBusProxyFlags.NONE,None,self.SERVICE,path,self.INTERFACE,None)
        loop=GLib.MainLoop();result={'packages':[],'errors':[],'finished':False,'exit':None}
        def signal_received(_proxy,_sender,name,parameters):
            values=parameters.unpack()
            if name=='Package':
                result['packages'].append({'info':values[0],'id':values[1],'summary':values[2]})
                emit('output',text=values[1]+' — '+values[2]+'\n')
            elif name=='ErrorCode':result['errors'].append(str(values[1]))
            elif name in ('EulaRequired','RepoSignatureRequired','MediaChangeRequired'):
                result['errors'].append('Esta transação exige licença, chave ou mídia adicional. '
                    'Confira as fontes e as condições apresentadas pelo fornecedor antes de tentar novamente.')
            elif name=='RequireRestart':emit('output',text='O gerenciador solicita reiniciar a sessão ou o sistema após concluir.\n')
            elif name=='Finished':
                result.update(finished=True,exit=values[0]);loop.quit()
            elif name=='Destroy' and not result['finished']:
                result['errors'].append('A transação foi encerrada pelo gerenciador.');loop.quit()
        def changed(_proxy,properties,_invalidated):
            values=properties.unpack()
            if 'Percentage' in values:emit('progress',percentage=values['Percentage'])
        proxy.connect('g-signal',signal_received);proxy.connect('g-properties-changed',changed)
        proxy.call_sync('SetHints',GLib.Variant('(as)',(['interactive=true','background=false','cache-age=4294967295'],)),
                        Gio.DBusCallFlags.NONE,15000,None)
        proxy.call_sync(method,GLib.Variant(signature,arguments),Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION,15000,None)
        if not result['finished']:loop.run()
        if result['errors'] or result['exit']!=1:
            raise ValueError('; '.join(result['errors']) or 'O gerenciador não concluiu a transação: '+str(result['exit']))
        return result['packages']

    def perform(self,request):
        action=request['action'];package=request['target']
        if action=='update':
            packages=self.transaction('GetUpdates','(t)',(1<<16,))
        else:
            filters=(1<<16)|(1<<14)|(1<<(2 if action=='remove' else 3))
            packages=self.transaction('Resolve','(tas)',(filters,[package]))
        matches=[value for value in packages if value['id'].split(';')[0]==package.split(':')[0]]
        architecture=package.split(':')[1] if ':' in package else machine_architecture()
        matches=[value for value in matches if value['id'].split(';')[2] in (architecture,'all')]
        if len(matches)!=1:
            raise ValueError('Nenhuma versão única disponível para esta operação. O pacote pode já estar atualizado '
                             'ou instalado. Confira a origem e a arquitetura na Loja.')
        identifier=matches[0]['id']
        method={'install':'InstallPackages','update':'UpdatePackages','remove':'RemovePackages'}[action]
        def arguments(flags):
            return (flags,[identifier],False,False) if action=='remove' else (flags,[identifier])
        signature='(tasbb)' if action=='remove' else '(tas)'
        plan=self.transaction(method,signature,arguments((1<<1)|(1<<2)))
        emit('confirmation',packages=plan,target=identifier,action=action,preflight=getattr(self,'preflight',None))
        if sys.stdin.readline().strip()!='approve':
            raise ValueError('Operação recusada. Nenhum pacote foi alterado por esta etapa.')
        emit('output',text='Aguardando autorização nativa e gerenciador de pacotes…\n')
        self.transaction(method,signature,arguments(1<<1))


def available_updates():
    """Use current native indexes; this query neither refreshes nor installs."""
    results=[];errors=[]
    try:
        architecture=machine_architecture()
        for value in PackageKit().transaction('GetUpdates','(t)',(1<<16,)):
            parts=value['id'].split(';')
            if len(parts)!=4 or parts[2] not in (architecture,'all'):continue
            target=parts[0]+':'+parts[2]
            results.append(dict(manager='deb',scope='system',target=target,origin=parts[3],installed=True,
                name=parts[0],label='DEB · sistema · '+parts[0]+' '+parts[1]+' · '+parts[3]))
    except Exception as error:errors.append('DEB: '+str(error))
    for scope,title in (('user','sua conta'),('system','sistema')):
        try:
            query=subprocess.run(['/usr/bin/flatpak','remote-ls','--'+scope,'--cached','--updates','--app',
                '--columns=application,arch,branch,origin,name'],capture_output=True,text=True,timeout=30,
                env={**os.environ,'LC_ALL':'C'})
            if query.returncode:raise ValueError(query.stderr.strip() or 'Consulta não concluída.')
            for line in query.stdout.splitlines():
                values=line.split('\t')
                if len(values)!=5:continue
                target='/'.join(values[:3]);name=values[4][:200] or values[0]
                candidate=dict(manager='flatpak',scope=scope,target=target,origin=values[3],installed=True,name=name,
                    label='Flatpak · '+title+' · '+name+' · '+target+' · '+values[3])
                checked_request(dict(candidate,action='update'));results.append(candidate)
        except Exception as error:errors.append('Flatpak '+title+': '+str(error))
    return results,errors


def execute(request,identifier):
    global LOG_STREAM
    if os.geteuid()==0:raise ValueError('Abra a Loja na sessão normal do usuário.')
    request=checked_request(request)
    if str(uuid.UUID(identifier))!=identifier:raise ValueError('Registro de operação inválido.')
    directory=root();directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    if directory.is_symlink():raise ValueError('A pasta da Loja não pode ser um link simbólico.')
    record=dict(id=identifier,request=request,started=time.time(),finished=False,status='waiting')
    path=directory/'jobs'/(identifier+'.json');atomic_json(path,record)
    log_path=directory/'jobs'/(identifier+'.log')
    if log_path.is_symlink():raise ValueError('Registro de operação inválido.')
    LOG_STREAM=log_path.open('a',encoding='utf-8')
    try:
        lock_name=('deb' if Path(request['target']).suffix.lower()=='.deb' else 'flatpak') if request['manager']=='file' else request['manager']
        lock_path=directory/(lock_name+'.lock')
        if lock_path.is_symlink():raise ValueError('Registro de bloqueio inválido.')
        with lock_path.open('a') as lock:
            emit('output',text='Aguardando outras operações deste gerenciador…\n')
            fcntl.flock(lock,fcntl.LOCK_EX)
            record['status']='running';atomic_json(path,record)
            if request['manager']=='file':run_local(request)
            elif request['manager']=='deb':
                manager=PackageKit()
                if request['action']=='update':
                    try:
                        from protection_status import preflight
                        manager.preflight=preflight();record['preflight']=manager.preflight;atomic_json(path,record)
                    except ImportError:manager.preflight=None
                manager.perform(request)
            else:run_flatpak(request)
        record.update(status='success',error='')
        emit('output',text='Operação concluída pelo gerenciador.\n')
    except Exception as error:
        record.update(status='failed',error=str(error))
        emit('output',text=str(error)+'\n')
    finally:
        record.update(finished=True,ended=time.time());atomic_json(path,record)
        emit('finished',record=record)
        LOG_STREAM.close();LOG_STREAM=None
    return 0 if record['status']=='success' else 1


def run_local(request):
    import hashlib
    import stat
    import tempfile
    original=Path(request['target']).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='linuxbr-package-') as directory:
        snapshot=Path(directory)/('programa'+original.suffix.lower());hasher=hashlib.sha256()
        fd=os.open(original,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as source,snapshot.open('xb') as output:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise ValueError('Selecione um arquivo regular.')
            while chunk:=source.read(1024*1024):hasher.update(chunk);output.write(chunk)
            output.flush();os.fsync(output.fileno())
        snapshot.chmod(0o400)
        if hasher.hexdigest()!=request['sha256']:raise ValueError('O arquivo mudou depois da revisão. Selecione e confira o arquivo novamente.')
        from installer import inspect_package
        _,allowed,details=inspect_package(str(snapshot))
        if not allowed:raise ValueError('Formato não permitido.')
        emit('output',text=details+'\nSHA-256: '+hasher.hexdigest()+'\n')
        if original.suffix.lower()=='.deb':
            manager=PackageKit();plan=manager.transaction('InstallFiles','(tas)',(1<<2,[str(snapshot)]))
            emit('confirmation',packages=plan,target=original.name,action='install')
            if sys.stdin.readline().strip()!='approve':raise ValueError('Instalação recusada.')
            manager.transaction('InstallFiles','(tas)',(0,[str(snapshot)]))
        else:
            emit('output',text='Confira a origem, as permissões e o tamanho apresentados pelo Flatpak antes de responder.\n')
            run_terminal(['/usr/bin/flatpak','--user','install',str(snapshot)])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--request');parser.add_argument('--job');parser.add_argument('--list-updates',action='store_true');parser.add_argument('--refresh-indexes',action='store_true')
    args=parser.parse_args()
    if args.refresh_indexes:
        try:PackageKit().transaction('RefreshCache','(b)',(True,));emit('output',text='Índices atualizados. Nenhum pacote foi instalado.\n');raise SystemExit(0)
        except Exception as error:emit('output',text=str(error)+'\n');raise SystemExit(1)
    if args.list_updates:
        values,errors=available_updates();emit('updates',targets=values,errors=errors);raise SystemExit(0)
    if not args.request or not args.job:parser.error('Informe a operação e o registro.')
    try:raise SystemExit(execute(json.loads(args.request),args.job))
    except (OSError,ValueError,ImportError) as error:
        emit('output',text=str(error));raise SystemExit(1)
