"""Firewalld read model and privileged, validated port rule changes."""
import json
import re
import subprocess
import sys

PORT = re.compile(r'([1-9][0-9]{0,4})/(tcp|udp)\Z')


def command(*argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=12, check=True).stdout.strip()


def validate(port):
    match = PORT.fullmatch(port)
    if not match or int(match[1]) > 65535: raise ValueError('Porta ou protocolo inválido.')
    return port


def state():
    running = subprocess.run(['firewall-cmd','--state'], capture_output=True, text=True, timeout=4).returncode == 0
    result = {'running':running,'zone':'','zones':[],'details':{},'listeners':[]}
    if running:
        result['zone'] = command('firewall-cmd','--get-default-zone')
        active=command('firewall-cmd','--get-active-zones').splitlines()
        current=[line.strip() for line in active if line and not line[0].isspace()]
        result['zones']=list(dict.fromkeys([result['zone']]+current))
        for zone in result['zones']:
            details={'services':command('firewall-cmd','--zone='+zone,'--list-services').split(),
                     'ports':command('firewall-cmd','--zone='+zone,'--list-ports').split(),
                     'rich':command('firewall-cmd','--zone='+zone,'--list-rich-rules').splitlines(),
                     'forward':command('firewall-cmd','--zone='+zone,'--list-forward-ports').split(),
                     'service_ports':{}}
            for service in details['services']:
                info=command('firewall-cmd','--info-service='+service)
                match=re.search(r'^\s*ports:\s*(.*)$',info,re.MULTILINE)
                details['service_ports'][service]=match.group(1).split() if match else []
            result['details'][zone]=details
    # ss exposes process names for the current user; other processes may be hidden.
    sockets = subprocess.run(['ss','-H','-ltnup'], capture_output=True, text=True, timeout=4)
    for line in sockets.stdout.splitlines():
        cells = line.split(maxsplit=6)
        if len(cells) < 5: continue
        proto, address = cells[0], cells[4]
        if proto not in ('tcp','udp'): continue
        name = re.search(r'\("([^"\\]+)"', line)
        result['listeners'].append({'protocol':proto.upper(),'address':address,
            'app':name.group(1) if name else 'Processo não identificado'})
    return result


def apply(action, port='', zone=''):
    if action in ('enable','disable'):
        command('systemctl', 'enable' if action == 'enable' else 'disable', '--now', 'firewalld')
        return
    if action not in ('allow','remove'): raise ValueError('Ação desconhecida.')
    validate(port)
    zone = zone or command('firewall-cmd','--get-default-zone')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',zone) or zone not in command('firewall-cmd','--get-zones').split():
        raise ValueError('Zona inválida.')
    command('firewall-cmd','--permanent','--zone='+zone,
            ('--add-port=' if action == 'allow' else '--remove-port=')+port)
    command('firewall-cmd','--reload')


if __name__ == '__main__':
    try:
        if len(sys.argv) not in (2,3,4): raise ValueError('Parâmetros inválidos.')
        apply(*sys.argv[1:])
    except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr); sys.exit(1)
