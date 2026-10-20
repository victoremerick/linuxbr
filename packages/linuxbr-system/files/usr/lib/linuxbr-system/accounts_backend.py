"""Unprivileged AccountsService/realmd client. Secrets travel only over stdin/D-Bus."""
import json
import re
import sys
from pathlib import Path

PREFIX = 'org.freedesktop.realmd'
ROOT = '/org/freedesktop/realmd'


def domain_name(value):
    value = value.strip().lower().rstrip('.')
    if len(value) > 253 or '.' not in value or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
        for part in value.split('.')
    ):
        raise ValueError('Informe o domínio DNS completo, por exemplo empresa.com.br.')
    return value


def execute(request):
    import dbus
    bus = dbus.SystemBus()
    def interface(path, name):
        return dbus.Interface(bus.get_object(PREFIX, path), PREFIX + '.' + name)
    def props(path, name):
        return dbus.Interface(bus.get_object(PREFIX, path), 'org.freedesktop.DBus.Properties').GetAll(PREFIX + '.' + name)
    def record(path):
        p = props(path, 'Realm')
        return dict(path=str(path), name=str(p['Name']), configured=bool(p['Configured']),
                    formats=list(map(str, p['LoginFormats'])), policy=str(p['LoginPolicy']))
    action = request['action']
    if action == 'users':
        manager = dbus.Interface(bus.get_object('org.freedesktop.Accounts', '/org/freedesktop/Accounts'), 'org.freedesktop.Accounts')
        rows = []
        limits = dict(re.findall(r'^\s*(UID_MIN|UID_MAX)\s+(\d+)', Path('/etc/login.defs').read_text(), re.MULTILINE))
        minimum, maximum = int(limits.get('UID_MIN', 1000)), int(limits.get('UID_MAX', 60000))
        # Read local passwd explicitly; never enumerate corporate NSS accounts.
        for line in Path('/etc/passwd').read_text().splitlines():
            fields = line.split(':')
            if len(fields) != 7 or not minimum <= int(fields[2]) <= maximum:
                continue
            path = manager.FindUserByName(fields[0])
            p = dbus.Interface(bus.get_object('org.freedesktop.Accounts', path), 'org.freedesktop.DBus.Properties').GetAll('org.freedesktop.Accounts.User')
            if p['LocalAccount'] and not p['SystemAccount']:
                rows.append(dict(name=str(p['UserName']), full=str(p['RealName']), admin=bool(p['AccountType']), locked=bool(p['Locked'])))
        return rows
    if action == 'realms':
        return [record(p) for p in props(ROOT, 'Provider')['Realms'] if props(p, 'Realm')['Configured']]
    domain = domain_name(request['domain'])
    options = dbus.Dictionary({'server-software': 'active-directory', 'client-software': 'sssd'}, signature='sv')
    if action in ('discover', 'join'):
        _, paths = interface(ROOT, 'Provider').Discover(domain, options, timeout=120)
        matches = [p for p in paths if str(props(p, 'Realm')['Name']).lower() == domain]
    elif action == 'leave':
        matches = [p for p in props(ROOT, 'Provider')['Realms'] if str(props(p, 'Realm')['Name']).lower() == domain and props(p, 'Realm')['Configured']]
    else:
        raise ValueError('Operação desconhecida.')
    if not matches:
        raise ValueError('Domínio não encontrado. Confira o DNS da empresa, a conexão/VPN e o nome informado.')
    path = matches[0]
    if action == 'discover':
        return [record(path)]
    member = props(path, 'KerberosMembership')
    supported = member['SupportedJoinCredentials' if action == 'join' else 'SupportedLeaveCredentials']
    if ('password', 'administrator') not in [tuple(map(str, x)) for x in supported]:
        raise ValueError('Este domínio não oferece autenticação por senha administrativa nesta operação.')
    username, password = request.get('username', '').strip(), request.get('password', '')
    if not username or not password:
        raise ValueError('Informe a conta autorizada do domínio e sua senha.')
    credential = dbus.Struct(('password', 'administrator', dbus.Struct((username, password), signature='ss', variant_level=1)), signature='ssv')
    opts = dbus.Dictionary({}, signature='sv')
    if action == 'join':
        if props(path, 'Realm')['Configured']:
            raise ValueError('O computador já está conectado a esse domínio.')
        opts['membership-software'] = 'adcli'
        ou = request.get('ou', '').strip()
        if ou:
            opts['computer-ou'] = ou
    method = interface(path, 'KerberosMembership').Join if action == 'join' else interface(path, 'KerberosMembership').Leave
    method(credential, opts, timeout=600)
    return [record(path)]


def main():
    request = {}
    try:
        request = json.loads(sys.stdin.read(65536))
        result = {'ok': True, 'data': execute(request)}
    except Exception as error:
        message = str(error)
        for key in ('password',):
            if request.get(key):
                message = message.replace(request[key], '[oculto]')
        result = {'ok': False, 'error': message}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
