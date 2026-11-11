"""Optional native package providers for the desktop store."""
import http.client
import json
import os
from pathlib import Path
import platform
import re
import socket
import stat
import subprocess
import threading
import time
from urllib.parse import quote, urlencode
from urllib.request import urlopen


POLICY = Path('/etc/linuxbr/store-optional-sources.json')
SNAP = Path('/usr/bin/snap')
SNAP_SOCKET = Path('/run/snapd.socket')
BREW_PREFIX = Path('/home/linuxbrew/.linuxbrew')
BREW_API = 'https://formulae.brew.sh/api/formula'
PROVIDERS = {
    'snap': ('Snap Store', 'system', 'https://snapcraft.io/store'),
    'brew': ('Homebrew Core', 'user', 'https://formulae.brew.sh/formula/'),
}
NAMES = {
    'snap': re.compile(r'(?=[a-z0-9-]{2,40}$)(?=.*[a-z])[a-z0-9]+(?:-[a-z0-9]+)*'),
    'brew': re.compile(r'[a-z0-9][a-z0-9+_.-]{0,79}(?:@[a-z0-9][a-z0-9_.-]{0,39})?'),
}
_catalog_lock = threading.Lock()
_catalog = (0, [])


def preferences():
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return config / 'linuxbr/store-optional-sources.json'


def read_flags(path):
    with path.open('rb') as stream:
        data = stream.read(4097)
    if len(data) > 4096:
        raise ValueError('Configuração de fontes opcionais muito grande.')
    value = json.loads(data)
    if not isinstance(value, dict) or any(
            key not in PROVIDERS or not isinstance(flag, bool) for key, flag in value.items()):
        raise ValueError('Configuração de fontes opcionais inválida.')
    return value


def allowed(manager):
    if manager not in PROVIDERS:
        return False
    try:
        info = POLICY.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            return False
        return read_flags(POLICY).get(manager, True)
    except FileNotFoundError:
        return not POLICY.is_symlink()
    except (OSError, ValueError):
        return False


def enabled(manager):
    if not allowed(manager):
        return False
    try:
        return read_flags(preferences()).get(manager, False)
    except (OSError, ValueError):
        return False


def set_enabled(manager, value):
    from store_sources import atomic_write

    if manager not in PROVIDERS or (value and not allowed(manager)):
        raise ValueError('A organização bloqueou esta fonte na Loja.')
    path = preferences()
    try:
        flags = read_flags(path)
    except FileNotFoundError:
        flags = {}
    flags[manager] = bool(value)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(path, json.dumps(flags).encode(), 0o600)


def brew_binary():
    """Use the standard prefix only, under the account that owns it."""
    uid = os.geteuid()
    try:
        prefix = BREW_PREFIX.resolve(strict=True)
        executable = (prefix / 'bin/brew').resolve(strict=True)
        if (uid and prefix == BREW_PREFIX and executable.is_relative_to(prefix)
                and prefix.stat().st_uid == uid and executable.stat().st_uid == uid
                and executable.is_file() and os.access(executable, os.X_OK)):
            return str(prefix / 'bin/brew')
    except (OSError, RuntimeError):
        pass
    raise ValueError('Use a conta proprietária do Homebrew no prefixo padrão do Linux.')


