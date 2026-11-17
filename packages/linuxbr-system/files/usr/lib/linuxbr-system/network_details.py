"""Read-only NetworkManager adapter details."""
import os
import re
import shutil
import subprocess
import ipaddress


def split_escaped(line):
    result=[];part='';escaped=False
    for char in line:
        if escaped:part+=char;escaped=False
        elif char=='\\':escaped=True
        elif char==':':result.append(part);part=''
        else:part+=char
    result.append(part)
    return result


def wifi_details(output):
    for line in output.splitlines():
        values=split_escaped(line)
        if len(values)==6 and values[0]=='*':
            return dict(zip(('WIFI.SSID','WIFI.FREQUENCY','WIFI.SIGNAL','WIFI.SECURITY','WIFI.BSSID'),values[1:]))
    return {}


def parse_devices(output):
    devices = []
    current = None
    for line in output.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key == 'GENERAL.DEVICE':
            current = {}
            devices.append(current)
        if current is not None:
            current[key] = value if value != '--' else ''
    return devices


def inventory():
    env = dict(os.environ, LC_ALL='C.UTF-8')
    result = subprocess.run(
        ['/usr/bin/nmcli', '--terse', '--escape', 'no', '--fields', 'all',
         'device', 'show'], capture_output=True, text=True, timeout=15, env=env)
    if result.returncode:
        raise RuntimeError('Não foi possível consultar os adaptadores de rede.')
    devices=parse_devices(result.stdout)
    for device in devices:
        if device.get('GENERAL.TYPE')=='wifi':
            try:
                data=subprocess.run(['/usr/bin/nmcli','-t','--escape','yes','-f','IN-USE,SSID,FREQ,SIGNAL,SECURITY,BSSID','device','wifi','list','ifname',device['GENERAL.DEVICE'],'--rescan','no'],capture_output=True,text=True,timeout=8,env=env)
                if not data.returncode:device.update(wifi_details(data.stdout))
            except subprocess.TimeoutExpired:pass
    return devices


def values(device, prefix):
    return '\n'.join(value for key, value in device.items()
                     if (key == prefix or key.startswith(prefix + '[')) and value)


def fields(device):
    state = device.get('GENERAL.STATE', '').split(' ', 1)[0]
    states = {'10': 'Não gerenciado', '20': 'Indisponível', '30': 'Desconectado',
              '40': 'Preparando', '50': 'Configurando', '60': 'Autenticação necessária',
              '70': 'Obtendo endereço', '80': 'Verificando conexão',
              '90': 'Finalizando', '100': 'Conectado', '110': 'Desconectando',
              '120': 'Falha na conexão'}
    kind = device.get('GENERAL.TYPE', '')
    types = {'ethernet': 'Ethernet', 'wifi': 'Wi-Fi', 'bridge': 'Ponte de rede',
             'tun': 'Túnel', 'wireguard': 'WireGuard', 'loopback': 'Interface local',
             'vlan': 'VLAN', 'bond': 'Agregação de interfaces'}
    rows = [('Conexão', device.get('GENERAL.CONNECTION', '')),
            ('Adaptador', device.get('GENERAL.DEVICE', '')),
            ('Tipo', types.get(kind, kind)), ('Estado', states.get(state, 'Não disponível')),
            ('Endereço físico (MAC)', device.get('GENERAL.HWADDR', '')),
            ('MTU', device.get('GENERAL.MTU', '')),
            ('Driver', device.get('GENERAL.DRIVER', '')),
            ('Velocidade do link', device.get('WIRED-PROPERTIES.SPEED', device.get('CAPABILITIES.SPEED','')).replace('unknown','Não disponível')),
            ('Fabricante',device.get('GENERAL.VENDOR','')),('Modelo',device.get('GENERAL.PRODUCT',''))]
    if kind=='wifi':
        for label,key in [('Rede Wi-Fi (SSID)','SSID'),('Frequência','FREQUENCY'),('Intensidade (%)','SIGNAL'),('Segurança Wi-Fi','SECURITY'),('Ponto de acesso','BSSID')]:rows.append((label,device.get('WIFI.'+key,'')))
    for family in (4, 6):
        connectivity=device.get(f'GENERAL.IP{family}-CONNECTIVITY','').split(' ',1)[0]
        rows.append((f'Conectividade IPv{family}',{'0':'Não verificada','1':'Sem conectividade','2':'Portal de autenticação','3':'Acesso limitado','4':'Internet disponível segundo o gerenciador'}.get(connectivity,'Não disponível')))
        for label, key in [('Endereços', 'ADDRESS'), ('Gateway', 'GATEWAY'),
                           ('Servidores DNS', 'DNS'), ('Domínios de pesquisa', 'DOMAIN')]:
            rows.append((f'{label} IPv{family}', values(device, f'IP{family}.{key}')))
        routes=[]
        for route in values(device,f'IP{family}.ROUTE').splitlines():
            parsed=dict(re.findall(r'(dst|nh|mt)\s*=\s*([^,]+)',route))
            if 'dst' in parsed:
                destination=parsed['dst'].strip();destination='Rota padrão' if destination in ('0.0.0.0/0','::/0') else destination
                routes.append(destination+' → '+parsed.get('nh','Não disponível').strip()+' · prioridade '+parsed.get('mt','Não disponível').strip())
        rows.append((f'Rotas IPv{family}','\n'.join(routes)))
        masks=[]
        for address in values(device,f'IP{family}.ADDRESS').splitlines():
            try:masks.append(str(ipaddress.ip_interface(address).netmask))
            except ValueError:pass
        if family==4:rows.append(('Máscaras IPv4','\n'.join(masks)))
        options = values(device, f'DHCP{family}.OPTION')
        server = re.search(r'(?:^|\n)dhcp_server_identifier\s*=\s*([^\n]+)', options)
        if server:
            rows.append((f'Servidor DHCP IPv{family}', server.group(1)))
    return [(label, value or 'Não disponível') for label, value in rows]


