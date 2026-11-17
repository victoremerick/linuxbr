"""Processo privilegiado da primeira configuração, ativado pelo Calamares."""
import grp
import json
import os
import pwd
import re
import socket
import socketserver
import ssl
import stat
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo, available_timezones


STATE_DIR = Path('/var/lib/linuxbr/initial-setup')
RUNTIME = Path('/run/linuxbr-initial-setup')
SOCKET = RUNTIME / 'control.sock'
SDDM_CONFIG = Path('/etc/sddm.conf.d/99-linuxbr-initial-setup.conf')
SDDM_SESSION = Path('/usr/share/xsessions/linuxbr-initial-setup.desktop')
SESSION_TEMPLATE = Path('/usr/share/linuxbr/initial-setup/sddm.desktop')
KEYBOARD_DEFAULTS = Path('/etc/default/keyboard')
KEYBOARD_XORG = Path('/etc/X11/xorg.conf.d/00-keyboard.conf')
SSSD_CONFIG = Path('/etc/sssd/sssd.conf')
SETUP_USER = 'linuxbr-setup'
SETUP_HOME = Path('/var/lib/linuxbr/setup-user')
SETUP_CONFIG = (
    b'[General]\nDisplayServer=x11\n'
    b'[Autologin]\nUser=linuxbr-setup\nSession=linuxbr-initial-setup.desktop\nRelogin=true\n'
    b'[Users]\nRememberLastUser=false\nRememberLastSession=false\n'
)
STEPS = ('keyboard', 'network', 'timezone', 'account', 'apps')
KEYBOARDS = {'br': ('br', 'abnt2'), 'pt': ('pt', ''), 'us': ('us', ''),
             'us-intl': ('us', 'intl'), 'es': ('latam', '')}
LIMIT = 256 * 1024
NETWORK = 'org.freedesktop.NetworkManager'
NETWORK_PATH = '/org/freedesktop/NetworkManager'
DISCOVERY = 'https://linuxbr.homedeveloper.com.br/.well-known/linuxbr-webapps'
GEO_TIMEZONE = 'https://worldtimeapi.org/api/ip'
LOCAL_NAME = re.compile(r'[a-z][a-z0-9_-]{0,31}')


def command(argv, message, *, data=None, timeout=35):
    try:
        return subprocess.run(argv, input=data, capture_output=True, check=True, timeout=timeout,
                              env={'PATH': '/usr/sbin:/usr/bin', 'LC_ALL': 'C.UTF-8',
                                   'DEBIAN_FRONTEND': 'noninteractive'}).stdout
    except (OSError, subprocess.SubprocessError):
        raise ValueError(message) from None


