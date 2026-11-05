"""User-owned Wine environments. Never execute a shell or run Wine as root."""
import argparse
import fcntl
import json
import ntpath
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import struct
import subprocess
import tempfile
import time
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


def program_icon_path(identifier):
    program_path(identifier)
    directory=data_root()/'icons'
    if directory.is_symlink():raise ValueError('A pasta de ícones não pode ser um link simbólico.')
    path=directory/(identifier+'.ico')
    if path.is_symlink():raise ValueError('O ícone não pode ser um link simbólico.')
    return path


def program_icon(identifier):
    try:
        path=program_icon_path(identifier)
        return str(path) if path.is_file() else 'wine'
    except ValueError:return 'wine'


def valid_icon(value):
    """Reject truncated or oversized extracted ICO files before registering them."""
    if len(value)<22 or len(value)>16*1024*1024 or value[:4]!=b'\0\0\1\0':return False
    count=struct.unpack_from('<H',value,4)[0]
    if not 1<=count<=256 or len(value)<6+16*count:return False
    for index in range(count):
        size,offset=struct.unpack_from('<II',value,6+16*index+8)
        if not size or offset<6+16*count or offset+size>len(value):return False
    return True


def bounded_tool_output(argv,limit,timeout):
    """Read one local tool with bounded output and elapsed time."""
    process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)
    output=bytearray();deadline=time.monotonic()+timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:return None
                for _key,_events in selector.select(remaining):
                    value=os.read(process.stdout.fileno(),min(8192,limit+1-len(output)))
                    if not value:
                        return bytes(output) if process.wait(timeout=max(.01,deadline-time.monotonic()))==0 else None
                    output.extend(value)
                    if len(output)>limit:return None
    except (OSError,subprocess.TimeoutExpired):return None
    finally:
        if process.poll() is None:process.kill()
        process.wait();process.stdout.close()


def primary_icon_resource(path):
    listing=bounded_tool_output(['/usr/bin/wrestool','--list','--type=14','--',str(path)],65536,4)
    if listing is None:return None
    candidates=[]
    for line in listing.decode('utf-8',errors='replace').splitlines():
        try:tokens=shlex.split(line)
        except ValueError:continue
        names=[value.removeprefix('--name=') for value in tokens if value.startswith('--name=')]
        languages=[value.split('=',1)[1] for value in tokens if value.startswith(('--language=','--lang='))]
        if '--type=14' not in tokens or len(names)!=1 or len(languages)!=1:continue
        name=names[0];language=languages[0]
        if not name or len(name)>256 or any(ord(value)<32 or ord(value)==127 for value in name):continue
        if not language.isdecimal() or not 0<=int(language)<=65535:continue
        # Windows application icons conventionally start with numeric resource 1.
        # Explicit names and languages prevent a later group replacing that icon.
        numeric=name.isdecimal()
        rank=(0 if name=='1' else 1 if numeric else 2,int(name) if numeric else name.casefold(),int(language))
        candidates.append((rank,'--name='+name,'--language='+language))
    if not candidates:return None
    _rank,name,language=min(candidates,key=lambda item:item[0])
    return [name,language]