def reconnect_command(device):
    name=device.get('GENERAL.DEVICE','');uuid=device.get('GENERAL.CON-UUID','')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}',name) or not re.fullmatch(r'[a-fA-F0-9-]{36}',uuid):raise ValueError('Selecione uma conexão gerenciada ativa.')
    if device.get('GENERAL.TYPE') not in ('ethernet','wifi'):raise ValueError('Reconexão disponível para Ethernet e Wi-Fi gerenciados.')
    return ['/usr/bin/nmcli','--wait','45','connection','up','uuid',uuid,'ifname',name]


def connectivity_check(name):
    device = next((item for item in inventory() if item.get('GENERAL.DEVICE') == name), {})
    state = device.get('GENERAL.STATE', '').partition(' ')[0]
    active = state == '100'
    rows = [('Conexão', 'Adaptador conectado.' if active else 'Adaptador sem conexão ativa. Confira o cabo, o Wi-Fi ou a autenticação.')]

    addresses = [values(device, f'IP{family}.ADDRESS') for family in (4, 6)]
    if active:
        rows.append(('Endereço IP', 'Endereço atribuído.' if any(addresses) else 'Nenhum endereço IP foi atribuído.'))

    gateways = [values(device, f'IP{family}.GATEWAY') for family in (4, 6)]
    ping = shutil.which('ping')
    if active and not any(gateways):
        rows.append(('Gateway', 'A conexão não informa um gateway. Isso é esperado em algumas redes locais.'))
    for family, gateway in zip((4, 6), gateways):
        if not active or not gateway:
            continue
        try:
            address = ipaddress.ip_address(gateway)
        except ValueError:
            rows.append((f'Gateway IPv{family}', 'Endereço inválido na configuração.'))
            continue
        if ping:
            try:
                result = subprocess.run([ping, f'-{family}', '-n', '-c', '1', '-W', '2',
                                         '-I', name, str(address)], capture_output=True, timeout=4)
                reply = result.returncode == 0
            except subprocess.TimeoutExpired:
                reply = False
            message = 'Respondeu ao teste.' if reply else 'Sem resposta ao ping. O gateway pode bloquear esse teste.'
        else:
            message = 'Endereço configurado. O teste de resposta está indisponível.'
        rows.append((f'Gateway IPv{family}', message))

    result = subprocess.run(['/usr/bin/nmcli', 'networking', 'connectivity', 'check'],
                            capture_output=True, text=True, timeout=25,
                            env=dict(os.environ, LC_ALL='C.UTF-8'))
    connectivity = result.stdout.strip() if not result.returncode else 'unknown'
    if active and any(addresses) and connectivity != 'portal':
        try:
            lookup = subprocess.run(['/usr/bin/getent', 'ahosts', 'linuxbr.homedeveloper.com.br'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            resolved = lookup.returncode == 0
        except subprocess.TimeoutExpired:
            resolved = False
        message = ('O resolvedor do sistema encontrou o endereço do site do Linux BR.' if resolved
                   else 'O resolvedor do sistema não encontrou o endereço do site do Linux BR.')
        rows.append(('DNS', message))
    rows.append(('Internet neste computador', {
        'full': 'O NetworkManager confirmou acesso.',
        'portal': 'A rede exige autenticação em um portal.',
        'limited': 'Conexão local disponível sem confirmação de acesso à internet.',
        'none': 'Sem conexão disponível.',
        'unknown': 'A verificação de acesso não está disponível.',
    }.get(connectivity, 'Resultado não disponível.')))
    return rows, connectivity