def brew_environment():
    keep = {'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME',
            'https_proxy', 'http_proxy', 'no_proxy', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY'}
    env = {key: value for key, value in os.environ.items() if key in keep}
    env['PATH'] = '/usr/bin:/bin'
    env.update(HOMEBREW_NO_ANALYTICS='1', HOMEBREW_NO_AUTO_UPDATE='1', HOMEBREW_NO_SUDO='1',
               HOMEBREW_NO_INSTALL_CLEANUP='1', HOMEBREW_NO_INSTALL_UPGRADE='1',
               HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK='1')
    return env


class SnapConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(str(SNAP_SOCKET))


def snap_get(path, **params):
    conn = SnapConnection('localhost', timeout=8)
    try:
        conn.request('GET', path + ('?' + urlencode(params) if params else ''))
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError('O snapd recusou a consulta.')
        content = response.read(4 * 1024 * 1024 + 1)
        if len(content) > 4 * 1024 * 1024:
            raise ValueError('Resposta do snapd acima do limite permitido.')
        data = json.loads(content)
        if not isinstance(data, dict) or data.get('type') != 'sync':
            raise ValueError('Resposta do snapd inválida.')
        return data['result']
    except (OSError, KeyError, http.client.HTTPException) as error:
        raise ValueError('Snap Store indisponível. Confira se o snapd está ativo.') from error
    finally:
        conn.close()


def brew_query(*args):
    try:
        result = subprocess.run([brew_binary(), *args], check=True, capture_output=True,
                                timeout=15, env=brew_environment())
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise ValueError('Não foi possível consultar o Homebrew desta conta.') from error


def brew_api(url):
    with urlopen(url, timeout=8) as response:
        if not response.geturl().startswith(BREW_API):
            raise ValueError('Endereço do catálogo Homebrew inesperado.')
        data = response.read(48 * 1024 * 1024 + 1)
    if len(data) > 48 * 1024 * 1024:
        raise ValueError('Catálogo Homebrew acima do limite permitido.')
    return json.loads(data)


def brew_catalog():
    global _catalog
    with _catalog_lock:
        if time.monotonic() >= _catalog[0]:
            rows = brew_api(BREW_API + '.json')
            if not isinstance(rows, list):
                raise ValueError('Catálogo Homebrew inválido.')
            _catalog = time.monotonic() + 900, rows
        return _catalog[1]


def text(value, fallback=''):
    return value[:500] if isinstance(value, str) and value.strip() else fallback


def valid_row(manager, row):
    if not isinstance(row, dict):
        return False
    name = row.get('name')
    if not isinstance(name, str) or not NAMES[manager].fullmatch(name):
        return False
    if manager == 'snap':
        return (row.get('type') == 'app' and row.get('confinement') in ('strict', 'classic')
                and not row.get('devmode') and not row.get('jailmode'))
    return row.get('tap') == 'homebrew/core' and row.get('disabled') is not True


def has_linux_bottle(row):
    tag = {'x86_64': 'x86_64_linux', 'aarch64': 'arm64_linux'}.get(platform.machine())
    try:
        return bool(tag and tag in row['bottle']['stable']['files'])
    except (KeyError, TypeError):
        return False


def snap_system_info():
    try:
        info = snap_get('/v2/system-info')
        return info if isinstance(info, dict) else {}
    except ValueError:
        return {}


def snap_support(info):
    confinement = info.get('confinement')
    if confinement == 'strict':
        return True, ''
    if confinement == 'partial':
        features = info.get('sandbox-features')
        apparmor = features.get('apparmor') if isinstance(features, dict) else None
        if isinstance(apparmor, list) and any(level in apparmor for level in (
                'support-level:partial', 'support-level:full')):
            return True, ('O snapd informa confinamento parcial neste kernel. '
                          'O gerenciador aplica perfis de isolamento mais permissivos.')
        return False, 'Confira o AppArmor do sistema. O snapd ainda precisa confirmar suporte utilizável de isolamento.'
    return False, 'A Loja precisa confirmar o suporte do snapd neste sistema.'


def entry(manager, row, installed=False, *, snap_info=None):
    name = row['name']
    origin, scope, _ = PROVIDERS[manager]
    if manager == 'snap':
        display_name = ' '.join(text(row.get('title'), name).split())[:200] or name
        description = text(row.get('summary'), 'Aplicativo Snap.')
        confinement = row['confinement']
        channel = text(row.get('tracking-channel') if installed else row.get('channel'),
                       'stable' if not installed else 'não informado')
        version = text(row.get('version'), 'não informada')
        revision = text(str(row['revision']) if row.get('revision') is not None else '', 'não informada')
        publisher = row.get('publisher')
        publisher = text(publisher.get('display-name') or publisher.get('username')) if isinstance(publisher, dict) else text(row.get('developer'))
        note = ('Confinamento classic: acesso ampliado ao sistema.' if confinement == 'classic'
                else 'O pacote declara confinamento strict. Atualizações automáticas seguem a configuração do snapd.')
        label = f'{origin} · sistema · {name} · {channel} · {confinement} · revisão {revision}'
        source = 'https://snapcraft.io/' + name
        category = 'Fontes configuradas'
    else:
        display_name = name
        description = text(row.get('desc'), 'Ferramenta de terminal.')
        versions = row.get('versions')
        version = text(versions.get('stable') if isinstance(versions, dict) else row.get('current_version'), 'não informada')
        if installed and isinstance(row.get('installed'), list):
            observed = [text(item.get('version')) for item in row['installed'] if isinstance(item, dict)]
            version = ', '.join(filter(None, observed)) or version
        confinement = ''
        publisher = 'Homebrew Core'
        note = ('Ferramenta de terminal. O Homebrew instala comandos em /home/linuxbrew/.linuxbrew/bin. '
                'Consulte a fórmula para saber o nome do comando e se ela usa outro caminho.')
        label = f'{origin} · sua conta · {name} · {version}'
        source = 'https://formulae.brew.sh/formula/' + quote(name, safe='@')
        category = 'Ferramentas de terminal'
    result = {
        'id': manager + ':' + name, 'name': display_name, 'kind': 'linux', 'category': category,
        'description': description, 'source': source, 'note': note, 'version': version, 'keywords': name,
        'publisher': publisher, 'icon': 'package-x-generic' if manager == 'snap' else 'utilities-terminal',
        'optional_target': dict(manager=manager, target=name, scope=scope, origin=origin,
                                installed=installed, confinement=confinement, label=label, name=display_name),
    }
    if manager == 'snap':
        result.update(channel=channel, revision=revision)
        if snap_info is not None:
            supported, detail = snap_support(snap_info)
            if detail and (confinement == 'strict' or not supported):
                result['note'] += ' ' + detail
                field = 'confinement_note' if supported else 'blocked_reason'
                result['optional_target'][field] = detail
    return result


def provider_inventory(manager, *, snap_info=None):
    refresh_note = ''
    if manager == 'snap':
        rows = snap_get('/v2/snaps')
        if snap_info is None:
            snap_info = snap_system_info()
        refresh = snap_info.get('refresh')
        if isinstance(refresh, dict):
            refresh_note = ' '.join(label + ' ' + text(refresh.get(key)) + '.'
                for key, label in (('last', 'Última atualização automática'),
                                   ('next', 'Próxima atualização automática'),
                                   ('hold', 'Atualizações adiadas até'),
                                   ('timer', 'Horários configurados')) if text(refresh.get(key)))
    else:
        rows = brew_query('info', '--json=v1', '--installed')
    if not isinstance(rows, list):
        raise ValueError('O gerenciador retornou uma biblioteca inválida.')
    entries = [entry(manager, row, installed=True, snap_info=snap_info)
               for row in rows if valid_row(manager, row)]
    if refresh_note:
        for item in entries:
            item['note'] += ' ' + refresh_note
    return entries


def inventory():
    entries, errors = [], []
    for manager, (name, _, _) in PROVIDERS.items():
        if enabled(manager):
            try:
                entries.extend(provider_inventory(manager))
            except (OSError, ValueError) as error:
                errors.append(f'{name} · {error}')
    return entries, errors


def sources():
    rows = []
    for manager, (name, scope, url) in PROVIDERS.items():
        active = enabled(manager)
        status = 'Bloqueada pela organização' if not allowed(manager) else ''
        detail = ''
        confinement = ''
        if not status:
            if manager == 'snap':
                if not SNAP.is_file() or not SNAP_SOCKET.exists():
                    status = 'Configure o snapd'
                elif active:
                    info = snap_system_info()
                    confinement = info.get('confinement')
                    supported, detail = snap_support(info)
                    if detail:
                        status = ('Confinamento parcial' if supported else 'Confinamento a verificar')
            else:
                try:
                    brew_binary()
                except ValueError:
                    status = 'Configure o Homebrew na sua conta'
            if status:
                status = ('Habilitada' if active else 'Desabilitada') + ' · ' + status
        row = dict(kind=name, name=name, scope=scope, url=url, enabled=active,
                   optional_manager=manager, status=status)
        if detail:
            row.update(content=detail, confinement=confinement)
        rows.append(row)
    return rows


def snap_launch(target):
    name = target['target']
    if not enabled('snap') or not NAMES['snap'].fullmatch(name) or not target['installed']:
        return None
    directory = Path('/var/lib/snapd/desktop/applications')
    desktop = [path for path in directory.glob(name + '_*.desktop')
               if path.is_file() and not path.is_symlink() and path.stat().st_uid == 0
               and not path.stat().st_mode & 0o022]
    return ['/usr/bin/gio', 'launch', str(desktop[0])] if len(desktop) == 1 else None


def search(query):
    entries, errors = [], []
    for manager, (name, _, _) in PROVIDERS.items():
        if not enabled(manager):
            continue
        try:
            snap_info = snap_system_info() if manager == 'snap' else None
            installed = {item['id']: item for item in provider_inventory(manager, snap_info=snap_info)}
            if manager == 'snap':
                candidates = snap_get('/v2/find', q=query)
            else:
                term = query.casefold()
                candidates = [row for row in brew_catalog() if valid_row(manager, row)
                              and has_linux_bottle(row) and (term in row['name']
                              or term in text(row.get('desc')).casefold())]
            if not isinstance(candidates, list):
                raise ValueError('A fonte retornou um catálogo inválido.')
            for row in candidates[:80]:
                if valid_row(manager, row):
                    item = entry(manager, row, snap_info=snap_info)
                    entries.append(installed.get(item['id'], item))
        except (OSError, ValueError) as error:
            errors.append(f'{name} · {error}')
    return entries, errors


def updates():
    targets, errors = [], []
    for manager, (name, _, _) in PROVIDERS.items():
        if not enabled(manager):
            continue
        try:
            if manager == 'snap':
                rows = snap_get('/v2/find', select='refresh')
            else:
                data = brew_query('outdated', '--formula', '--json=v2')
                rows = data.get('formulae') if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError('A lista de atualizações não pôde ser identificada.')
            installed = {item['optional_target']['target']: item for item in provider_inventory(manager)}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item = installed.get(text(row.get('name')))
                if item and not row.get('pinned'):
                    targets.append(item['optional_target'])
        except (OSError, ValueError) as error:
            errors.append(f'{name} · {error}')
    return targets, errors


def available_entry(manager, name):
    if not enabled(manager) or not NAMES[manager].fullmatch(name):
        raise ValueError('A fonte não está habilitada ou o aplicativo é inválido.')
    if manager == 'brew':
        row = brew_api(BREW_API + '/' + quote(name, safe='@') + '.json')
        if valid_row(manager, row) and row['name'] == name and has_linux_bottle(row):
            return entry(manager, row)
        raise ValueError('A fórmula oficial não tem pacote Linux para esta arquitetura.')
    rows = snap_get('/v2/find', name=name)
    row = next((item for item in rows if valid_row(manager, item) and item['name'] == name), None) if isinstance(rows, list) else None
    if row is None:
        raise ValueError('O aplicativo não está disponível na Snap Store.')
    return entry(manager, row)


def require_snap_support():
    supported, detail = snap_support(snap_system_info())
    if not supported:
        raise ValueError(detail)
    return detail


def command(request):
    manager, action, name = (request[key] for key in ('manager', 'action', 'target'))
    if not enabled(manager):
        raise ValueError('A fonte não está habilitada ou foi bloqueada pela organização.')
    origin, scope, _ = PROVIDERS[manager]
    if request['origin'] != origin or request['scope'] != scope or not NAMES[manager].fullmatch(name):
        raise ValueError('Destino da fonte inválido.')
    installed = {item['optional_target']['target']: item for item in provider_inventory(manager)}
    if (action == 'install') == (name in installed):
        raise ValueError('O estado da instalação mudou. Atualize a Loja antes de repetir.')
    if manager == 'brew':
        if action != 'remove':
            available_entry(manager, name)
        verb = {'install': 'install', 'update': 'upgrade', 'remove': 'uninstall'}[action]
        return [brew_binary(), verb, '--formula', 'homebrew/core/' + name], brew_environment()
    verb = {'install': 'install', 'update': 'refresh', 'remove': 'remove'}[action]
    argv = ['/usr/bin/pkexec', str(SNAP), verb]
    if action == 'install':
        row = available_entry(manager, name)['optional_target']
        if row['confinement'] != request['confinement']:
            raise ValueError('O confinamento do Snap mudou. Revise a opção de instalação.')
        argv.append('--stable')
        if row['confinement'] == 'classic':
            if request.get('classic_confirmed') is not True:
                raise ValueError('O acesso ampliado do Snap classic precisa de confirmação.')
            argv.append('--classic')
    else:
        row = installed[name]['optional_target']
        if action == 'update' and row['confinement'] != request['confinement']:
            raise ValueError('O confinamento do Snap mudou. Atualize a Loja antes de repetir.')
    if action != 'remove':
        require_snap_support()
    return argv + [name], None
