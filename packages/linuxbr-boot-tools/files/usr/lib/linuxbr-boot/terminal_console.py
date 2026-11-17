"""Interactive configuration for a Linux BR server."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import unicodedata

from boot_policy import edition, mode


def run(*argv, admin=False):
    command = (('sudo', '--') + argv) if admin and os.geteuid() else argv
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as error:
        print(f'Não foi possível abrir {argv[0]}. {error}')
        return 1


def confirm(message):
    return input(message + ' [s/N] ').strip().lower() == 's'


def configure_host():
    name = input('Novo nome do computador (Enter para cancelar) ').strip()
    if re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', name):
        run('hostnamectl', 'set-hostname', name, admin=True)
    elif name:
        print('Use até 63 letras, números ou hífens.')


def configure_time():
    run('timedatectl', 'status')
    zone = input('Novo fuso, por exemplo America/Sao_Paulo (Enter para voltar) ').strip()
    if zone:
        run('timedatectl', 'set-timezone', '--', zone, admin=True)


def local_accounts():
    run('getent', 'passwd')
    name = input('Nome da conta a criar (Enter para voltar) ').strip()
    if re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', name):
        run('adduser', '--', name, admin=True)
    elif name:
        print('Use letras minúsculas, números, hífen ou sublinhado.')


def local_groups():
    import grp
    import pwd

    run('getent', 'group')
    action = input('Criar grupo, adicionar conta, retirar conta ou Enter para voltar. ').strip().lower()
    if action not in ('criar', 'adicionar', 'retirar'):
        return
    group = input('Nome do grupo ').strip()
    pattern = r'[a-z_][a-z0-9_-]{0,30}'
    if not re.fullmatch(pattern, group):
        print('Use letras minúsculas, números, hífen ou sublinhado.')
        return
    if action == 'criar':
        if confirm(f'Criar o grupo local {group}?'):
            run('addgroup', '--', group, admin=True)
        return
    account = input('Conta local ').strip()
    if not re.fullmatch(pattern, account):
        print('Nome de conta inválido.')
        return
    try:
        user = pwd.getpwnam(account)
        target = grp.getgrnam(group)
        if user.pw_uid < 1000 or user.pw_uid == 65534 or target.gr_gid == user.pw_gid:
            raise ValueError('Escolha uma conta comum e um grupo suplementar.')
    except (KeyError, ValueError):
        print('Confira a conta comum e o grupo suplementar.')
        return
    if confirm(f'{action.capitalize()} {account} do grupo {group}?'):
        run('adduser' if action == 'adicionar' else 'deluser', '--', account, group, admin=True)


def units():
    run('systemctl', '--no-pager', 'list-units', '--type=service,timer')
    action = input('Ação: iniciar, parar, reiniciar, habilitar, desabilitar (Enter para voltar) ').strip()
    operations = {'iniciar': 'start', 'parar': 'stop', 'reiniciar': 'restart',
                  'habilitar': 'enable', 'desabilitar': 'disable'}
    if action not in operations:
        return
    unit = input('Nome completo da unidade (.service ou .timer) ').strip()
    if re.fullmatch(r'[A-Za-z0-9_.@:-]+\.(service|timer)', unit) and confirm(f'Aplicar a ação em {unit}?'):
        run('systemctl', operations[action], '--', unit, admin=True)


def scheduled_tasks():
    backend = next((path for path in (
        Path('/usr/lib/linuxbr-server/administration_backend.py'),
        Path('/usr/lib/linuxbr-system/administration_backend.py'),
    ) if path.is_file()), None)
    if backend is None:
        print('Instale a edição Servidor para administrar tarefas agendadas.')
        return
    sys.path.insert(0, str(backend.parent))
    try:
        from administration_backend import tasks
        rows = tasks('system')
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Não foi possível consultar o agendador. {error}')
        return
    finally:
        sys.path.pop(0)
    for index, task in enumerate(rows, 1):
        print(f'{index:2}. {task["name"]} | {task["calendar"]} | '
              f'{task["enabled"]} | Próxima execução {task["next"] or "indisponível"}')
    if not rows:
        print('Nenhuma tarefa cadastrada pelo Linux BR.')
    choice = input('Digite nova, o número de uma tarefa ou Enter para voltar. ').strip()
    if choice == 'nova':
        name = input('Nome da tarefa (Enter para cancelar) ').strip()
        if not name:
            return
        executable = input('Caminho absoluto do programa ').strip()
        try:
            argv = [executable, *shlex.split(input('Argumentos (opcional) '))]
        except ValueError:
            print('Confira as aspas nos argumentos.')
            return
        calendar = input('Agendamento (Enter para executar todo dia às 09:00) ').strip() or '*-*-* 09:00:00'
        print(shlex.join(argv))
        print(f'Agendamento {calendar}')
        if not confirm('Criar uma tarefa que executa como administrador do computador?'):
            return
        request = dict(action='create-task', scope='system', name=name, argv=argv, calendar=calendar)
    elif re.fullmatch(r'[0-9]{1,6}', choice) and 1 <= int(choice) <= len(rows):
        task = rows[int(choice) - 1]
        operation = input('Executar, habilitar, desabilitar, remover, histórico ou Enter para voltar. ').strip().lower()
        if operation in ('histórico', 'historico'):
            run('journalctl', '--no-pager', '-n', '60', '-u', f'linuxbr-task-{task["id"]}.service', admin=True)
            return
        operations = {'executar': 'run', 'habilitar': 'enable', 'desabilitar': 'disable', 'remover': 'remove'}
        if operation not in operations or not confirm(f'Aplicar a ação à tarefa {task["name"]}?'):
            return
        request = dict(action='task', scope='system', id=task['id'], operation=operations[operation])
    else:
        return
    if os.geteuid() and run('sudo', '-v'):
        return
    argv = ['/usr/bin/python3', str(backend), '--apply']
    if os.geteuid():
        argv = ['sudo', '-n', '--', *argv]
    result = subprocess.run(argv, input=json.dumps(request), capture_output=True, text=True, check=False)
    if result.returncode:
        print(result.stderr.strip() or 'O agendador recusou a operação.')
    elif request['action'] == 'create-task':
        print('Tarefa criada e agendamento ativado.')
    else:
        print('Solicitação aplicada ao agendador.')


def remote_access():
    run('systemctl', '--no-pager', 'status', 'ssh.service')
    if confirm('Habilitar o SSH para administração remota?'):
        run('systemctl', 'enable', '--now', 'ssh.service', admin=True)


def server_features():
    backend = next((path for path in (
        Path('/usr/lib/linuxbr-server/features_backend.py'),
        Path('/usr/lib/linuxbr-system/features_backend.py'),
    ) if path.is_file()), None)
    if backend is None:
        print('Instale o pacote da edição Servidor para administrar recursos.')
        return
    entries = {
        '1': ('Compartilhamento de arquivos', 'sharing'),
        '2': ('Impressão e digitalização', 'printing'),
        '3': ('Central de Administração Remota', 'server-console'),
        '4': ('Servidor de contêineres', 'containers'),
        '5': ('Cache de atualizações APT', 'apt-cache-server'),
        '6': ('Serviços DNS e DHCP da rede local', 'lan-services'),
    }
    for key, (label, _) in entries.items():
        print(f'{key}. {label}')
    choice = input('Recurso a instalar (Enter para voltar) ').strip()
    if choice not in entries:
        return
    sys.path.insert(0, str(backend.parent))
    try:
        from features_backend import package_plan
        plan = package_plan(entries[choice][1], 'install')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(error)
        return
    finally:
        sys.path.pop(0)
    print(plan['details'])
    if not confirm('Instalar os pacotes apresentados?'):
        return
    request = json.dumps(dict(action='install', feature=plan['feature'], sha256=plan['sha256']))
    if os.geteuid() and run('sudo', '-v'):
        return
    command = ['/usr/bin/python3', str(backend)]
    if os.geteuid():
        command = ['sudo', '-n', '--', *command]
    subprocess.run(command, input=request, text=True, check=False)


def configure_apt_cache():
    config = '/etc/apt/apt.conf.d/80linuxbr-cache-rede'
    if Path(config).is_file():
        print(Path(config).read_text(encoding='utf-8').strip())
    address = input('Nome ou IP do servidor de cache (digite remover para desativar) ').strip()
    if address == 'remover':
        if confirm('Desativar o cache de atualizações neste computador?'):
            run('rm', '-f', '--', config, admin=True)
        return
    try:
        parsed = ipaddress.ip_address(address)
        if parsed.version == 6:
            address = f'[{parsed}]'
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', address):
            if address:
                print('Informe somente o nome ou IP do servidor.')
            return
    port = input('Porta HTTP (Enter para 3142) ').strip() or '3142'
    if not re.fullmatch(r'[0-9]{1,5}', port) or not 1 <= int(port) <= 65535:
        print('Porta inválida.')
        return
    proxy = f'http://{address}:{port}/'
    if not confirm(f'Usar {proxy} como cache dos repositórios APT que usam HTTP?'):
        return
    program = '''
import os
from pathlib import Path
import sys
import tempfile

target = Path(sys.argv[1])
with tempfile.NamedTemporaryFile(mode='w', encoding='ascii', dir=target.parent, prefix='.linuxbr-cache-', delete=False) as stream:
    temporary = Path(stream.name)
    try:
        stream.write('Acquire::http::Proxy "' + sys.argv[2] + '";\\n')
        stream.flush()
        os.fsync(stream.fileno())
        temporary.chmod(0o644)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
'''
    run('/usr/bin/python3', '-I', '-c', program, config, proxy, admin=True)


def certificates():
    path = input('Caminho do certificado PEM (Enter para voltar) ').strip()
    if not path:
        return
    try:
        with Path(path).open('rb') as source:
            data = source.read(65537)
        if len(data) > 65536 or not re.fullmatch(
            rb'\s*-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*', data
        ):
            raise ValueError('Escolha um arquivo PEM com um único certificado público.')
        details = subprocess.run(
            ['openssl', 'x509', '-noout', '-subject', '-issuer', '-dates', '-fingerprint', '-sha256'],
            input=data, capture_output=True, check=True, timeout=10,
        )
        print(details.stdout.decode(errors='replace'))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Não foi possível ler o certificado. {error}')
        return


def install_cockpit_certificate():
    from cockpit_certificates import ENSURE, LIMIT, inspect_pair, payload

    if not Path(ENSURE).is_file():
        print('Instale a Central de Administração Remota primeiro.')
        return
    hostname = input('Nome DNS ou IP usado para acessar o Cockpit (Enter para voltar) ').strip()
    if not hostname:
        return
    chain_path = input('Caminho da cadeia pública PEM ').strip()
    key_path = input('Caminho da chave privada PEM ').strip()
    if not chain_path or not key_path:
        return
    try:
        with Path(chain_path).open('rb') as stream:
            chain = stream.read(LIMIT + 1)
        with Path(key_path).open('rb') as stream:
            key = stream.read(LIMIT + 1)
        print(inspect_pair(chain, key, hostname))
        if not confirm('Instalar o certificado HTTPS do Cockpit?'):
            return
        if os.geteuid() and run('sudo', '-v'):
            return
        argv = ['/usr/bin/python3', '-I', str(Path(__file__).with_name('cockpit_certificates.py'))]
        if os.geteuid():
            argv = ['sudo', '-n', '--', *argv]
        result = subprocess.run(argv, input=payload(chain, key, hostname), check=False)
        if result.returncode == 0:
            print('Certificado instalado. Aplique ao Cockpit reiniciando cockpit.service durante a manutenção.')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Não foi possível instalar o certificado. {error}')


def configure_network():
    if os.environ.get('SSH_CONNECTION'):
        print('Confirme a nova configuração após sair do editor. Prazo de reversão: 5 minutos.')
        run('nmcli', 'device', 'checkpoint', '--timeout', '300', '--', 'nmtui', admin=True)
    else:
        run('nmtui', admin=True)


def firewall_rules():
    if run('firewall-cmd', '--list-all', admin=True):
        return
    action = input('Liberar, remover ou Enter para voltar. ').strip().lower()
    operations = {'liberar': 'allow', 'remover': 'remove'}
    if action not in operations:
        return
    zone = input('Zona do firewall ').strip()
    port = input('Porta e protocolo, por exemplo 8443/tcp ').strip().lower()
    if not confirm('Testar a alteração por até dois minutos?'):
        return
    argv = ['/usr/bin/python3', '-I', str(Path(__file__).with_name('firewall_trial.py'))]
    if os.geteuid():
        if run('sudo', '-v'):
            return
        argv = ['sudo', '-n', '--', *argv]
    result = subprocess.run([*argv, 'begin', zone, port, operations[action]], capture_output=True, text=True)
    if result.returncode:
        print(result.stderr.strip() or 'Não foi possível iniciar o teste do firewall.')
        return
    token = result.stdout.strip()
    print('A alteração está em teste. Verifique o acesso por outra conexão antes de confirmar.')
    commit = confirm('O acesso está funcionando e deseja salvar a regra?')
    if not run(*argv, 'commit' if commit else 'rollback', token):
        print('Regra salva.' if commit else 'Regra anterior restaurada.')
    elif not commit:
        print('A reversão continua agendada no hospedeiro.')


def delegate_vm():
    if run('virsh', '--connect', 'qemu:///system', 'list', '--all', admin=True):
        return
    operation = input('Conceder, revogar ou Enter para voltar. ').strip().lower()
    if operation not in ('conceder', 'revogar'):
        return
    account = input('Conta local com acesso ao SSH ').strip()
    identifier = input('UUID da VM (consulte virsh domuuid NOME) ').strip()
    if not confirm(f'{operation.capitalize()} a operação de energia desta VM para {account}?'):
        return
    if not run('/usr/bin/linuxbr-vm-operator', operation, account, identifier, admin=True) and operation == 'conceder':
        print(f'Na conta delegada, use sudo linuxbr-vm-operator estado {identifier}')


def configure_lan_services():
    from lan_services import DEFINITION, DNSMASQ, UNIT, live_config

    if not Path(DNSMASQ).is_file():
        print('Instale Serviços DNS e DHCP da rede local em Funções do servidor.')
        return
    run('systemctl', '--no-pager', 'is-active', UNIT)
    choice = input('Configurar, adicionar, remover, ativar, desativar, consultar ou Enter para voltar. ').strip().lower()
    if choice == 'consultar':
        if DEFINITION.is_file():
            print(DEFINITION.read_text(encoding='utf-8'))
        return
    if choice == 'desativar':
        if confirm('Parar o serviço DNS e DHCP desta interface?'):
            run('systemctl', 'disable', '--now', UNIT, admin=True)
        return
    if choice == 'ativar':
        if not DEFINITION.is_file():
            print('Salve a configuração antes de ativar o serviço.')
            return
        if DEFINITION.is_file():
            print(DEFINITION.read_text(encoding='utf-8'))
        if confirm('A rede está preparada para este serviço? Se houver DHCP na configuração, confira se nenhum outro servidor atende o mesmo segmento.'):
            if not run('systemctl', 'restart', UNIT, admin=True):
                run('systemctl', 'enable', UNIT, admin=True)
            run('systemctl', '--no-pager', 'status', UNIT)
        return
    if choice in ('adicionar', 'remover'):
        if not DEFINITION.is_file():
            print('Configure uma interface primeiro.')
            return
        request = json.loads(DEFINITION.read_text())
        name = input('Nome local sem domínio (Enter para cancelar) ').strip().lower()
        if not name:
            return
        records = request['records']
        if choice == 'remover':
            request['records'] = [record for record in records if record['name'].lower() != name]
            if len(request['records']) == len(records):
                print('Nome local não encontrado.')
                return
        else:
            address = input('Endereço IPv4 ').strip()
            mac = input('MAC de reserva (Enter para adicionar só DNS) ').strip() if request['scope'] else ''
            records.append(dict(name=name, address=address, mac=mac))
        save_lan_request(request, live_config)
        return
    if choice != 'configurar':
        return
    run('ip', '-br', '-4', 'address')
    interface = input('Interface LAN física com IPv4 estático (Enter para voltar) ').strip()
    if not interface:
        return
    subnet = input('Sub-rede em CIDR, por exemplo 192.168.50.0/24 ').strip()
    domain = input('Domínio interno (Enter para rede.home.arpa) ').strip() or 'rede.home.arpa'
    scope = []
    if confirm('Configurar também um servidor DHCP nesta interface?'):
        scope = [input(label).strip() for label in ('Primeiro IP da faixa dinâmica ',
                 'Último IP da faixa dinâmica ', 'IP do roteador (Enter para não anunciar gateway) ')]
    records = []
    while len(records) < 250:
        name = input('Nome local sem domínio (Enter para concluir) ').strip()
        if not name:
            break
        address = input('Endereço IPv4 ').strip()
        mac = input('MAC de reserva (Enter para adicionar só DNS) ').strip() if scope else ''
        records.append(dict(name=name, address=address, mac=mac))
    request = dict(interface=interface, subnet=subnet, domain=domain, scope=scope, records=records)
    save_lan_request(request, live_config)


def save_lan_request(request, live_config):
    try:
        print(live_config(request))
        if not confirm('Salvar esta configuração da rede local?'):
            return
        argv = ['/usr/bin/python3', '-I', str(Path(__file__).with_name('lan_services.py'))]
        if os.geteuid():
            if run('sudo', '-v'):
                return
            argv = ['sudo', '-n', '--', *argv]
        subprocess.run(argv, input=json.dumps(request), text=True, check=False)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Não foi possível preparar o serviço. {error}')


def create_vm():
    if not shutil.which('virt-install'):
        print('Instale o componente virtinst para criar VMs.')
        return
    name = input('Nome da VM (Enter para voltar) ').strip()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', name):
        return
    try:
        memory = int(input('Memória em MiB '))
        cpus = int(input('Número de processadores '))
        size = int(input('Tamanho do disco em GiB '))
        if not (256 <= memory <= 262144 and 1 <= cpus <= 256 and 4 <= size <= 2048):
            raise ValueError
    except ValueError:
        print('Informe memória de 256 a 262144 MiB, 1 a 256 CPUs e disco de 4 a 2048 GiB.')
        return
    iso = input('Caminho absoluto da ISO (Enter para criar sem mídia) ').strip()
    if iso and (',' in iso or not Path(iso).is_absolute() or not Path(iso).is_file()):
        print('Escolha um arquivo de mídia existente com caminho absoluto e sem vírgulas.')
        return
    options = ('--cdrom', iso) if iso else ('--import',)
    if run('virsh', '--connect', 'qemu:///system', 'pool-list', admin=True):
        return
    pool = input('Nome do local de armazenamento ativo ').strip()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', pool):
        print('Escolha um local de armazenamento ativo da lista.')
        return
    network = input('Nome da rede libvirt (Enter para criar sem rede) ').strip()
    if network and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', network):
        print('Nome de rede inválido.')
        return
    if confirm(f'Criar e ligar {name} com {cpus} CPUs, {memory} MiB e disco de {size} GiB?'):
        run('virt-install', '--connect', 'qemu:///system', '--name', name,
            '--memory', str(memory), '--vcpus', str(cpus), '--disk', f'pool={pool},size={size},format=qcow2',
            '--network', f'network={network}' if network else 'none',
            '--osinfo', 'generic', '--boot', 'uefi', '--noautoconsole', *options, admin=True)


def vm_backend(operation, *values):
    backend = next((path for path in (
        Path('/usr/lib/linuxbr-server'), Path('/usr/lib/linuxbr-system'),
    ) if (path / 'virtualization_backend.py').is_file()), None)
    if backend is None:
        print('O componente de gerenciamento de VMs está indisponível.')
        return 1
    program = '''
import sys
sys.path.insert(0, sys.argv[1])
from virtualization_backend import Manager

manager = Manager()
try:
    operation, *values = sys.argv[2:]
    if operation == 'network':
        name, mode, value = values
        identifier = manager.define_network(dict(name=name, mode=mode, subnet=value, bridge=value))
        try:
            manager.network_action(identifier, 'start')
        except Exception:
            manager.network_action(identifier, 'remove')
            raise
    elif operation == 'import':
        path, pool, name, network = values
        manager.import_bundle(path, pool, name, True, network)
    else:
        identifier, *arguments = values
        domain = next((row for row in manager.domains() if identifier in (row['id'], row['name'])), None)
        if domain is None:
            raise ValueError('Máquina virtual não encontrada.')
        if operation == 'resources':
            memory, cpus = map(int, arguments)
            manager.resources(domain['id'], memory, cpus, domain['autostart'])
        elif operation == 'checkpoints':
            for checkpoint in manager.snapshots(domain['id']):
                print(checkpoint['name'])
        elif operation == 'checkpoint':
            action, name = arguments
            manager.snapshot(domain['id'], action, name)
        elif operation == 'export':
            manager.export_bundle(domain['id'], arguments[0])
except Exception as error:
    sys.exit(str(error))
finally:
    manager.close()
'''
    return run('/usr/bin/python3', '-I', '-c', program, str(backend), operation, *values, admin=True)


def vm_resources(name):
    try:
        memory = int(input('Nova memória em MiB '))
        cpus = int(input('Novo número de processadores '))
        if not (256 <= memory <= 262144 and 1 <= cpus <= 256):
            raise ValueError
    except ValueError:
        print('Informe memória de 256 a 262144 MiB e 1 a 256 CPUs.')
        return
    vm_backend('resources', name, str(memory), str(cpus))


def vm_storage(command):
    run(*command, 'pool-list', '--all', admin=True)
    name = input('Nome do local de armazenamento a criar (Enter para voltar) ').strip()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', name):
        return
    target = Path('/var/lib/libvirt/images') / name
    if not confirm(f'Criar e ativar o armazenamento em {target}?'):
        return
    if run(*command, 'pool-define-as', name, 'dir', '--target', str(target), admin=True):
        return
    if run(*command, 'pool-build', name, admin=True) or run(*command, 'pool-start', name, admin=True):
        run(*command, 'pool-undefine', name, admin=True)
        return
    run(*command, 'pool-autostart', name, admin=True)


def vm_transfer(command):
    action = input('Ação: importar, exportar (Enter para voltar) ').strip()
    if action not in ('importar', 'exportar'):
        return
    name = input('Nome da máquina virtual ').strip()
    path = input('Caminho absoluto da pasta da cópia ').strip()
    if not name or not Path(path).is_absolute():
        print('Informe o nome da VM e o caminho absoluto.')
        return
    if action == 'exportar':
        if confirm(f'Exportar {name} para a nova pasta {path}?'):
            vm_backend('export', name, path)
        return
    run(*command, 'pool-list', admin=True)
    pool = input('Local de armazenamento ativo ').strip()
    network = input('Rede virtual no destino (Enter para NAT do QEMU) ').strip()
    if pool and confirm(f'Importar a cópia de {path} como {name}?'):
        vm_backend('import', path, pool, name, network)


def virtual_machines():
    if not shutil.which('virsh'):
        print('A administração de VMs exige libvirt. Use o perfil Servidor de Máquinas Virtuais.')
        return
    print('Aceleração KVM:', 'disponível' if Path('/dev/kvm').exists()
          else 'indisponível. Confira se a virtualização está habilitada no firmware.')
    command = ('virsh', '--connect', 'qemu:///system')
    if run(*command, 'list', '--all', admin=True):
        return
    action = input('Ação: armazenamento, redes, criar, recursos, checkpoints, cópias, ligar, desligar, reiniciar, pausar, retomar, console, autoiniciar, cancelar-autoinicio (Enter para voltar) ').strip()
    if action in ('copias', 'cópias'):
        vm_transfer(command)
        return
    if action == 'armazenamento':
        vm_storage(command)
        return
    if action == 'redes':
        run(*command, 'net-list', '--all', admin=True)
        action = input('Ação: criar, ativar (Enter para voltar) ').strip()
        if action == 'criar':
            name = input('Nome da nova rede ').strip()
            kind = input('Tipo: nat, isolada, ponte ').strip()
            modes = {'nat': 'nat', 'isolada': 'private', 'ponte': 'bridge'}
            if kind in modes:
                value = input('Sub-rede IPv4 CIDR ' if kind == 'nat' else 'Nome da ponte existente ').strip() if kind != 'isolada' else ''
                if confirm(f'Criar e ativar a rede {name}?'):
                    vm_backend('network', name, modes[kind], value)
        elif action == 'ativar':
            name = input('Nome da rede existente ').strip()
            if name and confirm(f'Ativar a rede {name}?'):
                run(*command, 'net-start', '--network', name, admin=True)
        return
    if action == 'criar':
        create_vm()
        return
    operations = {'ligar': 'start', 'desligar': 'shutdown', 'reiniciar': 'reboot',
                  'pausar': 'suspend', 'retomar': 'resume', 'console': 'console',
                  'autoiniciar': 'autostart', 'cancelar-autoinicio': 'autostart'}
    if action not in operations and action not in ('recursos', 'checkpoints'):
        return
    name = input('Nome ou UUID da VM ').strip()
    if name and action == 'checkpoints':
        if vm_backend('checkpoints', name):
            return
        choice = input('Ação: criar, restaurar (Enter para voltar) ').strip()
        if choice in ('criar', 'restaurar'):
            checkpoint = input('Nome do checkpoint ').strip()
            if checkpoint and confirm(f'{choice.capitalize()} o checkpoint {checkpoint} de {name}?'):
                vm_backend('checkpoint', name, 'create' if choice == 'criar' else 'restore', checkpoint)
        return
    if not name or not confirm(f'Aplicar a ação na VM {name}?'):
        return
    if action == 'recursos':
        vm_resources(name)
        return
    options = ('--disable',) if action == 'cancelar-autoinicio' else ()
    if action == 'console':
        print('Pressione Ctrl+] para fechar o console serial da VM.')
    run(*command, operations[action], '--domain', name, *options, admin=True)


def updates():
    if run('apt-get', 'update', admin=True) == 0:
        run('apt', 'list', '--upgradable')


def power(action):
    label = 'Reiniciar' if action == 'reboot' else 'Desligar'
    if confirm(f'{label} o computador?'):
        run('systemctl', action, admin=True)


def menu_options(profile):
    options = [
        ('Nome do computador', configure_host,
         'Informe o novo nome com letras, números ou hífens. Use Enter com o campo vazio para voltar.'),
        ('Rede e DNS', configure_network,
         'Escolha a conexão pela interface. Revise IP, gateway e DNS. Se estiver usando acesso remoto, confirme a conexão antes do fim do prazo de reversão.'),
        ('DNS e DHCP da rede local', configure_lan_services,
         'Escolha uma interface com IPv4 estático. Confira a faixa e as reservas. Ative o DHCP apenas no segmento onde este servidor deve distribuir endereços.'),
        ('Contas locais', local_accounts,
         'Consulte as contas existentes e informe o nome da nova conta. O sistema solicita a configuração da senha para a conta criada.'),
        ('Grupos locais', local_groups,
         'Escolha criar grupo, adicionar conta ou retirar conta. Revise a associação antes de confirmar.'),
        ('Data e fuso horário', configure_time,
         'Confira o relógio e a sincronização. Informe um fuso como America/Sao_Paulo ou deixe vazio para voltar.'),
        ('Serviços do sistema', units,
         'Informe o nome da unidade para consultar o estado. Confirme a unidade antes de iniciar, parar ou alterar a inicialização automática.'),
        ('Agendador de tarefas', scheduled_tasks,
         'Revise o comando, a conta e a recorrência ao criar uma tarefa. Consulte as execuções para confirmar o resultado.'),
        ('Consultar armazenamento', lambda: run('lsblk', '-f'),
         'Lista discos, sistemas de arquivos e pontos de montagem. Use os identificadores para distinguir volumes com nomes parecidos.'),
        ('Regras de portas do firewall', firewall_rules,
         'Confira zona, porta e protocolo. Teste a regra a partir de outra conexão autorizada e confirme dentro do prazo para torná-la permanente.'),
        ('Consultar atualizações', updates,
         'Atualiza os índices APT e lista os pacotes atualizáveis. Requer acesso aos repositórios configurados.'),
        ('Eventos da inicialização', lambda: run('journalctl', '-b', '-n', '80'),
         'Abre os eventos recentes da inicialização atual. Use as setas para navegar e pressione q se o visualizador estiver aberto.'),
        ('Acesso remoto por SSH', remote_access,
         'Consulte ou habilite o serviço SSH. Valide a conexão usando a conta autorizada antes de encerrar o acesso local.'),
        ('Máquinas virtuais', virtual_machines,
         'Liste as VMs antes de escolher a ação. Informe o nome ou UUID correto e revise as mudanças de CPU, memória, discos ou checkpoints antes de aplicar.'),
        ('Delegar ações de energia de uma VM', delegate_vm,
         'Informe a conta SSH dedicada e a VM autorizada. Use a mesma opção para revisar ou revogar a concessão.'),
        ('Funções do servidor', server_features,
         'Escolha a função para consultar os componentes correspondentes. Revise o que será instalado ou removido antes de confirmar.'),
        ('Cache de atualizações APT', configure_apt_cache,
         'Consulte o estado do cache e confira a porta antes de apontar clientes para ele. Cada cliente continua verificando as assinaturas dos pacotes.'),
        ('Consultar certificado', certificates,
         'Confira o nome, o emissor, as datas e a impressão digital da cadeia usada pelo serviço.'),
        ('Instalar certificado HTTPS do Cockpit', install_cockpit_certificate,
         'Informe os arquivos da cadeia e da chave correspondente. Confira o nome de acesso e a validade antes de ativar.'),
        ('Reiniciar', lambda: power('reboot'),
         'Avise quem está usando o host, salve o trabalho e confira o estado das VMs antes de confirmar.'),
        ('Desligar', lambda: power('poweroff'),
         'Confirme que as VMs e serviços podem parar. Após o desligamento, será necessário ligar o equipamento novamente.'),
    ]
    if profile == 'virtualization':
        index = next(index for index, (_, action, _) in enumerate(options) if action is virtual_machines)
        options.insert(0, options.pop(index))
    if os.environ.get('DISPLAY') and Path('/run/live/medium').exists():
        label = 'Instalar Linux BR VM Server' if profile == 'virtualization' else 'Instalar Linux BR'
        options.insert(0, (label, lambda: run('calamares-install-linuxbr'),
                           'Abra o instalador e confira a edição e o disco de destino antes de confirmar as alterações.'))
    return options


def help_search_text(text):
    normalized = unicodedata.normalize('NFD', text.casefold())
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def show_help(options, query=''):
    terms = help_search_text(query).split()
    if not terms:
        print('Digite ? N para ler o guia da opção N ou ? seguido de palavras para pesquisar.')
    if query.isascii() and query.isdecimal():
        matches = [(index, option) for index, option in enumerate(options, 1) if query == str(index)]
    else:
        matches = [
            (index, option) for index, option in enumerate(options, 1)
            if all(term in help_search_text(f'{option[0]} {option[2]}') for term in terms)
        ]
    if not matches:
        print('Nenhum guia encontrado.')
    for index, (label, _, guide) in matches:
        print(f'{index:2}. {label}')
        if terms:
            print(f'    {guide}')


def menu(profile, window=False):
    title = 'VM Server' if profile == 'virtualization' else 'Console do servidor'
    options = menu_options(profile)
    while True:
        print(f'\nLinux BR | {title} | {socket.gethostname()}')
        for index, (label, _, _) in enumerate(options, 1):
            print(f'{index:2}. {label}')
        print(' 0. Fechar configuração' if window else ' 0. Voltar ao terminal')
        print(' ?. Ajuda offline (por exemplo, ? 1 ou ? armazenamento)')
        choice = input('Selecione uma opção: ').strip()
        if not choice:
            continue
        if choice == '0':
            return
        if choice.startswith('?'):
            show_help(options, choice[1:].strip())
            input('Pressione Enter para voltar ao menu. ')
        elif choice.isascii() and choice.isdecimal() and len(choice) <= 2 and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print('Opção inválida.')


def main():
    parser = argparse.ArgumentParser(description='Console do servidor Linux BR')
    parser.add_argument('--server-login', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--janela', action='store_true', help=argparse.SUPPRESS)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--virtualizacao', action='store_true', help='Abrir a administração de máquinas virtuais.')
    actions.add_argument('--ajuda', nargs='?', const='', metavar='TERMO', help='Consultar guias locais do console.')
    args = parser.parse_args()
    if mode():
        if not args.server_login:
            print('Use as ferramentas do modo de manutenção atual.')
        return
    profile = edition()
    if args.ajuda is not None:
        show_help(menu_options(profile), args.ajuda.strip())
        return
    if args.server_login and profile not in ('server', 'virtualization'):
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.exit(1, 'Abra o console em um terminal interativo.\n')
    try:
        if args.virtualizacao:
            virtual_machines()
        else:
            menu(profile, window=args.janela)
    except (EOFError, KeyboardInterrupt):
        print()


if __name__ == '__main__':
    main()
