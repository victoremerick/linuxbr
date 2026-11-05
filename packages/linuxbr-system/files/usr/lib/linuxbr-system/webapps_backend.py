"""Per-user Chromium web apps. URLs and web metadata are always untrusted."""
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
import shlex
import shutil
import configparser
from urllib.parse import urlsplit, urlunsplit, unquote, quote

CATALOG = Path('/usr/share/linuxbr/webapps/catalog.json')
EXTENSION_ID = 'lhanpdfpjlicodjfidgojclnppokanbi'

def clean_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value) or '\\' in value:
        raise ValueError('Informe um endereço HTTPS válido, sem espaços.')
    parts = urlsplit(value)
    if parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Use HTTPS, sem senha no endereço e na porta padrão.')
    host = (parts.hostname or '').encode('idna').decode('ascii').lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '.' not in host or any(not label or len(label)>63 or label.startswith('-') or label.endswith('-') for label in host.split('.')):
        raise ValueError('Use o domínio público do aplicativo.')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Endereços IP não são aceitos como aplicativos sugeridos.')
    if host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
        raise ValueError('Use o domínio público do aplicativo.')
    path = parts.path or '/'
    if any(ord(c)<32 or ord(c)==127 for c in unquote(path)):
        raise ValueError('O endereço contém caracteres inválidos.')
    # Queries/fragments may contain temporary login tokens or document identifiers.
    return urlunsplit(('https', host, path, '', ''))

def clean_name(value):
    if not isinstance(value, str):
        raise ValueError('Nome inválido.')
    name = ' '.join(value.split())[:70]
    if not name or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Informe o nome do aplicativo.')
    return name

def catalog():
    return json.loads(CATALOG.read_text())['services']

def service_for(url):
    host = urlsplit(clean_url(url)).hostname
    return next((item for item in catalog() if host in item['hosts']), None)

def normalize_offer(data):
    url = clean_url(data.get('url', ''))
    service = service_for(url)
    if service:
        url = clean_url(service['url'])
    return {'url': url, 'name': clean_name(service['name'] if service else data.get('name', urlsplit(url).hostname)),
            'availability': service['availability'] if service else 'unknown',
            'source': service.get('source', '') if service else ''}

def root():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'linuxbr/webapps'

def apps_dir():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'applications'

def app_id(url, instance=''):
    suffix = '\0' + checked_id(instance) if instance else ''
    return hashlib.sha256((clean_url(url) + suffix).encode()).hexdigest()[:32]

