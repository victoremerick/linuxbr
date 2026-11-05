"""Session launchers and integration with the desktop's existing services."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))


def state_home():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'linuxbr/desktop-flows'


def _write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise ValueError('O destino é um link. Revise a configuração antes de continuar.')
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as stream:
        temporary=Path(stream.name);stream.write(text)
    temporary.replace(path)


def _name(name):
    if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.desktop') or any(ord(c)<32 for c in name):
        raise ValueError('Nome de lançador inválido.')
    return name


def autostart_dirs():
    system=[Path(value)/'autostart' for value in os.environ.get('XDG_CONFIG_DIRS','/etc/xdg').split(':') if value and Path(value).is_absolute()]
    return [config_home()/'autostart']+system


def _entry(path):
    parser=configparser.ConfigParser(interpolation=None,strict=False)
    parser.optionxform=str
    try:parser.read_string(path.read_text(encoding='utf-8'))
    except configparser.Error as exc:raise ValueError('O lançador tem uma configuração inválida.') from exc
    if not parser.has_section('Desktop Entry'):raise ValueError('Lançador sem seção principal.')
    return parser


def _original_text(path):
    return path.read_bytes().decode('utf-8')


def _state(parser):
    entry=parser['Desktop Entry']
    if entry.get('Type','Application')!='Application':return False,'Tipo de lançador não compatível'
    if entry.get('Hidden','false').lower()=='true' or entry.get('X-GNOME-Autostart-enabled','true').lower()=='false':
        return False,'Desativado nesta conta'
    desktop=set(os.environ.get('XDG_CURRENT_DESKTOP','KDE').split(':'))
    only=set(filter(None,entry.get('OnlyShowIn','').split(';')))
    excluded=set(filter(None,entry.get('NotShowIn','').split(';')))
    if only and not desktop.intersection(only):return False,'Não se aplica a esta área de trabalho'
    if desktop.intersection(excluded):return False,'Excluído desta área de trabalho'
    command=entry.get('TryExec','')
    if command and not shutil.which(command):return False,'Executável exigido não encontrado'
    if not entry.get('Exec','').strip() and not entry.get('DBusActivatable','false').lower()=='true':
        return False,'Sem comando de inicialização'
    if entry.get('X-systemd-skip','false').lower()=='true':return False,'Gerenciado por outro mecanismo da sessão'
    if entry.get('AutostartCondition') or entry.get('X-KDE-autostart-condition'):
        return True,'Habilitado; depende de condição nativa'
    return True,'Habilitado para a próxima sessão'


def autostart_entries():
    entries={};directories=autostart_dirs()
    for directory in directories:
        try:paths=sorted(directory.glob('*.desktop'))
        except OSError:continue
        for path in paths:
            if path.name in entries:continue
            try:
                parser=_entry(path);entry=parser['Desktop Entry'];enabled,status=_state(parser)
                source='Conta atual' if directory==directories[0] else 'Padrão da sessão'
                entries[path.name]={'id':path.name,'name':entry.get('Name[pt_BR]',entry.get('Name[pt]',entry.get('Name',path.stem))),
                    'path':str(path),'origin':source,'enabled':enabled,'status':status,
                    'command':entry.get('Exec','Ativação por D-Bus'),
                    'configured':entry.get('Hidden','false').lower()!='true' and entry.get('X-GNOME-Autostart-enabled','true').lower()!='false',
                    'restorable':_snapshot_path(path.name).is_file(),
                    'editable':entry.get('X-systemd-skip','false').lower()!='true' and not (directory==directories[0] and path.is_symlink())}
            except (OSError,UnicodeError,configparser.Error,ValueError):
                entries[path.name]={'id':path.name,'name':path.stem,'path':str(path),'origin':'Configuração inválida',
                    'enabled':False,'configured':False,'status':'Não foi possível ler o lançador','command':'','restorable':False,'editable':False}
    return sorted(entries.values(),key=lambda entry:entry['name'].casefold())


def _snapshot_path(name):
    return state_home()/'autostart'/(_name(name)+'.json')


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def set_autostart(name, enabled):
    if os.geteuid()==0:raise ValueError('Altere a inicialização na sua conta, sem sudo.')
    _name(name)
    paths=[directory/name for directory in autostart_dirs()]
    source=next((path for path in paths if path.is_file()),None)
    if source is None:raise ValueError('O lançador não está mais disponível. Atualize a lista.')
    target=paths[0]
    if target.is_symlink():raise ValueError('O lançador da conta é um link. Use as preferências nativas para revisá-lo.')
    original=_original_text(source);parser=_entry(source)
    if parser.get('Desktop Entry','Type',fallback='Application')!='Application':
        raise ValueError('Somente lançadores de aplicativos da sessão podem ser alterados aqui.')
    if parser.get('Desktop Entry','X-systemd-skip',fallback='false').lower()=='true':
        raise ValueError('Este item é gerenciado por outro mecanismo da sessão. Consulte as preferências nativas; nenhum serviço foi alterado.')
    snapshot=_snapshot_path(name)
    if snapshot.exists():
        saved=json.loads(snapshot.read_text())
        if not target.exists() or _digest(_original_text(target))!=saved.get('written'):
            raise ValueError('O lançador mudou em outro programa. Restaure ou revise a configuração nativa antes de alterar novamente.')
    else:
        saved={'existed':target.is_file(),'original':_original_text(target) if target.is_file() else None}
    # Change only relevant keys, preserving comments, localized names and actions.
    lines=original.splitlines(keepends=True);section=False;found=False;output=[]
    values={'Hidden':'false' if enabled else 'true','X-GNOME-Autostart-enabled':'true' if enabled else 'false'}
    keys=dict(values);seen=set()
    for line in lines:
        if line.strip().startswith('['):
            if section:
                for key,value in keys.items():output.append(f'{key}={value}\n')
                keys={}
            section=line.strip()=='[Desktop Entry]';found=found or section
        key=line.partition('=')[0].strip()
        if section and key in values:
            if key not in seen:output.append(f'{key}={values[key]}\n');seen.add(key)
            keys.pop(key,None)
        else:output.append(line if line.endswith('\n') else line+'\n')
    if section:
        for key,value in keys.items():output.append(f'{key}={value}\n')
    if not found:raise ValueError('Lançador inválido.')
    text=''.join(output);saved['written']=_digest(text)
    _write(snapshot,json.dumps(saved,ensure_ascii=False,indent=2)+'\n');_write(target,text)


def restore_autostart(name):
    if os.geteuid()==0:raise ValueError('Restaure a inicialização na sua conta, sem sudo.')
    target=config_home()/'autostart'/_name(name);snapshot=_snapshot_path(name)
    if target.is_symlink():raise ValueError('O lançador é um link. Revise-o nas preferências nativas.')
    saved=json.loads(snapshot.read_text())
    if not target.is_file() or _digest(_original_text(target))!=saved.get('written'):
        raise ValueError('O lançador foi alterado fora desta tela. A restauração não substituirá essa edição.')
    if saved['existed']:_write(target,saved['original'])
    else:target.unlink()
    snapshot.unlink()


NATIVE={
    'search':['krunner'],
    'index':['kcmshell6','kcm_baloofile'],
    'search-settings':['kcmshell6','kcm_plasmasearch'],
    'shortcuts':['kcmshell6','kcm_keys'],
    'startup':['kcmshell6','kcm_autostart'],
    'session':['kcmshell6','kcm_smserver'],
    'defaults':['kcmshell6','kcm_componentchooser'],
    'filetypes':['kcmshell6','kcm_filetypes'],
    'notifications':['kcmshell6','kcm_notifications'],
    'files':['dolphin',str(Path.home())],
}


def launch_native(action, query=''):
    if action not in NATIVE:raise ValueError('Ação da área de trabalho inválida.')
    argv=list(NATIVE[action])
    if action=='search':
        if len(query)>1000 or any(ord(c)<32 for c in query):raise ValueError('Termo de busca inválido.')
        argv+=['--',query] if query else []
    binary=shutil.which(argv[0])
    if not binary:raise ValueError('O componente '+argv[0]+' não está instalado. Nenhuma configuração foi alterada.')
    argv[0]=binary
    return subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,start_new_session=True)


def indexing_status():
    command=shutil.which('balooctl6') or shutil.which('balooctl')
    if not command:return 'O controle do índice Baloo não está instalado. A busca de aplicativos continua disponível no KRunner.'
    try:
        result=subprocess.run([command,'status'],capture_output=True,text=True,timeout=5,check=False)
        return result.stdout.strip() or result.stderr.strip() or 'O serviço de indexação não informou seu estado.'
    except (OSError,subprocess.TimeoutExpired):return 'O serviço de indexação não respondeu. Abra as preferências de indexação para conferir.'


def _xdg(args):
    command=shutil.which('xdg-mime')
    if not command:raise ValueError('xdg-mime não está instalado. Use o editor de tipos de arquivo do KDE.')
    try:result=subprocess.run([command]+args,capture_output=True,text=True,timeout=10,check=False)
    except subprocess.TimeoutExpired as exc:raise ValueError('A consulta de associação não respondeu.') from exc
    if result.returncode:raise ValueError(result.stderr.strip() or 'A associação não pôde ser consultada ou alterada.')
    return result.stdout.strip()


def file_association(path):
    path=Path(path).resolve(strict=True)
    if not path.is_file():raise ValueError('Escolha um arquivo para consultar seu tipo.')
    mime=_xdg(['query','filetype',str(path)])
    if not re.fullmatch(r'[\w.+-]+/[\w.+-]+',mime):raise ValueError('O sistema não identificou o tipo deste arquivo.')
    return {'path':str(path),'mime':mime,'default':_xdg(['query','default',mime])}


def applications():
    directories=[Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'applications']
    directories += [Path(value)/'applications' for value in os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':') if value]
    entries={}
    for directory in directories:
        for path in directory.rglob('*.desktop'):
            identifier=str(path.relative_to(directory)).replace(os.sep,'-')
            if identifier in entries:continue
            try:
                parser=_entry(path);entry=parser['Desktop Entry']
                entries[identifier]=None
                if entry.get('Hidden','false').lower()=='true' or not entry.get('Exec',''):continue
                entries[identifier]={'id':identifier,'name':entry.get('Name[pt_BR]',entry.get('Name',path.stem)),
                    'types':entry.get('MimeType','').split(';'),'path':str(path)}
            except (OSError,UnicodeError,ValueError,configparser.Error):continue
    return sorted((entry for entry in entries.values() if entry),key=lambda entry:entry['name'].casefold())


def set_default(mime, identifier):
    if os.geteuid()==0:raise ValueError('Escolha aplicativos na sua conta, sem sudo.')
    if not re.fullmatch(r'[\w.+-]+/[\w.+-]+',mime):raise ValueError('Tipo de arquivo inválido.')
    _name(identifier)
    if not any(entry['id']==identifier for entry in applications()):raise ValueError('O aplicativo escolhido não está registrado nesta conta.')
    previous=_xdg(['query','default',mime])
    _xdg(['default',identifier,mime])
    if _xdg(['query','default',mime])!=identifier:
        raise ValueError('O sistema não confirmou a associação. Revise as prioridades no editor de tipos de arquivo do KDE.')
    return {'mime':mime,'previous':previous,'current':identifier}


def undo_default(change):
    if not change.get('previous'):raise ValueError('Não havia aplicativo padrão anterior. Ajuste a associação no editor de tipos do KDE.')
    if _xdg(['query','default',change['mime']])!=change['current']:
        raise ValueError('A associação mudou em outro programa. A edição mais recente foi preservada.')
    set_default(change['mime'],change['previous'])


def test_default(path):
    # Ask the desktop to open the explicitly selected file; never execute a command
    # constructed from a desktop entry in this process.
    command=shutil.which('xdg-open')
    if not command:raise ValueError('O abridor padrão xdg-open não está disponível.')
    path=Path(path).resolve(strict=True)
    return subprocess.Popen([command,str(path)],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)


SEARCH_ACTIONS=[
    ('Aplicativos na inicialização','startup','iniciar inicialização iniciar sistema startup msconfig programas sessão'),
    ('Indexação e pastas excluídas','index','buscar pesquisa procurar indexar índice exclusões baloo arquivos'),
    ('Preferências da pesquisa','search-settings','busca pesquisar krunner resultados aplicativos configurações'),
    ('Aplicativos padrão','defaults','padrão navegador email e-mail browser default aplicativos'),
    ('Tipos de arquivo e Abrir com','filetypes','extensão extensões abrir com associação pdf txt jpg programas'),
    ('Atalhos de teclado','shortcuts','atalhos teclado windows pesquisar win buscar'),
    ('Notificações e transferências','notifications','copiar cópias conflito fila progresso transferência pausar'),
]


def search_actions(query):
    import unicodedata
    def normalized(value):return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))
    terms=normalized(query).split()
    return [(label,action) for label,action,aliases in SEARCH_ACTIONS
            if all(term in normalized(label+' '+aliases) for term in terms)]
