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
from urllib.parse import urlsplit, urlunsplit, unquote

CATALOG = Path('/usr/share/linuxbr/webapps/catalog.json')

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