def extract_program_icon(identifier,filename):
    """Read PE icon resources with local icoutils; never run the executable."""
    destination=program_icon_path(identifier)
    try:
        path,kind=inspect_windows_file(filename)
        if kind not in ('x64','x86') or path.stat().st_size>256*1024*1024:return program_icon(identifier)
        resource=primary_icon_resource(path)
        if not resource:return program_icon(identifier)
        value=bounded_tool_output(['/usr/bin/wrestool','--extract','--type=14',*resource,'--',str(path)],16*1024*1024,8)
        if value is None or not valid_icon(value):return program_icon(identifier)
        destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with tempfile.TemporaryDirectory(prefix='.extract-',dir=destination.parent) as temporary:
            output=Path(temporary)/'program.ico'
            output.write_bytes(value)
            os.chmod(output,0o600);os.replace(output,destination)
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return program_icon(identifier)


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
    if kind in ('MSI','BAT','CMD'):raise ValueError('Escolha o EXE do programa instalado para criar um atalho.')
    if kind=='x64' and item['architecture']=='win32':raise ValueError('Este programa exige um ambiente de 64 bits.')
    name=clean_name(name)
    existing=next((entry for entry in programs(environment) if entry['file']==str(path)),None)
    identifier=existing['id'] if existing else str(uuid.uuid4())
    write_json(program_path(identifier),{'name':name,'environment':environment,'file':str(path)})
    icon=extract_program_icon(identifier,path)
    desktop=program_desktop(identifier)
    desktop.parent.mkdir(parents=True,exist_ok=True)
    if desktop.is_symlink():raise ValueError('O arquivo de atalho não pode ser um link simbólico.')
    # Only a validated UUID enters Exec. User names and paths never become commands.
    escaped=name.replace('\\','\\\\')
    content=('[Desktop Entry]\nType=Application\nName='+escaped+'\n'
             'Comment=Programa Windows no ambiente Linux BR\n'
             'Exec=/usr/bin/linuxbr-windows --launch '+identifier+'\n'
             'Icon='+icon.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')+'\nTerminal=false\nCategories=Utility;\n'
             'Keywords=Windows;Wine;\nStartupNotify=false\n')
    desktop.write_text(content,encoding='utf-8')
    return identifier


def forget_program(identifier):
    read_program(identifier)
    desktop=program_desktop(identifier)
    if desktop.is_symlink():raise ValueError('O arquivo de atalho não pode ser um link simbólico.')
    desktop.unlink(missing_ok=True);program_path(identifier).unlink()
    program_icon_path(identifier).unlink(missing_ok=True)


def compatibility_guidance(filename):
    basename=Path(filename).name.casefold() if filename else ''
    if basename in ('7z.exe','7zfm.exe','7zg.exe') or re.fullmatch(r'7z\d+[^/]*\.exe',basename):
        return ('7-Zip: teste compactar, extrair e abrir os formatos de que precisa. '
                'O Ark já oferece compactação no Linux. Associações de arquivos do Wine não substituem '
                'automaticamente as do gerenciador de arquivos. Versão e documentação: https://www.7-zip.org/')
    if basename.startswith('openttd'):
        return ('OpenTTD: existe edição Linux. Confira a versão e os arquivos gráficos, de som e música '
                'do jogo. Uma partida iniciada não comprova áudio, rede ou desempenho gráfico. '
                'Downloads e documentação: https://www.openttd.org/')
    return ('Confira os requisitos e a edição do programa no site do fornecedor. Prefira Linux ou web '
            'quando disponíveis. Use um ambiente separado para bibliotecas específicas. '
            'Drivers Windows, DRM e antitrapaças podem impedir a execução. '
            'Relatos por versão: https://appdb.winehq.org/')


