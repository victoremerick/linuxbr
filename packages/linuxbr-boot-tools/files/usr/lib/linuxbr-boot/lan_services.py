"""Generate an opt-in, interface-scoped DNS and DHCPv4 service."""

import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile


DEFINITION = Path('/etc/linuxbr/lan-services.json')
RUNTIME = Path('/run/linuxbr-lan/dnsmasq.conf')
UNIT = 'linuxbr-lan-services.service'
DNSMASQ = '/usr/sbin/dnsmasq'
LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')
MAC = re.compile(r'(?:[a-f0-9]{2}:){5}[a-f0-9]{2}')


def render(config, addresses):
    interface = config['interface']
    if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,14}', interface)
            or interface == 'lo' or interface.startswith(('virbr', 'docker', 'veth', 'podman'))
            or not addresses):
        raise ValueError('Escolha uma interface LAN com IPv4 estático.')
    subnet = ipaddress.IPv4Network(config['subnet'])
    served = {interface_ip.ip for interface_ip in addresses if interface_ip.network == subnet}
    if subnet.prefixlen > 30 or len(served) != 1:
        raise ValueError('Escolha a sub-rede IPv4 configurada na interface.')
    server = next(iter(served))
    domain = config['domain'].lower()
    if not domain or len(domain) > 200 or len(domain.split('.')) < 2 or not all(
            LABEL.fullmatch(label) for label in domain.split('.')):
        raise ValueError('Informe um domínio local, por exemplo rede.home.arpa.')
    rows = ['interface=' + interface, 'except-interface=lo', 'bind-interfaces', 'no-hosts',
            'domain-needed', 'bogus-priv', 'domain=' + domain, 'local=/' + domain + '/',
            'listen-address=' + str(server), 'user=nobody', 'group=nogroup']

    def ip(value):
        address = ipaddress.IPv4Address(value)
        if address not in subnet or address in (subnet.network_address, subnet.broadcast_address):
            raise ValueError('O endereço precisa ser utilizável dentro da sub-rede.')
        return address

    scope = config['scope']
    start = end = gateway = None
    if scope:
        if not isinstance(scope, list) or len(scope) != 3:
            raise ValueError('Informe início, fim e gateway do DHCP.')
        start, end = ip(scope[0]), ip(scope[1])
        gateway = ip(scope[2]) if scope[2] else None
        if start > end or any(start <= value <= end for value in (server, gateway) if value is not None):
            raise ValueError('A faixa deve estar em ordem e excluir o servidor e o gateway.')
        rows.extend([f'dhcp-range={start},{end},{subnet.netmask},12h',
                     f'dhcp-option=option:router{"," + str(gateway) if gateway else ""}',
                     'dhcp-option=option:dns-server,' + str(server)])
    names = set()
    addresses_reserved = set()
    macs = set()
    if not isinstance(config['records'], list) or len(config['records']) > 250:
        raise ValueError('Use até 250 nomes ou reservas.')
    for record in config['records']:
        hostname = record['name'].lower()
        address = ip(record['address'])
        mac = record.get('mac', '').lower()
        if not LABEL.fullmatch(hostname) or hostname in names:
            raise ValueError('Os nomes locais devem ser únicos e conter letras, números ou hífen.')
        names.add(hostname)
        rows.append(f'host-record={hostname}.{domain},{address}')
        if mac:
            if (start is None or not MAC.fullmatch(mac) or mac in macs or int(mac[:2], 16) & 1
                    or mac == '00:00:00:00:00:00' or address in addresses_reserved
                    or address in (server, gateway) or start <= address <= end):
                raise ValueError('Cada reserva exige um MAC unicast único e um IP fora da faixa dinâmica.')
            macs.add(mac)
            addresses_reserved.add(address)
            rows.append(f'dhcp-host={mac},{address},{hostname}')
    return '\n'.join(rows) + '\n'


def command(*argv, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True, timeout=30)


def live_config(config):
    interface = config['interface']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,14}', interface):
        raise ValueError('Interface inválida.')
    if not (Path('/sys/class/net') / interface / 'device').exists():
        raise ValueError('Selecione uma interface LAN física.')
    data = json.loads(command('/usr/sbin/ip', '-j', '-4', 'address', 'show', 'dev', interface).stdout)
    addresses = [ipaddress.IPv4Interface(f'{item["local"]}/{item["prefixlen"]}')
                 for link in data for item in link['addr_info']
                 if item.get('scope') == 'global' and not item.get('dynamic')]
    return render(config, addresses)


def apply(config, target=DEFINITION, save_definition=True):
    if os.geteuid() != 0:
        raise PermissionError('A alteração exige autorização administrativa.')
    if not Path(DNSMASQ).is_file():
        raise ValueError('Instale Serviços DNS e DHCP da rede local em Funções do servidor.')
    fd = os.open(DEFINITION.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not save_definition:
            config = json.loads(DEFINITION.read_text(encoding='utf-8'))
        content = live_config(config)
        with NamedTemporaryFile(mode='w', encoding='ascii', dir=target.parent, delete=False,
                                prefix='.linuxbr-lan-') as stream:
            temporary = Path(stream.name)
            try:
                stream.write(content)
                stream.flush()
                command(DNSMASQ, '--test', '--conf-file=' + str(temporary))
                if not save_definition:
                    temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        if not save_definition:
            return
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False,
                                prefix='.linuxbr-lan-json-') as stream:
            temporary = Path(stream.name)
            try:
                os.fchmod(stream.fileno(), 0o644)
                json.dump(config, stream, indent=2)
                stream.flush()
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--prepare-runtime']:
            apply(None, RUNTIME, save_definition=False)
        elif len(sys.argv) == 1:
            data = sys.stdin.buffer.read(65537)
            if len(data) > 65536:
                raise ValueError('A configuração excede o tamanho permitido.')
            apply(json.loads(data))
            print('Configuração verificada e salva.')
        else:
            raise ValueError('Operação inválida.')
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(detail, file=sys.stderr)
        raise SystemExit(1)