def atomic_write(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_https(address):
    try:
        with urlopen(address, timeout=5, context=ssl.create_default_context()) as response:
            value = json.loads(response.read(512 * 1024))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def internet_available():
    return bool(read_https(DISCOVERY).get('schema'))


def app_rows():
    from store_backend import NATIVE_PACKAGES, catalog
    return [{'id': row['id'], 'name': row['name'], 'category': row['category'],
             'package': NATIVE_PACKAGES[row['id']]}
            for row in catalog() if row['kind'] == 'linux' and row['id'] in NATIVE_PACKAGES]


def local_user(name):
    for line in Path('/etc/passwd').read_text().splitlines():
        fields = line.split(':')
        if len(fields) == 7 and fields[0] == name:
            return fields
    return None


def allowed_account_name(value):
    name = str(value).strip()
    if not LOCAL_NAME.fullmatch(name) or name == SETUP_USER:
        raise ValueError('Use um nome de usuário com 1 a 32 caracteres, começando por uma letra minúscula.')
    return name


def checked_secret(value, field):
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(c in value for c in '\x00\r\n'):
        raise ValueError(f'Informe {field}.')
    return value


def verify_ldaps(host):
    try:
        with socket.create_connection((host, 636), timeout=8) as connection:
            with ssl.create_default_context().wrap_socket(connection, server_hostname=host):
                pass
    except ssl.SSLCertVerificationError:
        raise ValueError('O certificado LDAPS não é confiável para o servidor informado.') from None
    except OSError:
        raise ValueError('Não foi possível alcançar o servidor LDAPS na porta 636.') from None


def ldap_configuration(record):
    host, base, username = record['host'], record['base'], record['username']
    return f'''[sssd]
services = nss, pam
domains = {host}

[domain/{host}]
id_provider = ldap
auth_provider = ldap
access_provider = simple
simple_allow_users = {username}@{host}
ldap_uri = ldaps://{host}:636
ldap_search_base = {base}
ldap_schema = rfc2307
ldap_tls_reqcert = demand
ldap_tls_cacert = /etc/ssl/certs/ca-certificates.crt
use_fully_qualified_names = true
fallback_homedir = /home/%u@%d
default_shell = /bin/bash
min_id = 1000
cache_credentials = true
'''.encode()


def verified_domain_account(login, password, message):
    account = pwd.getpwnam(login)
    local_uids = {int(row.split(':')[2]) for row in Path('/etc/passwd').read_text().splitlines()
                  if row.count(':') == 6}
    if local_user(login) or account.pw_uid < 1000 or account.pw_uid in local_uids:
        raise ValueError('O identificador da conta corporativa coincide com uma conta local ou do sistema.')
    command(['/usr/bin/pamtester', 'sddm', login, 'authenticate', 'acct_mgmt'], message,
            data=(password + '\n').encode(), timeout=100)
    return account


class State:
    def __init__(self, folder=STATE_DIR):
        self.folder = folder
        self.path = folder / 'progress.json'
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            self.data = {'schema': 1}
        if self.data.get('schema') != 1:
            raise ValueError('Estado da configuração incompatível.')

    @property
    def next(self):
        return next((index for index, step in enumerate(STEPS) if step not in self.data), len(STEPS))

    def save(self, key, value):
        updated = dict(self.data, **{key: value})
        self.write(updated)

    def write(self, data):
        atomic_write(self.path, json.dumps(data, ensure_ascii=False).encode('utf-8') + b'\n')
        self.data = data

    def public(self):
        try:
            checks = json.loads((self.folder / 'live-checks.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            checks = {}
        result = {}
        if isinstance(checks, dict) and checks.get('schema') == 1:
            result = {key: checks[key] for key in ('keyboard', 'touchpad', 'audio', 'video')
                      if key in checks and (checks[key] is None or isinstance(checks[key], bool))}
        return {'state': self.data, 'next': self.next, 'live_checks': result}

    def complete(self):
        if self.next != len(STEPS):
            raise ValueError('Complete as etapas anteriores antes de liberar a tela de login.')
        os.replace(self.folder / 'pending', self.folder / 'complete')
        sync_directory(self.folder)


def network_api():
    import dbus
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object(NETWORK, NETWORK_PATH), NETWORK)
    return dbus, bus, manager


def get_properties(dbus, bus, path, interface):
    return dbus.Interface(bus.get_object(NETWORK, path), 'org.freedesktop.DBus.Properties').GetAll(interface, timeout=5)


def access_point(dbus, bus, device, path):
    data = get_properties(dbus, bus, path, NETWORK + '.AccessPoint')
    name = bytes(data['Ssid']).decode('utf-8', 'replace')
    security = int(data['WpaFlags']) | int(data['RsnFlags'])
    if not name:
        return None
    if security & 0x0100:
        key = 'wpa-psk'
    elif security & 0x0400:
        key = 'sae'
    elif not int(data['Flags']) & 1:
        key = ''
    else:
        return None
    return dict(name=name, device=str(device), path=str(path), key=key, strength=int(data['Strength']))


def networks(rescan=False):
    dbus, bus, manager = network_api()
    wifi = {}
    connected = []
    types = {1: 'Ethernet', 2: 'Wi-Fi'}
    for device in manager.GetDevices(timeout=5):
        info = get_properties(dbus, bus, device, NETWORK + '.Device')
        device_type = int(info['DeviceType'])
        if device_type in types and int(info['State']) == 100:
            connected.append(types[device_type])
        if device_type != 2:
            continue
        wireless = dbus.Interface(bus.get_object(NETWORK, device), NETWORK + '.Device.Wireless')
        if rescan:
            try:
                wireless.RequestScan({}, timeout=4)
            except dbus.DBusException:
                pass
        for path in wireless.GetAccessPoints(timeout=5):
            try:
                row = access_point(dbus, bus, device, path)
            except dbus.DBusException:
                continue
            if row:
                identity = row['name'], row['key']
                if row['strength'] > wifi.get(identity, {}).get('strength', -1):
                    wifi[identity] = row
    internet = bool(connected) and internet_available()
    if internet:
        status = f"Rede {', '.join(sorted(set(connected)))} conectada com acesso à internet."
    elif connected:
        status = f"Rede {', '.join(sorted(set(connected)))} conectada. A internet ainda não foi confirmada. Uma rede corporativa local pode continuar acessível."
    else:
        status = 'Nenhuma conexão Ethernet ou Wi-Fi ativa.'
    return {'wifi': sorted(wifi.values(), key=lambda row: (-row['strength'], row['name']))[:70],
            'internet': internet, 'status': status}


def connect_wifi(device, path, password):
    dbus, bus, manager = network_api()
    if not isinstance(device, str) or not isinstance(path, str) or device not in manager.GetDevices(timeout=5):
        raise ValueError('Atualize a lista de redes e selecione o Wi-Fi novamente.')
    info = get_properties(dbus, bus, device, NETWORK + '.Device')
    if int(info['DeviceType']) != 2:
        raise ValueError('A interface indicada não oferece Wi-Fi.')
    settings = dbus.Interface(bus.get_object(NETWORK, device), NETWORK + '.Device.Wireless')
    if path not in settings.GetAccessPoints(timeout=5):
        raise ValueError('A rede saiu do alcance. Atualize a lista e tente novamente.')
    network = access_point(dbus, bus, device, path)
    if network is None:
        raise ValueError('O modo de autenticação desta rede precisa ser configurado após o primeiro login.')
    wireless_state = get_properties(dbus, bus, device, NETWORK + '.Device.Wireless')
    if int(info['State']) == 100 and str(wireless_state.get('ActiveAccessPoint')) == path:
        return networks()
    connection = {'connection': {'type': '802-11-wireless', 'id': network['name'],
                                 'autoconnect': dbus.Boolean(True)}}
    if network['key']:
        password = checked_secret(password, 'a senha do Wi-Fi')
        connection['802-11-wireless-security'] = {'key-mgmt': network['key'], 'psk': password}
    profile = None
    try:
        profile, active, _ = manager.AddAndActivateConnection2(
            connection, device, path, {'persist': 'memory'}, timeout=18)
        profile_interface = dbus.Interface(bus.get_object(NETWORK, profile), NETWORK + '.Settings.Connection')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = int(get_properties(dbus, bus, active, NETWORK + '.Connection.Active')['State'])
            if state == 2:
                profile_interface.Save(timeout=6)
                break
            if state in (3, 4):
                raise ValueError('A ativação não foi confirmada.')
            time.sleep(0.45)
        else:
            raise ValueError('O prazo para conectar terminou.')
    except (dbus.DBusException, ValueError):
        if profile:
            try:
                dbus.Interface(bus.get_object(NETWORK, profile), NETWORK + '.Settings.Connection').Delete(timeout=5)
            except dbus.DBusException:
                pass
        raise ValueError('Não foi possível conectar. Confira a senha, o alcance e a segurança escolhida no roteador.') from None
    return networks()


def zones():
    common = ('America/Sao_Paulo', 'America/Manaus', 'America/Rio_Branco', 'America/Fortaleza',
              'America/Noronha', 'America/Belem', 'America/Cuiaba', 'America/Porto_Velho')
    values = available_timezones()
    return [zone for zone in common if zone in values] + sorted(values - set(common))


class Setup:
    def __init__(self, state):
        self.state = state
        self.progress = None

    def call(self, operation, args):
        if operation == 'state':
            return self.state.public()
        if operation == 'restart':
            command(['/usr/bin/systemctl', '--no-block', 'reboot'], 'Não foi possível solicitar o reinício.')
            return {}
        if operation == 'finish':
            return self.finish()
        if operation == 'profile':
            return self.load_profile(args.get('value'))
        if operation in ('networks', 'wifi', 'timezones', 'catalog'):
            index = {'networks': 1, 'wifi': 1, 'timezones': 2, 'catalog': 4}[operation]
            if index > self.state.next:
                raise ValueError('Complete as etapas anteriores.')
            if operation == 'networks':
                return networks(rescan=True)
            if operation == 'wifi':
                return connect_wifi(args.get('device'), args.get('access_point'), args.get('password'))
            if operation == 'timezones':
                values = zones()
                suggestion = read_https(GEO_TIMEZONE).get('timezone') if internet_available() else None
                return {'zones': values, 'suggested': suggestion if suggestion in values else None}
            return {'apps': app_rows() if internet_available() else []}
        if operation not in STEPS or STEPS.index(operation) > self.state.next:
            raise ValueError('Complete as etapas anteriores.')
        handlers = dict(keyboard=self.keyboard, network=self.network, timezone=self.timezone,
                        account=self.account, apps=self.apps)
        handlers[operation](args)
        return self.state.public()

    def load_profile(self, profile):
        if self.state.next != 0:
            raise ValueError('Importe predefinições antes de confirmar o teclado.')
        expected = {'schema', 'language', 'edition', 'keyboard', 'timezone', 'apps'}
        if (not isinstance(profile, dict) or set(profile) != expected or profile['schema'] != 1
                or profile['language'] != 'pt_BR' or profile['edition'] != 'desktop'):
            raise ValueError('O arquivo precisa ser um conjunto de predefinições do Linux BR Desktop.')
        keyboard, timezone, apps = profile['keyboard'], profile['timezone'], profile['apps']
        if not isinstance(keyboard, str) or keyboard not in KEYBOARDS:
            raise ValueError('O layout do arquivo não está disponível.')
        if not isinstance(timezone, str) or timezone not in available_timezones():
            raise ValueError('O fuso horário do arquivo não está disponível.')
        if not isinstance(apps, list) or len(apps) > 40 or not all(isinstance(item, str) for item in apps):
            raise ValueError('A lista de aplicativos do arquivo é inválida.')
        allowed = {row['id'] for row in app_rows()} if apps else set()
        if any(app not in allowed for app in apps):
            raise ValueError('A lista do arquivo contém aplicativos indisponíveis nesta versão.')
        self.state.save('profile', dict(profile, apps=list(dict.fromkeys(apps))))
        return self.state.public()

    def keyboard(self, args):
        layout = args.get('layout')
        if layout not in KEYBOARDS:
            raise ValueError('Escolha um layout da lista.')
        locale, variant = KEYBOARDS[layout]
        defaults = KEYBOARD_DEFAULTS.read_text(encoding='utf-8') if KEYBOARD_DEFAULTS.exists() else ''
        defaults = re.sub(r'^XKB(?:LAYOUT|VARIANT)=.*$', '', defaults, flags=re.MULTILINE).rstrip()
        values = f'{defaults}\nXKBLAYOUT="{locale}"\nXKBVARIANT="{variant}"\n'.lstrip()
        atomic_write(KEYBOARD_DEFAULTS, values.encode(), 0o644)
        keyboard = f'''Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "{locale}"
    Option "XkbModel" "pc105"
    Option "XkbVariant" "{variant}"
EndSection
'''
        atomic_write(KEYBOARD_XORG, keyboard.encode(), 0o644)
        self.state.save('keyboard', layout)

    def network(self, _):
        self.state.save('network', True)

    def timezone(self, args):
        zone = str(args.get('zone', '')).strip()
        if zone not in available_timezones():
            raise ValueError('Escolha um fuso horário válido.')
        ZoneInfo(zone)
        command(['/usr/bin/timedatectl', 'set-timezone', zone], 'Não foi possível aplicar o fuso horário.')
        self.state.save('timezone', zone)

    def account(self, args):
        if 'account' in self.state.data:
            return
        if args.get('mode') == 'ldap' and 'draft' not in self.state.data:
            self.join_ldap(args)
        elif args.get('mode') == 'local' and 'ldap_draft' not in self.state.data:
            self.create_local(args)
        elif args.get('mode') == 'ad' and not ({'draft', 'ldap_draft'} & self.state.data.keys()):
            self.join_domain(args)
        else:
            raise ValueError('Escolha um tipo de conta disponível.')

    def create_local(self, args):
        name = allowed_account_name(args.get('username', ''))
        full = str(args.get('display', '')).strip()
        if not full or len(full) > 128 or any(c in full for c in '\n\r\x00:'):
            raise ValueError('Informe o nome completo.')
        password = checked_secret(args.get('password'), 'a senha da conta local')
        record = self.state.data.get('draft')
        if record and (record['username'], record['display']) != (name, full):
            raise ValueError('Conclua a conta que já foi iniciada.')
        user = local_user(name)
        if record is None:
            try:
                pwd.getpwnam(name)
            except KeyError:
                pass
            else:
                raise ValueError('Já existe uma conta com este nome.')
            if (Path('/home') / name).exists() or (Path('/home') / name).is_symlink():
                raise ValueError('Já existe uma pasta pessoal com este nome.')
            uid = next((number for number in range(1000, 60000) if not uid_exists(number)), None)
            if uid is None:
                raise ValueError('Não foi possível reservar um identificador para a conta.')
            record = {'username': name, 'display': full, 'uid': uid}
            self.state.save('draft', record)
        if user is None:
            if (Path('/home') / name).exists() or (Path('/home') / name).is_symlink():
                raise ValueError('Já existe uma pasta pessoal com este nome.')
            try:
                command(['/usr/sbin/useradd', '--create-home', '--user-group', '--shell', '/bin/bash',
                         '--uid', str(record['uid']), '--groups', 'sudo', '--comment', full, '--', name],
                        'Não foi possível criar a conta local.')
            except ValueError:
                if local_user(name) is None:
                    self.state.write({key: val for key, val in self.state.data.items() if key != 'draft'})
                raise
            user = local_user(name)
        if not user or int(user[2]) != record['uid'] or user[4] != full or user[5] != f'/home/{name}':
            raise ValueError('A conta existente não corresponde à criação iniciada.')
        command(['/usr/sbin/chpasswd'], 'Não foi possível registrar a senha da conta.',
                data=f'{name}:{password}\n'.encode())
        updated = dict(self.state.data, account={'mode': 'local', 'login': name, 'uid': record['uid']})
        updated.pop('draft', None)
        self.state.write(updated)

    def join_domain(self, args):
        from accounts_backend import domain_name, execute
        domain = domain_name(str(args.get('domain', '')))
        login = str(args.get('login', '')).strip()
        if not login or len(login) > 253 or any(ord(c) < 32 for c in login):
            raise ValueError('Informe a conta corporativa a usar no login.')
        password = checked_secret(args.get('user_password'), 'a senha da conta corporativa')
        try:
            realm = execute(dict(action='discover', domain=domain))[0]
            if not realm['configured']:
                admin = str(args.get('admin', '')).strip()
                secret = checked_secret(args.get('password'), 'a senha de ingresso no domínio')
                realm = execute(dict(action='join', domain=domain, username=admin, password=secret))[0]
        except Exception:
            raise ValueError('Não foi possível verificar ou ingressar no Active Directory. Confira DNS, horário, credenciais e as permissões de ingresso.') from None
        for pattern in realm['formats']:
            if '%U' in pattern and '@' not in login and '\\' not in login:
                login = pattern.replace('%U', login).replace('%D', domain)
                break
        try:
            account = verified_domain_account(login, password,
                                              'O Active Directory ainda não autorizou o login desta conta. Confira o formato e a política de acesso.')
        except KeyError:
            raise ValueError('Informe a conta completa do domínio, por exemplo usuario@empresa.com.br.') from None
        self.state.save('account', {'mode': 'ad', 'login': login, 'uid': account.pw_uid, 'domain': domain})

    def join_ldap(self, args):
        from accounts_backend import domain_name
        host = domain_name(str(args.get('host', '')))
        base = str(args.get('base', '')).strip()
        if not 3 <= len(base) <= 384 or '=' not in base or '?' in base or any(ord(c) < 32 for c in base):
            raise ValueError('Informe a base de busca LDAP, por exemplo dc=empresa,dc=com,dc=br.')
        username = allowed_account_name(args.get('login', ''))
        password = checked_secret(args.get('user_password'), 'a senha da conta corporativa')
        record = dict(host=host, base=base, username=username)
        draft = self.state.data.get('ldap_draft')
        if draft and draft != record:
            raise ValueError('Conclua a configuração LDAP já iniciada.')
        content = ldap_configuration(record)
        if SSSD_CONFIG.is_symlink() or (SSSD_CONFIG.exists() and (not draft or SSSD_CONFIG.read_bytes() != content)):
            raise ValueError('O SSSD já está configurado. Use a página Organização depois do primeiro login para revisar a configuração.')
        if any(SSSD_CONFIG.parent.glob('conf.d/*.conf')):
            raise ValueError('O SSSD já possui configurações da organização.')
        verify_ldaps(host)
        self.state.save('ldap_draft', record)
        atomic_write(SSSD_CONFIG, content)
        login = f'{username}@{host}'
        try:
            command(['/usr/bin/systemctl', 'restart', 'sssd.service'], 'Não foi possível iniciar o cliente LDAP.')
            for _ in range(10):
                try:
                    account = verified_domain_account(login, password, 'O diretório LDAP recusou a senha ou a autorização.')
                    break
                except KeyError:
                    time.sleep(0.5)
            else:
                raise ValueError('O diretório não retornou a conta POSIX. Confira a base de busca e a permissão de leitura.')
            updated = dict(self.state.data, account={'mode': 'ldap', 'login': login, 'uid': account.pw_uid, 'domain': host})
            updated.pop('ldap_draft', None)
            self.state.write(updated)
        except (OSError, ValueError):
            command(['/usr/bin/systemctl', 'stop', 'sssd.service'], 'Não foi possível restaurar o estado do cliente LDAP.')
            if SSSD_CONFIG.read_bytes() == content:
                SSSD_CONFIG.unlink()
                sync_directory(SSSD_CONFIG.parent)
            self.state.write({key: value for key, value in self.state.data.items() if key != 'ldap_draft'})
            raise

    def apps(self, args):
        items = args.get('items', [])
        if not isinstance(items, list) or len(items) > 40 or not all(isinstance(item, str) for item in items):
            raise ValueError('A seleção de aplicativos é inválida.')
        catalog = {row['id']: row['package'] for row in app_rows()} if items else {}
        if any(item not in catalog for item in items):
            raise ValueError('Algum aplicativo selecionado ficou indisponível na Loja.')
        items = list(dict.fromkeys(items))
        self.state.save('requested_apps', items)
        installed = self.state.data.get('installed_apps', self.state.data.get('apps', [])).copy()
        deadline = time.monotonic() + 900
        try:
            for index, item in enumerate(items):
                self.progress = {'done': index, 'total': len(items), 'app': item}
                if item in installed:
                    continue
                command(['/usr/bin/apt-get', '-y', '--no-remove', '-o', 'DPkg::Lock::Timeout=30',
                         '-o', 'Acquire::Retries=1', '-o', 'Acquire::http::Timeout=15',
                         '-o', 'Acquire::https::Timeout=15',
                         'install', '--', catalog[item]],
                        'A instalação dos aplicativos não terminou. Confira a rede e tente novamente ou avance para usar a Loja depois.',
                        timeout=max(1, deadline - time.monotonic()))
                installed.append(item)
                self.state.save('installed_apps', installed.copy())
            self.state.save('apps', installed)
        finally:
            self.progress = None

    def finish(self):
        settings = self.state.data
        if self.state.next != len(STEPS):
            raise ValueError('Complete as etapas anteriores antes de liberar a tela de login.')
        account = settings['account']
        try:
            uid = pwd.getpwnam(account['login']).pw_uid
        except KeyError:
            raise ValueError('A conta selecionada ficou indisponível. Confira a conexão e tente novamente.') from None
        if uid != account['uid']:
            raise ValueError('A conta mudou durante o assistente.')
        if account['mode'] == 'local':
            status = command(['/usr/bin/passwd', '--status', account['login']],
                             'Não foi possível verificar a conta local.').split()
            if len(status) < 2 or status[1] != b'P':
                raise ValueError('A senha da conta local ainda não está configurada.')
        if not (self.state.folder / 'complete').is_file():
            self.state.complete()
        remove_autologin()
        command(['/usr/bin/systemctl', '--no-block', 'restart', 'sddm.service'],
                'Configuração concluída. Reinicie o computador para abrir a tela de login.')
        return {}


def uid_exists(number):
    try:
        pwd.getpwuid(number)
    except KeyError:
        return False
    return True


def setup_user():
    if not local_user(SETUP_USER):
        try:
            pwd.getpwnam(SETUP_USER)
        except KeyError:
            pass
        else:
            raise ValueError('O nome reservado ao assistente está em uso.')
        command(['/usr/sbin/useradd', '--system', '--user-group', '--create-home', '--home-dir',
                 str(SETUP_HOME), '--shell', '/usr/sbin/nologin', '--', SETUP_USER],
                'Não foi possível preparar a conta temporária do assistente.')
    info = pwd.getpwnam(SETUP_USER)
    if not 0 < info.pw_uid < 1000 or info.pw_dir != str(SETUP_HOME) or info.pw_shell != '/usr/sbin/nologin':
        raise ValueError('A conta do assistente não corresponde à configuração esperada.')
    if any(SETUP_USER in group.gr_mem for group in grp.getgrall()):
        raise ValueError('A conta temporária possui grupos adicionais.')
    return info


def remove_autologin():
    if not SDDM_CONFIG.is_symlink() and SDDM_CONFIG.is_file() and SDDM_CONFIG.read_bytes() == SETUP_CONFIG:
        SDDM_CONFIG.unlink()
        sync_directory(SDDM_CONFIG.parent)
    if (not SDDM_SESSION.is_symlink() and SDDM_SESSION.is_file()
            and SESSION_TEMPLATE.is_file() and SDDM_SESSION.read_bytes() == SESSION_TEMPLATE.read_bytes()):
        SDDM_SESSION.unlink()
        sync_directory(SDDM_SESSION.parent)


def put_autologin(path, value, mode):
    if path.is_symlink() or path.exists() and path.read_bytes() != value:
        raise ValueError('O arquivo reservado ao assistente já está em uso.')
    atomic_write(path, value, mode)


def notify_ready():
    path = os.environ.get('NOTIFY_SOCKET')
    if path:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as status:
            status.sendto(b'READY=1', path.replace('@', '\0', 1) if path.startswith('@') else path)


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(8)
        peer = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        _, uid, _ = struct.unpack('3i', peer)
        if uid != self.server.uid:
            return
        try:
            request = self.rfile.readline(LIMIT + 1)
            if len(request) > LIMIT or not request.endswith(b'\n'):
                return
            args = json.loads(request)
            operation = args.pop('operation')
            if operation == 'progress':
                value = self.server.setup.progress if (STATE_DIR / 'pending').is_file() else None
            else:
                with self.server.operation_lock:
                    if not (STATE_DIR / 'pending').is_file() and operation not in ('restart', 'finish'):
                        raise ValueError('A configuração inicial já foi concluída.')
                    value = self.server.setup.call(operation, args)
            result = {'ok': True, 'value': value}
        except ValueError as error:
            result = {'ok': False, 'error': str(error)}
        except Exception:
            result = {'ok': False, 'error': 'Não foi possível concluir a operação. Confira a conexão ou reinicie e tente novamente.'}
        try:
            self.connection.settimeout(8)
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode() + b'\n')
        except OSError:
            pass
        if result['ok'] and operation == 'finish':
            self.server.shutdown()


def main():
    marker = STATE_DIR / 'pending'
    try:
        details = marker.lstat()
    except FileNotFoundError:
        remove_autologin()
        notify_ready()
        return
    if not stat.S_ISREG(details.st_mode) or details.st_uid != 0 or details.st_mode & 0o022:
        raise SystemExit('Marcador do assistente inválido.')
    info = setup_user()
    state = State(STATE_DIR)
    SOCKET.unlink(missing_ok=True)
    try:
        with Server(str(SOCKET), Handler) as server:
            os.chown(SOCKET, info.pw_uid, info.pw_gid)
            os.chmod(SOCKET, 0o600)
            server.uid = info.pw_uid
            server.setup = Setup(state)
            server.operation_lock = threading.Lock()
            put_autologin(SDDM_SESSION, SESSION_TEMPLATE.read_bytes(), 0o644)
            put_autologin(SDDM_CONFIG, SETUP_CONFIG, 0o644)
            notify_ready()
            server.serve_forever()
    finally:
        SOCKET.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