def diagnose_program(environment,filename=None,code=None,error='',log=''):
    """Create a local, read-only diagnosis without executing the selected EXE."""
    item=read_environment(environment);directory=environment_path(environment)
    lines=['Diagnóstico do programa Windows','Ambiente: '+item['name'],
        'Arquitetura do ambiente: '+item['architecture'],
        'Wine: '+('encontrado' if shutil.which('wine') else 'não instalado'),
        'Ambiente preparado: '+('sim' if (directory/'prefix/system.reg').is_file() else 'ainda não')]
    if filename:
        lines.append('Programa: '+str(Path(filename)))
        try:
            _path,kind=inspect_windows_file(filename);lines.append('Formato: '+kind)
            if item['architecture']=='win32' and kind=='x64':lines.append('Ação: use um ambiente de 64 bits para este EXE.')
        except (OSError,ValueError) as failure:lines.append('Arquivo: '+str(failure))
    if code is not None:
        lines.append('Código de saída: '+str(code))
        if code==0:lines.append('O processo retornou sucesso; isso não confirma todas as funções do programa.')
        elif code in (3010,1641):lines.append('O instalador solicitou reinicialização; salve o trabalho e reabra este ambiente.')
    if error:lines.append('Erro registrado: '+str(error)[:2000])
    sample=(str(error)+'\n'+str(log)).casefold()
    if any(marker in sample for marker in ('import_dll','c0000135','module not found','msvcp','vcruntime')):
        lines.append('Indício de biblioteca ausente. Consulte os requisitos do fornecedor e Dependências neste ambiente; evite DLLs avulsas.')
    if any(marker in sample for marker in ('c000007b','bad exe format','wrong architecture')):
        lines.append('Indício de mistura de arquiteturas. Confira EXE, bibliotecas e ambiente x86/x64.')
    if any(marker in sample for marker in ('vulkan','dxvk','d3d11','d3d12')):
        lines.append('O registro menciona gráficos. Confira o driver, o suporte Vulkan e as bibliotecas de 32 bits; a menção isolada não prova a causa.')
    lines.extend(['',compatibility_guidance(filename),
        '', 'Este diagnóstico lê a configuração e o registro local. Nenhuma biblioteca foi instalada ou ajuste alterado.'])
    return '\n'.join(lines)


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
    if not path.is_file() or path.suffix.lower() not in ('.exe','.msi','.bat','.cmd'):
        raise ValueError('Selecione um arquivo EXE, MSI, BAT ou CMD local.')
    if path.suffix.lower() in ('.bat','.cmd'):
        # CMD expands percent expressions even inside quotes. Reject ambiguous
        # path characters rather than interpolating a filename as instructions.
        if any(c in str(path) for c in '%"\r\n\0'):
            raise ValueError('Renomeie o arquivo e as pastas: o caminho não pode conter %, aspas ou quebras de linha.')
        with path.open('rb') as stream:sample=stream.read(8192)
        if b'\0' in sample:
            raise ValueError('O BAT/CMD precisa ser texto sem caracteres nulos.')
        return path,path.suffix[1:].upper()
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
        if kind in ('BAT','CMD'):
            return ['wine','cmd','/d','/v:off','/c','linuxbr-script.cmd']
        return ['wine','msiexec','/i',str(path)] if kind=='MSI' else ['wine',str(path)]
    if action=='configure':return ['winecfg']
    if action=='uninstall':return ['wine','uninstaller']
    if action=='dependencies':return ['winetricks','--gui']
    if action=='stop':return ['wineserver','--kill']
    raise ValueError('Ação desconhecida.')


