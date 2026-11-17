"""Versioned Wine configuration recipes and recoverable environment maintenance."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import windows_runner as runner

CATALOG=Path('/usr/share/linuxbr/windows/recipes-v1.json')
STATUS={'tested':'Testado em laboratório na base anterior','partial':'Parcial','untested':'Não testado'}
VERSIONS={'win7','win81','win10','win11'}
ACTIONS={'repair','apply','dependency','backup','restore','installer'}


def catalog():
    value=json.loads(CATALOG.read_text(encoding='utf-8'))
    if value.get('schema')!=1:raise ValueError('Versão desconhecida do catálogo de compatibilidade.')
    recipes=value.get('recipes',[]);seen=set()
    for item in recipes:
        from compatibility_records import checked_records
        checked_records(item)
        if item['id'] in seen or item['status'] not in STATUS or item['windows_version'] not in VERSIONS:
            raise ValueError('Receita de compatibilidade inválida.')
        if item['architecture'] not in ('win32','win64') or not 72<=item['dpi']<=240:
            raise ValueError('Configuração de receita inválida.')
        seen.add(item['id'])
    return value


def recipe(identifier):
    for item in catalog()['recipes']:
        if item['id']==identifier:return item
    raise ValueError('Receita não encontrada.')


def component_catalog(data):
    components = {}
    for item in data.get('recipes', []):
        for dependency in item.get('dependencies', []):
            key = dependency['id'], dependency['filename'], dependency['source']
            component = components.setdefault(key, dict(dependency, recipes=[]))
            component['recipes'].append({'id':item['id'],'name':item['name'],'architecture':item['architecture']})
    return sorted(components.values(), key=lambda component: component['name'].casefold())


def scoped_environment(identifier):
    item=runner.read_environment(identifier);path=runner.environment_path(identifier)
    env=os.environ.copy()
    for key in ('WINEPREFIX','WINEARCH','WINEDLLOVERRIDES','WINESERVER','WINELOADER'):
        env.pop(key,None)
    env.update(WINEPREFIX=str(path/'prefix'),WINEARCH=item['architecture'],WINEDEBUG='-all,err+module,err+seh')
    return env


def ensure_idle(identifier):
    try:
        subprocess.run(['wineserver','--wait'],env=scoped_environment(identifier),
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2,check=True)
    except subprocess.TimeoutExpired:
        raise ValueError('Feche todos os programas deste ambiente antes de continuar. Nenhum programa foi encerrado.') from None


def backup_environment(identifier):
    """Copy regular files and links as links; Wine links never copy personal folders."""
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    source=runner.environment_path(identifier);runner.read_environment(identifier)
    ensure_idle(identifier)
    size=0
    for directory,folders,files in os.walk(source,followlinks=False):
        folders[:]=[name for name in folders if not (Path(directory)/name).is_symlink()]
        for name in files:
            path=Path(directory)/name
            if not path.is_symlink():
                if not path.is_file():raise ValueError('O ambiente contém um arquivo especial. Faça uma cópia manual antes de reparar.')
                size+=path.stat().st_size
    backups=runner.data_root()/'backups'
    if backups.is_symlink():raise ValueError('A pasta de cópias não pode ser um link simbólico.')
    backups.mkdir(parents=True,exist_ok=True,mode=0o700)
    if shutil.disk_usage(backups).free<size+max(32*1024*1024,size//10):
        raise ValueError('Espaço insuficiente para copiar o ambiente. Nenhuma configuração foi alterada.')
    destination=backups/(identifier+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    print('Copiando o ambiente para '+str(destination),flush=True)
    try:
        shutil.copytree(source,destination,symlinks=True,ignore=shutil.ignore_patterns('*.lock'))
    except Exception:
        print('A cópia não foi concluída. Nenhum ajuste foi aplicado. Cópia parcial: '+str(destination),flush=True)
        raise
    runner.write_json(destination/'backup.json',dict(environment=identifier,created=time.time(),source=str(source),
        note='Links preservados; arquivos pessoais fora do ambiente não foram copiados.'))
    return destination


def snapshot(identifier, name):
    runner.environment_path(identifier)
    if not isinstance(name, str) or not re.fullmatch(
            re.escape(identifier) + r'-\d{8}-\d{6}-[a-f0-9]{8}', name):
        raise ValueError('A cópia não pertence ao ambiente selecionado.')
    root = runner.data_root()/'backups'
    directory = root/name
    files = (root, directory, directory/'backup.json', directory/'environment.json',
             directory/'prefix', directory/'prefix/system.reg')
    if any(path.is_symlink() for path in files) or not (directory/'prefix/system.reg').is_file():
        raise ValueError('A cópia não possui um prefixo válido.')
    try:
        metadata = json.loads((directory/'backup.json').read_text(encoding='utf-8'))
        state = json.loads((directory/'environment.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError('Os dados da cópia estão incompletos.') from None
    if (not isinstance(metadata,dict) or not isinstance(state,dict) or metadata.get('environment') != identifier
            or state.get('architecture') not in ('win32','win64')
            or not isinstance(state.get('name'), str)):
        raise ValueError('A cópia não pode ser restaurada neste ambiente.')
    return directory, state


def environment_backups(identifier):
    runner.read_environment(identifier)
    root = runner.data_root()/'backups'
    if root.is_symlink():
        return []
    result = []
    for directory in sorted(root.glob(identifier+'-*'), reverse=True):
        try:
            _, state = snapshot(identifier, directory.name)
        except ValueError:
            continue
        result.append((directory.name, state['name']))
    return result


def restore_environment(identifier, backup):
    directory, item = snapshot(identifier, backup)
    new_id = str(uuid.uuid4())
    destination = runner.environment_path(new_id)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.restauracao-', dir=destination.parent) as temporary:
        restored = Path(temporary)/new_id
        shutil.copytree(directory, restored, symlinks=True, ignore=shutil.ignore_patterns('backup.json','*.lock'))
        item['name'] = runner.clean_name(item['name'][:62].strip()+' — restaurado')
        runner.write_json(restored/'environment.json', item)
        os.rename(restored, destination)
    print('Cópia restaurada em ambiente separado: '+str(destination), flush=True)
    return new_id


def maintain(identifier,action,recipe_id=None,filename=None,backup_name=None):
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    path=runner.environment_path(identifier);item=runner.read_environment(identifier)
    if action not in ACTIONS:raise ValueError('Manutenção desconhecida.')
    if action == 'restore':
        restore_environment(identifier, backup_name)
        return 0
    selected=recipe(recipe_id) if action in ('apply','dependency') else None
    if selected and selected['architecture']!=item['architecture']:
        raise ValueError('Esta receita exige arquitetura '+selected['architecture']+'. Crie um ambiente separado.')
    dependency=None
    if action in ('dependency','installer'):
        file,kind=runner.inspect_windows_file(filename)
        if kind not in ('x64','x86','MSI'):
            raise ValueError('Selecione um instalador EXE ou MSI.')
        if kind=='x64' and item['architecture']=='win32':raise ValueError('O instalador exige um ambiente de 64 bits.')
    if action=='dependency':
        dependency=next((value for value in selected['dependencies'] if value['filename'].casefold()==file.name.casefold()),None)
        if not dependency:raise ValueError('Selecione o instalador indicado pela receita.')
    lock_path=path/'maintenance.lock'
    if lock_path.is_symlink():raise ValueError('Registro de bloqueio inválido.')
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Há outra operação neste ambiente. Aguarde sua conclusão.') from None
        backup=backup_environment(identifier);env=scoped_environment(identifier)
        if action=='backup':
            print('Cópia concluída em '+str(backup),flush=True)
            return 0
        print('Cópia concluída. Apenas este ambiente será alterado.',flush=True)
        if action=='installer':
            code=runner._run(identifier,'run',str(file))
        elif action=='repair':
            code=subprocess.call(['wineboot','--update'],env=env,cwd=str(path))
        elif action=='apply':
            if not (path/'prefix/system.reg').is_file():
                subprocess.run(['wineboot','--init'],env=env,cwd=str(path),check=True)
                subprocess.run(['wineserver','--wait'],env=env,check=True)
            subprocess.run(['winecfg','-v',selected['windows_version']],env=env,cwd=str(path),check=True)
            code=subprocess.call(['wine','reg','add',r'HKCU\Control Panel\Desktop','/v','LogPixels',
                '/t','REG_DWORD','/d',str(selected['dpi']),'/f'],env=env,cwd=str(path))
            if code==0:
                item.update(recipe=selected['id'],recipe_revision=catalog()['revision'],recipe_applied=time.time())
                runner.write_json(path/'environment.json',item)
        else:
            print(dependency['name']+' — origem declarada: '+dependency['source']+'\n'
                  'O nome do arquivo não comprova a assinatura ou a origem. Confira o instalador antes de confirmar.',flush=True)
            command=['wine','msiexec','/i',str(file)] if kind=='MSI' else ['wine',str(file)]
            code=subprocess.call(command,env=env,cwd=str(file.parent))
        subprocess.run(['wineserver','--wait'],env=env,check=True)
        print('Cópia anterior preservada em '+str(backup)+'\nCódigo de saída: '+str(code),flush=True)
        return code


def start_maintenance(identifier,action,recipe_id=None,filename=None,backup_name=None):
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    runner.read_environment(identifier)
    if action not in ACTIONS:raise ValueError('Manutenção desconhecida.')
    if action in ('apply','dependency'):recipe(recipe_id)
    if action=='restore':snapshot(identifier,backup_name)
    if filename:filename=str(runner.inspect_windows_file(filename)[0])
    job=str(uuid.uuid4())
    args=['/usr/bin/python3',str(Path(__file__).resolve()),identifier,action,'--job',job]
    if recipe_id:args+=['--recipe',recipe_id]
    if filename:args+=['--file',filename]
    if backup_name:args+=['--backup-name',backup_name]
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    return job


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('environment');parser.add_argument('action',choices=sorted(ACTIONS))
    parser.add_argument('--recipe');parser.add_argument('--file');parser.add_argument('--backup-name');parser.add_argument('--job',required=True);args=parser.parse_args()
    if str(uuid.UUID(args.job))!=args.job:raise SystemExit('Registro inválido.')
    root=runner.data_root()/'jobs';root.mkdir(parents=True,exist_ok=True,mode=0o700)
    result=dict(finished=True,code=1,error='',action=args.action,environment=args.environment)
    with (root/(args.job+'.log')).open('w',encoding='utf-8') as log:
        os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
        try:result['code']=maintain(args.environment,args.action,args.recipe,args.file,args.backup_name)
        except Exception as error:result['error']=str(error);print(str(error),flush=True)
    runner.write_json(root/(args.job+'.json'),result)