def checked_id(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('Identificador de aplicativo inválido.')
    return value

def record_path(value):
    path = root()/checked_id(value)
    if path.is_symlink():
        raise ValueError('Diretório de aplicativo inválido.')
    return path

def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as out:
        out.write(value)
        temporary = Path(out.name)
    temporary.replace(path)

def read_record(value):
    directory = record_path(value)
    data = json.loads((directory/'app.json').read_text())
    data['url'] = clean_url(data['url']); data['name'] = clean_name(data['name'])
    if app_id(data['url'], data.get('instance', '')) != value:
        raise ValueError('Registro de aplicativo inconsistente.')
    data['session'] = clean_name(data.get('session', 'Principal'))
    data['id'] = value
    return data

def installed(include_hidden=False):
    items=[]
    for path in root().glob('*/app.json'):
        try:
            item=read_record(path.parent.name)
            if include_hidden or (apps_dir()/f'linuxbr-webapp-{item["id"]}.desktop').is_file():
                items.append(item)
        except (OSError, ValueError, KeyError):
            continue
    return sorted(items, key=lambda item:(item['name'].casefold(), item['session'].casefold()))

def sessions(url, include_hidden=False):
    canonical = normalize_offer({'url': url})['url']
    return [item for item in installed(include_hidden) if item['url'] == canonical]

def display_name(item):
    return item['name'] + ' — ' + item.get('session', 'Principal')

def desktop_escape(value):
    return value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')

def icon_path(item):
    from webapp_icons import cached
    icon = cached(item['url'])
    if icon: return icon
    identifier = item.get('id', '')
    if re.fullmatch('[a-f0-9]{32}', identifier):
        fallback = record_path(identifier)/'icon.svg'
        if fallback.is_file(): return fallback
    return Path('/usr/share/linuxbr/webapps/icon.png')

def prepare_icon(item):
    from webapp_icons import launcher_icon
    try:
        desktop = apps_dir()/f'linuxbr-webapp-{checked_id(item["id"])}.desktop'
        if not desktop.is_file(): return
        icon = launcher_icon(item['url'])
        expected = 'Icon=' + desktop_escape(str(icon))
        if expected not in desktop.read_text().splitlines():
            save_record(item['id'], item)
    except OSError:
        pass

def install(data):
    if os.geteuid()==0:
        raise ValueError('Instale aplicativos na sua conta, sem sudo.')
    item=normalize_offer(data)
    subscription=None
    if data.get('signed_source'):
        import signed_catalog
        app=signed_catalog.application(data['signed_source'],data.get('signed_app'))
        if clean_url(app['url'])!=item['url'] or app['status']!='published':
            raise ValueError('A origem assinada não corresponde ao aplicativo solicitado.')
        subscription=dict(source=data['signed_source'],app=app['id'],revision=app['revision'])
    item['session'] = clean_name(data.get('session', 'Principal'))
    item['instance'] = uuid.uuid4().hex if data.get('new_session', False) else ''
    if data.get('new_session', False) and any(app['session'].casefold() == item['session'].casefold()
                                               for app in sessions(item['url'], True)):
        raise ValueError('Já existe uma sessão com esse nome. Escolha outro nome ou restaure a sessão existente.')
    identifier=app_id(item['url'], item['instance']); directory=record_path(identifier)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (directory/'app.json').exists():
        # Reinstalling a legacy/default entry must retain its session and data.
        item = read_record(identifier)
    if subscription:item['catalog_subscription']=subscription
    save_record(identifier, item)
    from webapp_icons import request_refresh
    request_refresh(item['url'])
    return identifier

def save_record(identifier, item):
    if os.geteuid()==0:
        raise ValueError('Gerencie sessões na sua conta, sem sudo.')
    directory = record_path(identifier)
    atomic_write(directory/'app.json', json.dumps(item, ensure_ascii=False, indent=2)+'\n')
    icon=directory/'icon.svg'
    letter=html.escape(item['name'][0].upper())
    atomic_write(icon, f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><rect width="128" height="128" rx="28" fill="#6450a2"/><text x="64" y="88" text-anchor="middle" font-family="sans-serif" font-size="80" fill="white">{letter}</text></svg>')
    from webapp_icons import launcher_icon
    icon = launcher_icon(item['url'])
    atomic_write(apps_dir()/f'linuxbr-webapp-{identifier}.desktop',
        '[Desktop Entry]\nType=Application\nVersion=1.0\n'
        f'Name={desktop_escape(display_name(item))}\nComment=Aplicativo web instalado pelo Linux BR\n'
        f'Exec=/usr/bin/linuxbr-webapps --launch {identifier}\n'
        f'Icon={desktop_escape(str(icon))}\nTerminal=false\nCategories=Network;\nNoDisplay=true\n'
        f'StartupWMClass=linuxbr-webapp-{identifier}\nStartupNotify=true\n')
    atomic_write(apps_dir()/f'linuxbr-webapp-site-{app_id(item["url"])}.desktop',
        '[Desktop Entry]\nType=Application\n'
        f'Name={desktop_escape(item["name"])}\nExec=/usr/bin/linuxbr-webapps --open-app {identifier}\n'
        f'Icon={desktop_escape(str(icon))}\nTerminal=false\nCategories=Network;\n')
    if session_start_enabled(identifier):set_session_start(identifier,True)

def profile_context():
    """Identify only our dedicated Chromium profile through host ancestry."""
    pid=os.getppid()
    for _ in range(8):
        try:
            raw=Path(f'/proc/{pid}/cmdline').read_bytes().decode().rstrip('\0')
            args=raw.split('\0') if '\0' in raw else shlex.split(raw)
            for arg in args:
                if arg.startswith('--user-data-dir='):
                    profile=Path(arg.split('=',1)[1])
                    if profile.name=='profile' and profile.parent.parent==root():
                        return read_record(profile.parent.name)
            status=Path(f'/proc/{pid}/status').read_text()
            pid=int(next(line.split()[1] for line in status.splitlines() if line.startswith('PPid:')))
            if pid<=1:break
        except (OSError,ValueError,KeyError,StopIteration):break
    return None

def rename_session(identifier, name):
    item = read_record(identifier)
    name = clean_name(name)
    if any(app['id'] != identifier and app['session'].casefold() == name.casefold()
           for app in sessions(item['url'], True)):
        raise ValueError('Já existe uma sessão com esse nome.')
    item['session'] = name
    save_record(identifier, item)

def restore(identifier):
    save_record(identifier, read_record(identifier))

def launch(identifier):
    if os.geteuid()==0:
        raise ValueError('Abra aplicativos na sua conta, sem sudo.')
    item=read_record(identifier)
    from webapp_icons import request_refresh
    prepare_icon(item)
    request_refresh(item['url'])
    profile=record_path(identifier)/'profile'
    if profile.is_symlink():
        raise ValueError('Perfil do aplicativo inválido.')
    profile.mkdir(exist_ok=True, mode=0o700)
    return subprocess.Popen(['/usr/bin/chromium', '--user-data-dir='+str(profile),
        '--app='+item['url'], '--class=linuxbr-webapp-'+identifier,
        '--no-first-run', '--no-default-browser-check'], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def remove(identifier):
    item=read_record(identifier)
    set_session_start(identifier, False)
    (apps_dir()/f'linuxbr-webapp-{checked_id(identifier)}.desktop').unlink(missing_ok=True)
    if not sessions(item['url']):
        (apps_dir()/f'linuxbr-webapp-site-{app_id(item["url"])}.desktop').unlink(missing_ok=True)
    # Keep profile/login data so accidental removal is reversible by reinstalling.

def native_present(service):
    if not service:
        return False
    paths=[apps_dir(), Path('/usr/share/applications'),
           Path.home()/'.local/share/flatpak/exports/share/applications',
           Path('/var/lib/flatpak/exports/share/applications')]
    return any((directory/name).is_file() for directory in paths for name in service.get('desktop_ids', []))

def status(data):
    item=normalize_offer(data)
    return {'installed': any(app['url']==item['url'] for app in installed()),
            'native_installed':native_present(service_for(item['url'])), **item}


def running_profiles(items=None, proc_root=Path('/proc')):
    """Find our live Chromium profiles without reading tabs, cookies or accounts."""
    items = installed() if items is None else items
    profiles = {str(record_path(item['id'])/'profile'): item['id'] for item in items}
    running = set()
    if not profiles:
        return running
    try:
        processes = list(proc_root.iterdir())
    except OSError:
        return running
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.geteuid():
                continue
            with (process/'cmdline').open('rb') as stream:
                args = stream.read(65536).decode('utf-8', errors='replace').rstrip('\0').split('\0')
            if len(args)==1 and ' ' in args[0]:
                # Chromium can replace argv with a single process title. Match
                # our known paths directly so spaces in a profile stay intact.
                program, _, title = args[0].partition(' ')
                if Path(program).name not in ('chromium', 'chromium-browser', 'chrome'):
                    continue
                for directory, identifier in profiles.items():
                    match = re.search(r'(?:^|\s)--user-data-dir(?:=|\s+)'+re.escape(directory)+r'(?=\s--|$)', title)
                    if match:
                        remaining = title[:match.start()]+' '+title[match.end():]
                        if not re.search(r'(?:^|\s)--type=\S+', remaining):
                            running.add(identifier)
                continue
            if not args or Path(args[0]).name not in ('chromium', 'chromium-browser', 'chrome'):
                continue
            if any(arg.startswith('--type=') for arg in args):
                continue
            for index, arg in enumerate(args[1:], 1):
                directory = arg.split('=', 1)[1] if arg.startswith('--user-data-dir=') else (
                    args[index+1] if arg == '--user-data-dir' and index+1 < len(args) else None)
                if directory in profiles:
                    running.add(profiles[directory])
        except OSError:
            # Chromium can exit between reading its process directory and arguments.
            continue
    return running


def profile_states(items=None, proc_root=Path('/proc')):
    items = installed() if items is None else items
    running = running_profiles(items, proc_root)
    preferred = {url: preferred_profile(url) for url in {item['url'] for item in items}}
    return {item['id']: {'running': item['id'] in running,
                         'preferred': preferred[item['url']] == item['id']} for item in items}


def _profile_preferences():
    try:
        preferences = json.loads((root()/'preferences.json').read_text())
        return preferences if isinstance(preferences, dict) else {}
    except (OSError, ValueError):
        return {}


def preferred_profile(url):
    try:
        preferences=_profile_preferences()
        identifier=preferences.get(app_id(normalize_offer({'url':url})['url']))
        return identifier if any(item['id']==identifier for item in sessions(url)) else None
    except (OSError,ValueError,TypeError,AttributeError):
        return None


def set_preferred_profile(identifier):
    if os.geteuid()==0:raise ValueError('Gerencie perfis na sua conta, sem sudo.')
    item=read_record(identifier)
    if not any(entry['id']==identifier for entry in sessions(item['url'])):
        raise ValueError('Restaure o perfil antes de usá-lo como preferido.')
    preferences=_profile_preferences()
    preferences[app_id(item['url'])]=identifier
    atomic_write(root()/'preferences.json',json.dumps(preferences))


def clear_preferred_profile(identifier):
    if os.geteuid()==0:raise ValueError('Gerencie perfis na sua conta, sem sudo.')
    item=read_record(identifier)
    preferences=_profile_preferences()
    key=app_id(item['url'])
    if preferences.get(key)==identifier:
        preferences.pop(key)
        atomic_write(root()/'preferences.json',json.dumps(preferences))


def delete_profile(identifier):
    if os.geteuid()==0:raise ValueError('Gerencie perfis na sua conta, sem sudo.')
    item=read_record(identifier);directory=record_path(identifier)
    profile=directory/'profile'
    if profile.is_symlink():raise ValueError('Diretório de perfil inválido.')
    lock=profile/'SingletonLock'
    if lock.exists() or lock.is_symlink():
        raise ValueError('Feche todas as janelas deste perfil antes de apagar seus dados.')
    if identifier in running_profiles([item]):
        raise ValueError('Feche todas as janelas deste perfil antes de apagar seus dados.')
    remove(identifier)
    shutil.rmtree(directory)
    preferences=_profile_preferences()
    key=app_id(item['url'])
    if preferences.get(key)==identifier:
        preferences.pop(key)
        atomic_write(root()/'preferences.json',json.dumps(preferences))
    remaining=sessions(item['url'])
    if remaining:save_record(remaining[0]['id'],remaining[0])


def config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))


def session_start_path(identifier):
    return config_home()/'autostart'/f'linuxbr-webapp-{checked_id(identifier)}.desktop'


def profile_options(identifier):
    """Only launcher choices are stored here; Chromium owns its own preferences."""
    read_record(identifier)
    try:
        data=json.loads((record_path(identifier)/'launcher-preferences.json').read_text())
        mode=data.get('external_links', 'profile')
    except (OSError, ValueError, AttributeError):
        mode='profile'
    return {'external_links': mode if mode in ('profile','default-browser') else 'profile',
            'session_start': session_start_enabled(identifier)}


def session_start_enabled(identifier):
    path=session_start_path(identifier)
    if path.is_symlink():return False
    try:
        parser=configparser.ConfigParser(interpolation=None, strict=False)
        parser.read_string(path.read_text())
        return (parser.has_section('Desktop Entry') and
                parser.get('Desktop Entry','Hidden',fallback='false').casefold()!='true' and
                parser.get('Desktop Entry','X-GNOME-Autostart-enabled',fallback='true').casefold()!='false')
    except (OSError, ValueError, configparser.Error):return False


def set_session_start(identifier, enabled):
    if os.geteuid()==0:raise ValueError('Gerencie perfis na sua conta, sem sudo.')
    item=read_record(identifier);path=session_start_path(identifier)
    if path.is_symlink():raise ValueError('O lançador de inicialização é um link. Revise-o nas preferências da sessão.')
    if not enabled:
        path.unlink(missing_ok=True)
        return
    if not (apps_dir()/f'linuxbr-webapp-{identifier}.desktop').is_file():
        raise ValueError('Restaure o perfil no menu antes de iniciar com a sessão.')
    atomic_write(path, '[Desktop Entry]\nType=Application\n'
        f'Name={desktop_escape(display_name(item))}\n'
        f'Exec=/usr/bin/linuxbr-webapps --launch {identifier}\n'
        f'Icon={desktop_escape(str(icon_path(item)))}\n'
        'Terminal=false\nX-KDE-autostart-phase=2\n'
        'Comment=Abre este perfil ao entrar na sessão\n')


def save_profile_options(identifier, external_links='profile', session_start=False):
    if os.geteuid()==0:raise ValueError('Gerencie perfis na sua conta, sem sudo.')
    if external_links not in ('profile','default-browser'):
        raise ValueError('Tratamento de links inválido.')
    read_record(identifier)
    if external_links=='default-browser':default_browser()
    set_session_start(identifier, bool(session_start))
    atomic_write(record_path(identifier)/'launcher-preferences.json',
                 json.dumps({'external_links':external_links},ensure_ascii=False,indent=2)+'\n')


def open_profile_settings(identifier, section='site'):
    """Use the existing browser process and profile, including when already open."""
    if os.geteuid()==0:raise ValueError('Abra as preferências na sua conta, sem sudo.')
    item=read_record(identifier)
    origin='https://'+urlsplit(item['url']).netloc
    if section not in ('downloads','site','notifications','camera','microphone'):
        raise ValueError('Preferência de navegador inválida.')
    # Chromium on Linux accepts the extension page when joining an open profile.
    # The local page validates the request and opens the native settings tab.
    page=('chrome-extension://'+EXTENSION_ID+'/settings.html?section='+section+
          '&origin='+quote(origin,safe=''))
    profile=record_path(identifier)/'profile'
    if profile.is_symlink():raise ValueError('Perfil do aplicativo inválido.')
    profile.mkdir(exist_ok=True,mode=0o700)
    return subprocess.Popen(['/usr/bin/chromium','--user-data-dir='+str(profile),
        '--no-first-run','--no-default-browser-check','--new-window',page],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)


def _browser_entry(identifier):
    if not re.fullmatch(r'[A-Za-z0-9_.+-]+\.desktop',identifier):
        raise ValueError('Escolha um navegador em Aplicativos padrão antes de ativar esta opção.')
    paths=[apps_dir()]+[Path(value)/'applications' for value in os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':') if value]
    paths += [Path.home()/'.local/share/flatpak/exports/share/applications',Path('/var/lib/flatpak/exports/share/applications')]
    path=next((directory/identifier for directory in paths if (directory/identifier).is_file()),None)
    if not path:raise ValueError('O lançador do navegador padrão não está disponível.')
    parser=configparser.ConfigParser(interpolation=None,strict=False)
    try:
        parser.read_string(path.read_text())
        command=parser.get('Desktop Entry','Exec',fallback='')
        args=shlex.split(command)
    except (OSError,UnicodeError,configparser.Error,ValueError) as exc:raise ValueError('Não foi possível ler o lançador do navegador padrão.') from exc
    if (identifier.startswith('linuxbr-webapp') or not command or
        'linuxbr-webapps' in command or any(arg in ('--app','--app-id') or arg.startswith(('--app=','--app-id=')) for arg in args)):
        raise ValueError('O navegador padrão aponta para um aplicativo web. Escolha um navegador para evitar retorno ao mesmo perfil.')
    for index,arg in enumerate(args):
        profile=arg.split('=',1)[1] if arg.startswith('--user-data-dir=') else (args[index+1] if arg=='--user-data-dir' and index+1<len(args) else '')
        if profile and Path(profile).resolve().is_relative_to(root().resolve()):
            raise ValueError('O navegador padrão aponta para um perfil web dedicado. Escolha um navegador para evitar retorno ao mesmo perfil.')
    if parser.get('Desktop Entry','Hidden',fallback='false').casefold()=='true':
        raise ValueError('O navegador padrão está desativado.')
    return identifier