def _run(identifier,action,filename=None):
    if os.geteuid()==0:raise ValueError('Execute como usuário normal, sem sudo.')
    item=read_environment(identifier); path=environment_path(identifier)
    command=command_for(action,filename)
    if action=='run' and item['architecture']=='win32' and inspect_windows_file(filename)[1]=='x64':
        raise ValueError('Este EXE exige um ambiente de 64 bits.')
    env=os.environ.copy()
    # Do not inherit DLL overrides or an unrelated Wine prefix from the launcher.
    for key in ('WINEPREFIX','WINEARCH','WINEDLLOVERRIDES','WINESERVER','WINELOADER'):
        env.pop(key,None)
    env.update(WINEPREFIX=str(path/'prefix'),WINEARCH=item['architecture'],WINEDEBUG='-all,err+module,err+seh')
    if action=='stop':return subprocess.call(command,env=env,cwd=str(path))
    with (path/'initialization.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not (path/'prefix/system.reg').exists():
            subprocess.run(['wineboot','--init'],env=env,check=True)
            subprocess.run(['wineserver','--wait'],env=env,check=True)
    cwd=str(Path(filename).resolve().parent) if action=='run' else str(path)
    if action=='run' and inspect_windows_file(filename)[1] in ('BAT','CMD'):
        converted=subprocess.check_output(['winepath','-w',str(Path(filename).resolve())],env=env,text=True).strip()
        if not converted or any(c in converted for c in '%"\r\n'):
            raise ValueError('Não foi possível converter o caminho do script com segurança.')
        # Wine reconstructs a Windows command line from Unix argv. A private
        # dispatcher avoids quoting a user filename through that extra layer.
        with tempfile.TemporaryDirectory(prefix='batch-',dir=path) as temporary:
            wrapper=Path(temporary)/'linuxbr-script.cmd'
            # Unicode values enter through the process environment, avoiding
            # the OEM encoding used when CMD reads a batch file.
            env.update(LINUXBR_BATCH_FILE=converted,LINUXBR_BATCH_DIR=ntpath.dirname(converted))
            wrapper.write_bytes(b'@echo off\r\ncd /d "%LINUXBR_BATCH_DIR%" || exit /b 12\r\n"%LINUXBR_BATCH_FILE%"\r\n')
            return subprocess.call(command,env=env,cwd=temporary)
    return subprocess.call(command,env=env,cwd=cwd)


def run(identifier,action,filename=None):
    if os.geteuid()==0:raise ValueError('Execute como usuário normal, sem sudo.')
    path=environment_path(identifier);read_environment(identifier)
    if action=='stop':return _run(identifier,action,filename)
    lock_path=path/'maintenance.lock'
    if lock_path.is_symlink():raise ValueError('Registro de bloqueio inválido.')
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Este ambiente está em manutenção. Aguarde a conclusão.') from None
        return _run(identifier,action,filename)


def start_job(identifier,action,filename=None):
    if os.geteuid()==0:raise ValueError('Execute sem sudo.')
    item=read_environment(identifier);command_for(action,filename)
    if action=='run' and item['architecture']=='win32' and inspect_windows_file(filename)[1]=='x64':
        raise ValueError('Este programa exige um ambiente de 64 bits.')
    job=str(uuid.uuid4())
    args=['/usr/bin/python3',str(Path(__file__).resolve()),identifier,action,'--job',job]
    if filename:args+=['--file',str(inspect_windows_file(filename)[0])]
    if action=='run' and inspect_windows_file(filename)[1] in ('BAT','CMD'):
        args=['konsole','--hold','-e',*args,'--interactive']
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,start_new_session=True)
    return job


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('environment');parser.add_argument('action',choices=['run','configure','uninstall','dependencies','stop'])
    parser.add_argument('--file');parser.add_argument('--job',required=True)
    parser.add_argument('--interactive',action='store_true')
    args=parser.parse_args()
    # A job id is a basename, never an arbitrary log/status path.
    if str(uuid.UUID(args.job))!=args.job:raise SystemExit('Job inválido.')
    root=data_root()/'jobs';root.mkdir(parents=True,exist_ok=True,mode=0o700)
    result={'finished':True,'code':1,'error':''}
    if args.interactive:
        (root/(args.job+'.log')).write_text('Script aberto em uma janela de terminal para permitir entrada pelo teclado.\n',encoding='utf-8')
        try:result['code']=run(args.environment,args.action,args.file)
        except (OSError,ValueError,subprocess.SubprocessError) as error:result['error']=str(error)
        with (root/(args.job+'.log')).open('a',encoding='utf-8') as log:
            log.write('Código de saída: '+str(result['code'])+'\n'+result['error']+'\n')
        write_json(root/(args.job+'.json'),result)
        print('\nScript concluído. Código de saída:',result['code'])
        if result['error']:print(result['error'])
        raise SystemExit(result['code'])
    with (root/(args.job+'.log')).open('w',encoding='utf-8') as log:
        os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
        try:result['code']=run(args.environment,args.action,args.file)
        except (OSError,ValueError,subprocess.SubprocessError) as error:result['error']=str(error)
    write_json(root/(args.job+'.json'),result)
