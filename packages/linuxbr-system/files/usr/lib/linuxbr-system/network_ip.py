"""NetworkManager IPv4/IPv6 configuration without shell expansion."""
import ipaddress
import re
import subprocess
import uuid


def nmcli(*args):
    return subprocess.check_output(['nmcli',*args],text=True,timeout=12).strip()


def profiles():
    rows=[]
    for line in nmcli('-t','-f','UUID,TYPE,NAME','connection','show').splitlines():
        parts=line.split(':',2)
        if len(parts)==3 and parts[1] in ('802-3-ethernet','802-11-wireless','ethernet','wifi'):
            rows.append({'uuid':parts[0],'type':parts[1],'name':parts[2]})
    return rows


KEYS=('ipv4.method','ipv4.addresses','ipv4.gateway','ipv4.dns','ipv4.ignore-auto-dns',
      'ipv6.method','ipv6.addresses','ipv6.gateway','ipv6.dns','ipv6.ignore-auto-dns')


def settings(profile):
    uuid.UUID(profile)
    result={}
    for key in KEYS:
        result[key]=nmcli('-g',key,'connection','show',profile)
    return result


def validated(family,method,address,gateway,dns):
    if method not in ('auto','manual','disabled'):
        raise ValueError('Método de IP inválido.')
    if method=='manual':
        try:
            interface=ipaddress.ip_interface(address)
            if interface.version!=family:raise ValueError()
        except ValueError:raise ValueError(f'Informe um endereço IPv{family} com prefixo, por exemplo 192.168.1.50/24.')
    elif address.strip():
        raise ValueError('Limpe o endereço manual ao usar configuração automática ou desativada.')
    if gateway:
        if method!='manual' or ipaddress.ip_address(gateway).version!=family:
            raise ValueError('Gateway incompatível com o método ou a versão IP.')
    servers=[part.strip() for part in re.split(r'[,;\s]+',dns) if part.strip()]
    if len(servers)>6:raise ValueError('Informe no máximo seis servidores DNS.')
    for server in servers:
        if ipaddress.ip_address(server).version!=family:
            raise ValueError(f'DNS IPv{family} inválido: {server}.')
    return {'method':method,'addresses':address.strip() if method=='manual' else '',
            'gateway':gateway.strip() if method=='manual' else '',
            'dns':','.join(servers), 'ignore-auto-dns':'yes' if servers else 'no'}


def apply(profile,v4,v6):
    uuid.UUID(profile)
    fields=[]
    for family,values in ((4,v4),(6,v6)):
        for key,value in values.items():fields.extend([f'ipv{family}.{key}',value])
    subprocess.run(['nmcli','connection','modify',profile,*fields],check=True,timeout=20)
