"""Read-only compatibility inspection before a libvirt migration."""

import copy
import xml.etree.ElementTree as ET

from virtualization_backend import checked_uri

GIB = 1024 ** 3
UNITS = {'b': 1, 'bytes': 1, 'k': 1024, 'kb': 1000, 'kib': 1024,
         'm': 1024 ** 2, 'mb': 1000 ** 2, 'mib': 1024 ** 2,
         'g': GIB, 'gb': 1000 ** 3, 'gib': GIB, 'tib': 1024 ** 4}


def cpu_profile(guest, capabilities):
    cpu = guest.find('cpu')
    if cpu is not None and cpu.find('model') is not None:
        content = cpu
    elif cpu is None or cpu.get('mode') == 'host-model':
        content = capabilities.find("cpu/mode[@name='host-model'][@supported='yes']")
    else:
        return ''
    if content is None or content.find('model') is None:
        return ''
    result = ET.Element('cpu', mode='custom', match='exact')
    for entry in content:
        if entry.tag in ('model', 'vendor', 'feature'):
            result.append(copy.deepcopy(entry))
    return ET.tostring(result, encoding='unicode')


def evaluate(manager, domain, destination, target, mode, pool=None, network=None, name=None):
    results = []

    def add(area, status, detail):
        results.append({'area': area, 'status': status, 'detail': detail})

    source_host = ET.fromstring(manager.connection.getCapabilities())
    target_host = ET.fromstring(target.getCapabilities())
    source_id, target_id = [host.findtext('host/uuid') for host in (source_host, target_host)]
    if not source_id or not target_id or source_id == target_id:
        add('Conectividade', 'blocked', 'O serviço respondeu, mas os hospedeiros não puderam ser confirmados como distintos.')
    else:
        add('Conectividade', 'ok', f'Conexão de administração autenticada em {destination}.')
    existing = list(target.listAllDomains(0))
    if any(item.name() == (name or domain.name()) or
           (mode != 'replica' and item.UUIDString() == domain.UUIDString()) for item in existing):
        add('Identidade da VM', 'blocked', 'O nome ou identificador já está em uso no destino.')
    if domain.hasManagedSaveImage(0):
        add('Estado salvo', 'blocked', 'Retome a VM e desligue-a antes da migração.')
    xml = ET.fromstring(domain.XMLDesc(0 if domain.isActive() else 2))
    guest = xml.find('os/type')
    if guest is None or not guest.get('arch') or not guest.get('machine'):
        raise ValueError('O convidado não informa arquitetura e tipo de máquina.')
    arch, machine, virt = guest.get('arch'), guest.get('machine'), xml.get('type')
    try:
        capabilities = ET.fromstring(target.getDomainCapabilities(None, arch, machine, virt, 0))
        add('Máquina virtual', 'ok', f'Destino reconhece {arch} · {machine} · {virt}.')
    except Exception:
        capabilities = ET.Element('unavailable')
        add('Máquina virtual', 'blocked', f'Libvirt não reconheceu {arch} · {machine} · {virt} no destino.')

    try:
        source_caps = ET.fromstring(manager.connection.getDomainCapabilities(None, arch, machine, virt, 0))
        cpu = cpu_profile(xml, source_caps)
        compat = target.compareHypervisorCPU(None, arch, machine, virt, cpu, 0) if cpu else None
    except Exception:
        compat = None
    if compat is None:
        add('CPU', 'review', 'O modelo ou as instruções da CPU exigem revisão manual nos hospedeiros.')
    elif compat > 0:
        add('CPU', 'ok', 'O hipervisor do destino confirmou o modelo e as instruções do convidado.')
    else:
        add('CPU', 'blocked', 'O modelo ou as instruções do processador são incompatíveis.')

    vcpus = int(xml.findtext('vcpu', '0'))
    memory = xml.find('memory')
    memory_bytes = int(memory.text) * UNITS.get(memory.get('unit', 'KiB').lower(), 0) if memory is not None else 0
    max_vcpus = int(capabilities.find('vcpu').get('max', '0')) if capabilities.find('vcpu') is not None else 0
    try:
        max_memory = target.getInfo()[1] * 1024 ** 2
        free = target.getFreeMemory()
    except Exception:
        max_memory, free = 0, 0
    if (max_vcpus and vcpus > max_vcpus) or (max_memory and memory_bytes > max_memory):
        add('Recursos', 'blocked', 'O destino não oferece o total de vCPUs ou de RAM configurado para a VM.')
    else:
        if not max_vcpus or not memory_bytes or not free or memory_bytes > free:
            add('Recursos', 'review', f'Confira {vcpus} vCPUs e {memory_bytes / GIB:.1f} GiB de memória com a carga prevista.')
        else:
            add('Recursos', 'ok', f'{vcpus} vCPUs e {memory_bytes / GIB:.1f} GiB cabem nos recursos informados.')

    loader = xml.find('os/loader')
    firmware = xml.find('os').get('firmware') == 'efi' or loader is not None or xml.find('os/nvram') is not None
    tpm = xml.find('devices/tpm')
    if firmware:
        supported_firmware = {item.text for item in capabilities.findall("os/enum[@name='firmware']/value")}
        paths = {item.text for item in capabilities.findall('os/loader/value')}
        if 'efi' not in supported_firmware and not paths:
            add('UEFI', 'blocked', 'O destino não declarou um carregador EFI para esta máquina.')
        elif loader is not None and loader.text and loader.text not in paths:
            add('UEFI', 'review', 'Confira o mesmo arquivo de firmware UEFI no destino.')
        elif loader is not None and loader.get('secure') == 'yes' or xml.find("os/firmware/feature[@name='secure-boot'][@enabled='yes']") is not None:
            secure_values = {item.text for item in capabilities.findall("os/loader/enum[@name='secure']/value")}
            add('UEFI', 'ok' if 'yes' in secure_values else 'review',
                'Confira a correspondência do firmware Secure Boot e das chaves.')
        else:
            add('UEFI', 'ok', 'Carregador UEFI disponível para a máquina.')
    if tpm is not None:
        supports_tpm = capabilities.find("devices/tpm[@supported='yes']") is not None
        add('TPM', 'review' if supports_tpm else 'blocked',
            'Confira a transferência do estado TPM.' if supports_tpm else 'TPM virtual indisponível.')
    if mode == 'live-copy' and (xml.find('os/nvram') is not None or tpm is not None or domain.listAllSnapshots(0)):
        add('Cópia ao vivo', 'blocked', 'NVRAM, TPM ou checkpoints exigem outro modo de transferência.')
    elif mode == 'live-copy':
        add('Cópia ao vivo', 'review', 'A conexão de administração foi testada. Confira o transporte TLS entre os servidores.')

    active_networks = {item.name() for item in target.listAllNetworks(0) if item.isActive()}
    requested = {item.get('network') for item in xml.findall("devices/interface[@type='network']/source")
                 if item.get('network')}
    if network:
        requested = {network}
    missing = requested - active_networks
    if missing:
        add('Rede da VM', 'blocked', 'Redes ativas ausentes: ' + ', '.join(sorted(missing)))
    elif requested:
        add('Rede da VM', 'ok', 'Redes ativas: ' + ', '.join(sorted(requested)))
    if not network:
        direct = [item.get('type') for item in xml.findall('devices/interface')
                  if item.get('type') in ('bridge', 'direct', 'hostdev')]
        if direct:
            add('Rede física', 'review', 'Confira pontes, VLANs, dispositivos e vínculo com a rede física.')
    if pool:
        destination_pool = next((item for item in target.listAllStoragePools(0) if item.name() == pool), None)
        minimum = 0
        try:
            for disk in xml.findall("devices/disk[@device='disk']/target"):
                minimum += domain.blockInfo(disk.get('dev'), 0)[1]
        except Exception:
            minimum = 0
        if destination_pool is None or not destination_pool.isActive():
            add('Armazenamento', 'blocked', 'O local de armazenamento do destino precisa estar ativo.')
        elif minimum and destination_pool.info()[3] < minimum:
            add('Armazenamento', 'blocked', 'O espaço livre informado é menor que a alocação dos discos.')
        else:
            add('Armazenamento', 'review', 'Local ativo. Confira o espaço para discos, firmware e estado da VM.')
    elif mode == 'shared':
        add('Armazenamento', 'review', 'Confirme que a origem e o destino acessam os mesmos volumes compartilhados.')
    return results


def check(manager, identifier, destination, mode, pool=None, network=None, name=None):
    import libvirt

    address = checked_uri(destination.strip())
    if address == manager.uri or address == 'test:///default':
        raise ValueError('Selecione outro hospedeiro libvirt real.')
    target = libvirt.openReadOnly(address)
    if target is None:
        raise ValueError('O serviço libvirt de destino está indisponível.')
    try:
        return evaluate(manager, manager.domain(identifier), address, target, mode, pool, network, name)
    finally:
        target.close()
