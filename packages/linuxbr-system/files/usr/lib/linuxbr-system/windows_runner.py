"""User-owned Wine environments. Never execute a shell or run Wine as root."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import uuid


def data_root():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'linuxbr/windows'


def clean_name(name):
    if not isinstance(name,str):raise ValueError('Nome inválido.')
    name=name.strip()
    if not name or len(name)>80 or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Use um nome de 1 a 80 caracteres, sem quebras de linha.')
    return name


def write_json(path,value):
    """Replace one user-owned record without leaving a partially written JSON file."""
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise ValueError('A configuração não pode ser um link simbólico.')
    descriptor,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def environment_path(identifier):
    if not isinstance(identifier,str) or str(uuid.UUID(identifier)) != identifier:
        raise ValueError('Ambiente inválido.')
    path=data_root()/'environments'/identifier
    if path.is_symlink() or (path/'prefix').is_symlink():
        raise ValueError('O ambiente não pode ser um link simbólico.')
    return path


def create_environment(name, architecture='win64'):
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    name=clean_name(name)
    if architecture not in ('win64','win32'):
        raise ValueError('Arquitetura inválida.')
    identifier=str(uuid.uuid4()); path=environment_path(identifier)
    path.mkdir(parents=True,mode=0o700)
    write_json(path/'environment.json',dict(name=name,architecture=architecture))
    return identifier


def environments():
    result=[]
    for path in sorted((data_root()/'environments').glob('*')):
        try:
            item=read_environment(path.name)
            result.append((path.name,item['name']))
        except (ValueError,OSError,KeyError):
            continue
    return result


def read_environment(identifier):
    item=json.loads((environment_path(identifier)/'environment.json').read_text(encoding='utf-8'))
    if not isinstance(item,dict) or not isinstance(item.get('name'),str) or item.get('architecture') not in ('win64','win32'):
        raise ValueError('Configuração de ambiente inválida.')
    clean_name(item['name'])
    return item


def rename_environment(identifier,name):
    item=read_environment(identifier);item['name']=clean_name(name)
    write_json(environment_path(identifier)/'environment.json',item)


def default_environment():
    try:
        item=json.loads((data_root()/'preferences.json').read_text(encoding='utf-8'))
        identifier=item.get('default_environment')
        read_environment(identifier)
        return identifier
    except (OSError,ValueError,TypeError,AttributeError):return None


def set_default_environment(identifier):
    read_environment(identifier)
    write_json(data_root()/'preferences.json',{'default_environment':identifier})


def program_path(identifier):
    if not isinstance(identifier,str) or str(uuid.UUID(identifier))!=identifier:
        raise ValueError('Atalho inválido.')
    path=data_root()/'programs'/(identifier+'.json')
    if path.is_symlink():raise ValueError('O atalho não pode ser um link simbólico.')
    return path


def program_desktop(identifier):
    program_path(identifier)
    return data_root().parent.parent/'applications'/('linuxbr-windows-'+identifier+'.desktop')


def read_program(identifier):
    item=json.loads(program_path(identifier).read_text(encoding='utf-8'))
    if not isinstance(item,dict):raise ValueError('Atalho inválido.')
    clean_name(item.get('name',''));read_environment(item.get('environment'))
    filename=item.get('file')
    if not isinstance(filename,str) or not Path(filename).is_absolute() or Path(filename).suffix.lower()!='.exe':
        raise ValueError('O atalho precisa apontar para um EXE local.')
    item['id']=identifier
    return item


def programs(identifier=None):
    result=[]
    for path in (data_root()/'programs').glob('*.json'):
        try:
            item=read_program(path.stem)
            if identifier is None or item['environment']==identifier:result.append(item)
        except (OSError,ValueError,TypeError,AttributeError):continue
    return sorted(result,key=lambda item:item['name'].casefold())


def register_program(environment,filename,name):
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    item=read_environment(environment);path,kind=inspect_windows_file(filename)
    if kind=='MSI':raise ValueError('Escolha o EXE do programa instalado; MSI é um instalador.')
    if kind=='x64' and item['architecture']=='win32':raise ValueError('Este programa exige um ambiente de 64 bits.')
    name=clean_name(name)
    existing=next((entry for entry in programs(environment) if entry['file']==str(path)),None)
    identifier=existing['id'] if existing else str(uuid.uuid4())
    write_json(program_path(identifier),{'name':name,'environment':environment,'file':str(path)})
    desktop=program_desktop(identifier)
    desktop.parent.mkdir(parents=True,exist_ok=True)
    if desktop.is_symlink():raise ValueError('O arquivo de atalho não pode ser um link simbólico.')
    # Only a validated UUID enters Exec. User names and paths never become commands.
    escaped=name.replace('\\','\\\\')
    content=('[Desktop Entry]\nType=Application\nName='+escaped+'\n'
             'Comment=Programa Windows no ambiente Linux BR\n'
             'Exec=/usr/bin/linuxbr-windows --launch '+identifier+'\n'
             'Icon=application-x-executable\nTerminal=false\nCategories=Utility;\n'
             'Keywords=Windows;Wine;\nStartupNotify=false\n')
    desktop.write_text(content,encoding='utf-8')
    return identifier


def forget_program(identifier):
    read_program(identifier)
    desktop=program_desktop(identifier)
    if desktop.is_symlink():raise ValueError('O arquivo de atalho não pode ser um link simbólico.')
    desktop.unlink(missing_ok=True);program_path(identifier).unlink()


def discover_programs(identifier,limit=250):
    """Read EXE headers in installed-program folders; never follow directory links."""
    read_environment(identifier)
    drive=environment_path(identifier)/'prefix/drive_c'
    if not drive.is_dir() or drive.is_symlink():return []
    roots=[drive/'Program Files',drive/'Program Files (x86)']
    users=drive/'users'
    if users.is_dir() and not users.is_symlink():
        for user in users.iterdir():
            if user.is_dir() and not user.is_symlink():roots.append(user/'AppData/Local/Programs')
    result=[];seen=set();visited=0
    excluded=('unins','uninstall','setup','install','update','crash','report','vcredist','vc_redist','dxsetup')
    for root in roots:
        if not root.is_dir() or root.is_symlink():continue
        # AppData can contain Wine-created links to personal folders. Do not
        # traverse such an ancestor while discovering installed executables.
        if any(parent.is_symlink() for parent in root.parents if parent!=drive and parent.is_relative_to(drive)):continue
        resolved=root.resolve()
        for folder,directories,files in os.walk(root,followlinks=False):
            visited+=1
            if visited>2000:return result
            directories[:]=[name for name in directories if not (Path(folder)/name).is_symlink()
                            and name.casefold() not in ('common files','windows nt','windows media player','internet explorer')]
            for name in sorted(files):
                if not name.lower().endswith('.exe') or name.casefold().startswith(excluded):continue
                candidate=Path(folder)/name
                if candidate.is_symlink():continue
                try:
                    path,kind=inspect_windows_file(candidate)
                    if not path.is_relative_to(resolved) or str(path) in seen:continue
                except (OSError,ValueError):continue
                seen.add(str(path));result.append({'name':path.stem,'file':str(path),'kind':kind})
                if len(result)>=limit:return result
    return sorted(result,key=lambda item:item['name'].casefold())


def inspect_windows_file(filename):
    try:path=Path(filename).expanduser().resolve(strict=True)
    except FileNotFoundError:raise ValueError('Arquivo não encontrado. Selecione o programa novamente.') from None
    if not path.is_file() or path.suffix.lower() not in ('.exe','.msi'):
        raise ValueError('Selecione um arquivo EXE ou MSI local.')
    with path.open('rb') as stream:
        header=stream.read(64)
        if path.suffix.lower()=='.msi':
            if header[:8]!=bytes.fromhex('d0cf11e0a1b11ae1'):
                raise ValueError('O arquivo não tem o formato de um instalador MSI.')
            return path,'MSI'
        if len(header)<64 or header[:2]!=b'MZ':
            raise ValueError('O arquivo não é um executável Windows válido.')
        offset=struct.unpack_from('<I',header,60)[0]
        if offset<64 or offset>path.stat().st_size-6:
            raise ValueError('Cabeçalho do executável inválido.')
        stream.seek(offset); pe=stream.read(6)
        if pe[:4]!=b'PE\0\0':
            raise ValueError('Executáveis DOS/16 bits não são suportados por esta ferramenta.')
        machine=struct.unpack_from('<H',pe,4)[0]
        if machine not in (0x14c,0x8664):
            raise ValueError('Use a versão Windows x86 ou x64; ARM não é suportado.')
        return path,'x64' if machine==0x8664 else 'x86'


def command_for(action,filename=None):
    if action=='run':
        path,kind=inspect_windows_file(filename)
        return ['wine','msiexec','/i',str(path)] if kind=='MSI' else ['wine',str(path)]
    if action=='configure':return ['winecfg']
    if action=='uninstall':return ['wine','uninstaller']
    if action=='dependencies':return ['winetricks','--gui']
    if action=='stop':return ['wineserver','--kill']
    raise ValueError('Ação desconhecida.')


def run(identifier,action,filename=None):
    if os.geteuid()==0:raise ValueError('Execute como usuário normal, sem sudo.')
    item=read_environment(identifier); path=environment_path(identifier)
    command=command_for(action,filename)
    if action=='run' and item['architecture']=='win32' and inspect_windows_file(filename)[1]=='x64':
        raise ValueError('Este EXE exige um ambiente de 64 bits.')
    env=os.environ.copy()
    # Do not inherit DLL overrides or an unrelated Wine prefix from the launcher.
    for key in ('WINEPREFIX','WINEARCH','WINEDLLOVERRIDES','WINESERVER','WINELOADER'):
        env.pop(key,None)
    env.update(WINEPREFIX=str(path/'prefix'),WINEARCH=item['architecture'],WINEDEBUG='-all')
    if action=='stop':return subprocess.call(command,env=env,cwd=str(path))
    with (path/'initialization.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not (path/'prefix/system.reg').exists():
            subprocess.run(['wineboot','--init'],env=env,check=True)
            subprocess.run(['wineserver','--wait'],env=env,check=True)
    cwd=str(Path(filename).resolve().parent) if action=='run' else str(path)
    return subprocess.call(command,env=env,cwd=cwd)


def start_job(identifier,action,filename=None):
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    item=read_environment(identifier);command_for(action,filename)
    if action=='run' and item['architecture']=='win32' and inspect_windows_file(filename)[1]=='x64':
        raise ValueError('Este programa exige um ambiente de 64 bits.')
    job=str(uuid.uuid4())
    args=['/usr/bin/python3',str(Path(__file__).resolve()),identifier,action,'--job',job]
    if filename:args+=['--file',str(inspect_windows_file(filename)[0])]
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,start_new_session=True)
    return job


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('environment');parser.add_argument('action',choices=['run','configure','uninstall','dependencies','stop'])
    parser.add_argument('--file');parser.add_argument('--job',required=True)
    args=parser.parse_args()
    # A job id is a basename, never an arbitrary log/status path.
    if str(uuid.UUID(args.job))!=args.job:raise SystemExit('Job inválido.')
    root=data_root()/'jobs';root.mkdir(parents=True,exist_ok=True,mode=0o700)
    result={'finished':True,'code':1,'error':''}
    with (root/(args.job+'.log')).open('w',encoding='utf-8') as log:
        os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
        try:result['code']=run(args.environment,args.action,args.file)
        except (OSError,ValueError,subprocess.SubprocessError) as error:result['error']=str(error)
    write_json(root/(args.job+'.json'),result)