def default_browser(scheme=None):
    """Require an actual registered browser; refuse a route back to a web app."""
    try:
        result=subprocess.run(['xdg-settings','get','default-web-browser'],capture_output=True,
                              text=True,timeout=5,check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Não foi possível consultar o navegador padrão. Use Aplicativos padrão nas configurações.') from exc
    identifier=result.stdout.strip()
    if result.returncode:
        raise ValueError('Escolha um navegador em Aplicativos padrão antes de ativar esta opção.')
    _browser_entry(identifier)
    if scheme in ('http','https'):
        try:
            handler=subprocess.run(['xdg-mime','query','default','x-scheme-handler/'+scheme],
                                   capture_output=True,text=True,timeout=5,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:raise ValueError('Não foi possível conferir o aplicativo associado a este tipo de link.') from exc
        if handler.returncode or not handler.stdout.strip():
            raise ValueError('Escolha um navegador para links '+scheme.upper()+' em Aplicativos padrão.')
        _browser_entry(handler.stdout.strip())
    return identifier


def external_url(identifier, value):
    item=read_record(identifier)
    if not isinstance(value,str) or len(value)>8192 or any(ord(char)<33 or ord(char)==127 for char in value) or '\\' in value:
        raise ValueError('Endereço externo inválido.')
    parsed=urlsplit(value)
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Somente links HTTP e HTTPS sem credenciais podem abrir no navegador padrão.')
    # Validate the port while retaining the full query needed by the clicked link.
    try:parsed.port
    except ValueError as exc:raise ValueError('Porta do endereço inválida.') from exc
    service=service_for(item['url'])
    hosts=set(service.get('hosts',[])) if service else set()
    hosts.add(urlsplit(item['url']).hostname)
    if parsed.hostname in hosts:raise ValueError('Este link pertence ao aplicativo e deve permanecer neste perfil.')
    return value


def open_external(identifier, value):
    if os.geteuid()==0:raise ValueError('Abra links na sua conta, sem sudo.')
    if profile_options(identifier)['external_links']!='default-browser':
        raise ValueError('Este perfil mantém os links no próprio aplicativo.')
    url=external_url(identifier,value)
    default_browser(urlsplit(url).scheme)
    # xdg-open uses the registered default without supplying this dedicated profile.
    # The browser entry is checked above so a webapp handler cannot reopen itself.
    return subprocess.Popen(['xdg-open',url],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
