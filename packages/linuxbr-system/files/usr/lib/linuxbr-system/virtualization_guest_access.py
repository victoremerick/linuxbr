"""Create an expiring standard account in a supported Linux lab guest."""

from datetime import date, timedelta
import json
import secrets
import time

WAIT_SECONDS = 12
TOOLS = {'create': '/usr/sbin/useradd', 'activate': '/usr/bin/chage', 'remove': '/usr/sbin/userdel'}


def expiration(value, today=None):
    today = today or date.today()
    try:
        selected = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Informe a data de expiração no formato AAAA-MM-DD.') from None
    if not today < selected <= today + timedelta(days=30):
        raise ValueError('Escolha uma data entre amanhã e os próximos 30 dias.')
    return selected.isoformat()


def agent(domain, execute, arguments=None):
    from libvirt_qemu import qemuAgentCommand

    request = {'execute': execute}
    if arguments is not None:
        request['arguments'] = arguments
    response = json.loads(qemuAgentCommand(domain, json.dumps(request), 5, 0))
    if 'return' not in response:
        raise RuntimeError('O agente do convidado não confirmou a operação.')
    return response['return']


def guest_exec(call, domain, action, arguments):
    process = call(domain, 'guest-exec', {'path': TOOLS[action], 'arg': arguments, 'capture-output': False})
    pid = process['pid']
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        result = call(domain, 'guest-exec-status', {'pid': pid})
        if result['exited']:
            return result.get('exitcode') == 0
        time.sleep(0.2)
    raise RuntimeError('O convidado não concluiu o gerenciamento da conta a tempo.')


def create(manager, identifier, expiry, call=agent):
    expires = expiration(expiry)
    domain = manager.domain(identifier)
    if not domain.isActive():
        raise ValueError('Inicie a VM e confira se o agente QEMU do convidado está em execução.')
    try:
        info = call(domain, 'guest-info')
        supported = {item['name'] for item in info['supported_commands'] if item.get('enabled')}
        if not {'guest-get-osinfo', 'guest-exec', 'guest-exec-status', 'guest-set-user-password'} <= supported:
            raise ValueError
        os_info = call(domain, 'guest-get-osinfo')
        if not os_info.get('kernel-release') or os_info.get('id') in ('mswindows', 'win32', 'windows'):
            raise ValueError
    except Exception:
        raise ValueError('O convidado precisa usar Linux com o agente QEMU e os comandos de contas habilitados.') from None

    username = 'laboratorio-' + secrets.token_hex(5)
    password = secrets.token_urlsafe(24)
    created = False
    try:
        # Stage the account expired. It remains unable to authenticate if password setup fails.
        created = guest_exec(call, domain, 'create', ['--expiredate', '1970-01-02',
                             '--create-home', '--user-group', '--shell', '/bin/bash', '--', username])
        if not created:
            raise ValueError
        domain.setUserPassword(username, password, 0)
        if not guest_exec(call, domain, 'activate', ['--expiredate', expires, '--', username]):
            raise ValueError
    except Exception:
        if created:
            try:
                guest_exec(call, domain, 'remove', ['--remove', '--', username])
            except Exception:
                pass
        raise RuntimeError('O convidado não confirmou a criação e a expiração da conta de laboratório.') from None
    return {'username': username, 'password': password, 'expires': expires}
