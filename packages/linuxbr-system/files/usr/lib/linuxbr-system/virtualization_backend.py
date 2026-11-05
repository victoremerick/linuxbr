"""Management of domains, storage and virtual networks through libvirt."""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}')
STATES = {0:'Desconhecida',1:'Em execução',2:'Ocupada',3:'Pausada',4:'Desligando',5:'Desligada',6:'Falha',7:'Suspensa'}
CPU_DEFAULTS='{https://linuxbr.local/vm-defaults}cpu'


def checked_name(value):
    if not isinstance(value,str) or not 1<=len(value)<=80 or not value[0].isalnum() or value!=value.strip() or len(value.encode('utf-8'))>180 or not all(c.isalnum() or c in ' ._-' for c in value):
        raise ValueError('Use até 80 letras, números, espaços, pontos, traços ou sublinhados, começando por uma letra ou número.')
    return value


def checked_uri(value):
    if not isinstance(value,str):raise ValueError('Endereço de hospedeiro inválido.')
    if value in ('qemu:///system','qemu:///session','test:///default'):return value
    match=re.fullmatch(r'qemu\+ssh://[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*(?::(?P<port>[0-9]{1,5}))?/system',value)
    if not match or match.group('port') and not 1<=int(match.group('port'))<=65535:
        raise ValueError('Use qemu:///system, qemu:///session ou qemu+ssh://usuario@servidor/system. Configure a chave SSH e confira o servidor primeiro.')
    return value


def child(parent,tag,text=None,**attrs):
    item=ET.SubElement(parent,tag,{k:str(v) for k,v in attrs.items()})
    if text is not None:item.text=str(text)
    return item


def domain_xml(spec,capabilities):
    name=checked_name(spec['name']);memory=int(spec['memory']);cpus=int(spec['cpus'])
    if not 256<=memory<=262144 or not 1<=cpus<=256:raise ValueError('Memória ou quantidade de processadores fora do intervalo permitido.')
    if spec.get('secure_boot') and not spec.get('uefi',True):raise ValueError('Secure Boot exige firmware UEFI.')
    machine=capabilities.get('machine','q35');kind=capabilities.get('kind','kvm')
    root=ET.Element('domain',type=kind);child(root,'name',name);child(root,'uuid',str(uuid.uuid4()))
    child(root,'memory',memory,unit='MiB');child(root,'currentMemory',memory,unit='MiB');child(root,'vcpu',cpus,placement='static')
    child(child(root,'cpu',mode='host-model' if kind=='kvm' else 'maximum'),'topology',sockets='1',cores=cpus,threads='1')
    child(child(root,'metadata'),CPU_DEFAULTS,topology='single-socket')
    operating=child(root,'os');child(operating,'type','hvm',arch='x86_64',machine=machine)
    if spec.get('uefi',True):
        operating.set('firmware','efi')
        firmware=child(operating,'firmware')
        child(firmware,'feature',enabled='yes' if spec.get('secure_boot') else 'no',name='secure-boot')
        child(firmware,'feature',enabled='yes' if spec.get('secure_boot') else 'no',name='enrolled-keys')
        if spec.get('firmware_template'):
            operating.attrib.pop('firmware',None);operating.remove(firmware)
            child(operating,'loader',spec['firmware_code'],readonly='yes',secure='yes',type='pflash',format='raw')
            child(operating,'nvram',template=spec['firmware_template'],templateFormat='raw',format='raw')
    child(operating,'boot',dev='cdrom' if spec.get('iso') else 'hd');child(operating,'bootmenu',enable='yes')
    features=child(root,'features');child(features,'acpi');child(features,'apic')
    if spec.get('secure_boot'):child(features,'smm',state='on')
    child(root,'clock',offset='localtime' if spec.get('windows') else 'utc')
    child(root,'on_poweroff','destroy');child(root,'on_reboot','restart');child(root,'on_crash','preserve')
    devices=child(root,'devices')
    child(devices,'controller',type='scsi',model='virtio-scsi')
    disk=child(devices,'disk',type='file' if spec.get('disk_path') else 'volume',device='disk');child(disk,'driver',name='qemu',type='qcow2')
    if spec.get('disk_path'):child(disk,'source',file=spec['disk_path'])
    else:child(disk,'source',pool=spec['pool'],volume=spec['volume'])
    child(disk,'target',dev='sda',bus='sata' if spec.get('windows') else 'scsi')
    if spec.get('iso'):
        iso=Path(spec['iso'])
        if not iso.is_absolute() or '\x00' in str(iso):raise ValueError('Selecione o caminho absoluto da imagem ISO no hospedeiro.')
        cd=child(devices,'disk',type='file',device='cdrom');child(cd,'driver',name='qemu',type='raw');child(cd,'source',file=str(iso));child(cd,'target',dev='sdb',bus='sata');child(cd,'readonly')
    if spec.get('network'):
        interface=child(devices,'interface',type='network');child(interface,'source',network=spec['network']);child(interface,'model',type='e1000e' if spec.get('windows') else 'virtio')
    else:child(child(devices,'interface',type='user'),'model',type='e1000e' if spec.get('windows') else 'virtio')
    child(devices,'input',type='tablet',bus='usb');child(devices,'controller',type='usb',model='qemu-xhci')
    graphics=child(devices,'graphics',type='spice',autoport='yes');child(graphics,'listen',type='address',address='127.0.0.1')
    video=child(devices,'video');child(video,'model',type='vga',heads='1',primary='yes')
    if spec.get('tpm'):
        if not spec.get('uefi',True):raise ValueError('TPM virtual exige firmware UEFI neste assistente.')
        child(child(devices,'tpm',model='tpm-crb'),'backend',type='emulator',version='2.0')
    channel=child(devices,'channel',type='unix');child(channel,'target',type='virtio',name='org.qemu.guest_agent.0')
    child(devices,'memballoon',model='virtio')
    return ET.tostring(root,encoding='unicode')


def default_topology(root):
    topology=root.find('cpu/topology');vcpu=root.find('vcpu')
    return root.find('metadata/'+CPU_DEFAULTS) is not None and topology is not None and vcpu is not None and vcpu.get('current') is None and root.find('vcpus') is None and root.find('cpu/numa') is None and topology.get('cores')==vcpu.text and all(value=='1' for key,value in topology.attrib.items() if key!='cores')


def patch_resources(xml,memory,cpus,autostart=None):
    root=ET.fromstring(xml);memory=int(memory);cpus=int(cpus)
    if not 256<=memory<=262144 or not 1<=cpus<=256:raise ValueError('Recursos fora do intervalo permitido.')
    for tag in ('memory','currentMemory'):
        node=root.find(tag)
        if node is None:node=child(root,tag)
        node.text=str(memory);node.set('unit','MiB')
    node=root.find('vcpu')
    if node is None:node=child(root,'vcpu')
    if root.find('cpu/topology') is not None or root.find('vcpus') is not None:
        previous=int(node.text)
        if previous!=cpus:
            if default_topology(root):root.find('cpu/topology').set('cores',str(cpus))
            else:raise ValueError('Esta VM tem topologia de CPU personalizada. Edite a topologia nas opções avançadas antes de mudar o total.')
    node.text=str(cpus)
    return ET.tostring(root,encoding='unicode')


def network_xml(spec):
    name=checked_name(spec['name']);mode=spec['mode'];root=ET.Element('network');child(root,'name',name)
    if mode=='bridge':
        bridge=spec.get('bridge','')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',bridge):raise ValueError('Informe uma ponte de rede existente no hospedeiro.')
        child(root,'forward',mode='bridge');child(root,'bridge',name=bridge)
    elif mode in ('nat','internal','private'):
        if mode=='nat':child(root,'forward',mode='nat')
        if mode!='private':
            subnet=ipaddress.ip_network(spec['subnet'],strict=True)
            if subnet.version!=4 or not 24<=subnet.prefixlen<=28:raise ValueError('Escolha uma sub-rede IPv4 /24 a /28, sem sobreposição com redes existentes.')
            ip=child(root,'ip',address=str(subnet.network_address+1),netmask=str(subnet.netmask))
            child(child(ip,'dhcp'),'range',start=str(subnet.network_address+2),end=str(subnet.broadcast_address-1))
    else:raise ValueError('Tipo de rede não suportado.')
    return ET.tostring(root,encoding='unicode')


class Manager:
    def __init__(self,uri='qemu:///system',connection=None):
        self.uri=checked_uri(uri)
        if connection is None:
            import libvirt
            libvirt.registerErrorHandler(lambda *_:None,None)
            connection=libvirt.open(self.uri)
        if connection is None:raise RuntimeError('Não foi possível conectar ao serviço de virtualização.')
        self.connection=connection

    def close(self):self.connection.close()

    def domains(self):
        result=[]
        for domain in self.connection.listAllDomains(0):
            info=domain.info();root=ET.fromstring(domain.XMLDesc(0))
            result.append(dict(id=domain.UUIDString(),name=domain.name(),state=STATES.get(info[0],str(info[0])),active=bool(domain.isActive()),memory=info[2]//1024,cpus=info[3],cpu_ns=info[4],autostart=bool(domain.autostart()) if domain.isPersistent() else False,description=root.findtext('description','')))
        return sorted(result,key=lambda item:item['name'].casefold())

    def domain(self,identifier):
        uuid.UUID(identifier)
        return self.connection.lookupByUUIDString(identifier)

    def networks(self):
        rows=[]
        for n in self.connection.listAllNetworks(0):
            root=ET.fromstring(n.XMLDesc(0));forward=root.find('forward');ip=root.find('ip')
            mode=forward.get('mode') if forward is not None else ('internal' if ip is not None else 'private')
            rows.append(dict(id=n.UUIDString(),name=n.name(),active=bool(n.isActive()),autostart=bool(n.autostart()),mode=mode,xml=n.XMLDesc(0)))
        return rows

    def pools(self):
        rows=[]
        for pool in self.connection.listAllStoragePools(0):
            if pool.name()=='linuxbr-vm-state':continue
            info=pool.info();root=ET.fromstring(pool.XMLDesc(0))
            rows.append(dict(name=pool.name(),active=bool(pool.isActive()),capacity=info[1],available=info[3],path=root.findtext('target/path',''),kind=root.get('type')))
        return rows

    def capabilities(self):
        root=ET.fromstring(self.connection.getCapabilities());types=[d.get('type') for d in root.findall('guest/arch/domain')]
        return dict(kind='kvm' if 'kvm' in types else 'qemu',machine='q35',host=root.findtext('host/cpu/model',''),uri=self.uri)

    def volume_permissions(self,target):
        capabilities=ET.fromstring(self.connection.getCapabilities())
        for model in capabilities.findall('host/secmodel'):
            if model.findtext('model')!='dac':continue
            labels=model.findall('baselabel')
            label=next((item.text for item in labels if item.get('type') in ('kvm','qemu')),None)
            match=re.fullmatch(r'\+?(\d+):\+?(\d+)',label or '')
            if match:
                permissions=child(target,'permissions');child(permissions,'owner',match[1]);child(permissions,'group',match[2]);child(permissions,'mode','0600');return

    def create(self,spec):
        checked_name(spec['name'])
        if self.uri in ('qemu:///system','qemu:///session') and spec.get('secure_boot'):
            from vm_firmware import TEMPLATE
            if not TEMPLATE.is_file():raise ValueError('O modelo de firmware Secure Boot não está preparado. Reconfigure o pacote linuxbr-system antes de criar esta VM.')
            spec=dict(spec,firmware_template=str(TEMPLATE),firmware_code='/usr/share/OVMF/OVMF_CODE_4M.ms.fd')
        if spec['pool']=='linuxbr-vm-state':raise ValueError('Este local é reservado ao estado protegido das VMs.')
        if any(d['name']==spec['name'] for d in self.domains()):raise ValueError('Já existe uma VM com esse nome.')
        size=int(spec['disk_gib'])
        if not 4<=size<=2048:raise ValueError('Escolha um disco entre 4 e 2048 GiB.')
        pool=self.connection.storagePoolLookupByName(spec['pool'])
        if not pool.isActive():raise ValueError('Ative o local de armazenamento primeiro.')
        if pool.info()[3]<min(size*1024**3,4*1024**3):raise ValueError('O local de armazenamento não tem espaço suficiente para iniciar esta VM.')
        volume=ET.Element('volume');child(volume,'name',spec['name']+'.qcow2');child(volume,'capacity',size,unit='GiB');target=child(volume,'target');child(target,'format',type='qcow2');self.volume_permissions(target)
        spec={**spec,'volume':spec['name']+'.qcow2'}
        xml=domain_xml(spec,self.capabilities())
        created=pool.createXML(ET.tostring(volume,encoding='unicode'),0)
        try:
            # Use the daemon-resolved path so its security profiles can include
            # the managed volume without resolving a pool from a child helper.
            xml=domain_xml(dict(spec,disk_path=created.path()),self.capabilities())
            domain=self.connection.defineXML(xml)
        except Exception:
            # Only the newly created, unattached volume is rolled back.
            created.delete(0);raise
        return domain.UUIDString()

    def action(self,identifier,action):
        domain=self.domain(identifier)
        if action=='start' and self.pending_restore(identifier):raise ValueError('Esta VM tem uma restauração de estado pendente. Conclua a restauração do checkpoint antes de iniciar.')
        methods={'start':domain.create,'shutdown':domain.shutdown,'reboot':lambda:domain.reboot(0),'poweroff':domain.destroy,'pause':domain.suspend,'resume':domain.resume,'save':lambda:domain.managedSave(0),'discard-save':lambda:domain.managedSaveRemove(0)}
        if action not in methods:raise ValueError('Ação desconhecida.')
        methods[action]()

    def resources(self,identifier,memory,cpus,autostart):
        domain=self.domain(identifier)
        self.editable(identifier)
        if domain.isActive():raise ValueError('Desligue a VM para alterar seus recursos persistentes.')
        xml=patch_resources(domain.XMLDesc(2),memory,cpus)
        self.connection.defineXML(xml);domain.setAutostart(bool(autostart))

    def interfaces(self,identifier):
        root=ET.fromstring(self.domain(identifier).XMLDesc(0));rows=[]
        for index,item in enumerate(root.findall('devices/interface')):
            source=item.find('source');mac=item.find('mac');model=item.find('model')
            rows.append(dict(index=index,kind=item.get('type'),source=dict(source.attrib) if source is not None else {},mac=mac.get('address','') if mac is not None else '',model=model.get('type','') if model is not None else '',xml=ET.tostring(item,encoding='unicode')))
        return rows

    def set_interface(self,identifier,index,spec,remove=False):
        domain=self.domain(identifier)
        self.editable(identifier)
        if domain.isActive():raise ValueError('Desligue a VM para editar seus adaptadores.')
        root=ET.fromstring(domain.XMLDesc(2));devices=root.find('devices');items=devices.findall('interface')
        old=None
        if index is not None:
            if not 0<=index<len(items):raise ValueError('Adaptador não encontrado.')
            old=items[index]
        if remove:
            if old is None:raise ValueError('Selecione um adaptador.')
            devices.remove(old)
        else:
            item=copy.deepcopy(old) if old is not None else ET.Element('interface')
            for tag in ('source','model','mac','link','vlan','bandwidth'):
                for element in item.findall(tag):item.remove(element)
            kind=spec.get('kind','network')
            if kind not in ('network','bridge','user'):raise ValueError('Tipo de adaptador inválido.')
            item.set('type',kind)
            if kind in ('network','bridge'):
                name=checked_name(spec['source']);child(item,'source',**{kind:name})
            model=spec.get('model','virtio')
            if model not in ('virtio','e1000e','rtl8139'):raise ValueError('Modelo inválido.')
            child(item,'model',type=model)
            mac=spec.get('mac','').strip()
            if mac:
                if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',mac) or int(mac[:2],16)&1:raise ValueError('Informe um MAC unicast válido.')
                child(item,'mac',address=mac)
            child(item,'link',state='up' if spec.get('connected',True) else 'down')
            if spec.get('vlan'):
                if kind!='bridge':raise ValueError('VLAN exige uma ponte com suporte a marcação configurado no hospedeiro.')
                vlan=int(spec['vlan'])
                if not 1<=vlan<=4094:raise ValueError('VLAN deve estar entre 1 e 4094.')
                child(child(item,'vlan'),'tag',id=vlan)
            bandwidth=int(spec.get('bandwidth',0))
            if not 0<=bandwidth<=10000000:raise ValueError('Limite de banda inválido.')
            if bandwidth:
                b=child(item,'bandwidth');child(b,'inbound',average=bandwidth);child(b,'outbound',average=bandwidth)
            if old is not None:devices.remove(old)
            devices.append(item)
        self.connection.defineXML(ET.tostring(root,encoding='unicode'))

    def define_network(self,spec):
        checked_name(spec['name'])
        if any(n['name']==spec['name'] for n in self.networks()):raise ValueError('Já existe uma rede com esse nome.')
        xml=network_xml(spec)
        if spec['mode'] in ('nat','internal'):
            proposed=ipaddress.ip_network(spec['subnet'])
            for n in self.networks():
                for ip in ET.fromstring(n['xml']).findall('ip'):
                    if ip.get('address') and ':' not in ip.get('address'):
                        existing=ipaddress.ip_network(ip.get('address')+'/'+(ip.get('netmask') or ip.get('prefix','24')),strict=False)
                        if proposed.overlaps(existing):raise ValueError('A sub-rede se sobrepõe a '+n['name']+'.')
        network=self.connection.networkDefineXML(xml)
        return network.UUIDString()

    def network_action(self,identifier,action):
        uuid.UUID(identifier);network=self.connection.networkLookupByUUIDString(identifier)
        if action=='start':network.create()
        elif action=='stop':network.destroy()
        elif action=='autostart':network.setAutostart(not network.autostart())
        elif action=='remove':
            if network.isActive():raise ValueError('Desative a rede antes de remover sua definição.')
            for domain in self.connection.listAllDomains(0):
                if any(n.get('network')==network.name() for n in ET.fromstring(domain.XMLDesc(0)).findall('devices/interface/source')):raise ValueError('Esta rede ainda está associada a '+domain.name()+'.')
            network.undefine()
        else:raise ValueError('Ação de rede inválida.')

    def edit_network(self,identifier,spec):
        uuid.UUID(identifier);network=self.connection.networkLookupByUUIDString(identifier)
        if network.isActive():raise ValueError('Desative a rede antes de alterar sua configuração.')
        root=ET.fromstring(network.XMLDesc(0));candidate=ET.fromstring(network_xml(dict(spec,name=network.name())))
        for n in self.networks():
            if n['id']==identifier:continue
            if spec['mode'] in ('nat','internal'):
                proposed=ipaddress.ip_network(spec['subnet'])
                for address in ET.fromstring(n['xml']).findall('ip'):
                    if ':' not in address.get('address',''):
                        other=ipaddress.ip_network(address.get('address')+'/'+(address.get('netmask') or address.get('prefix','24')),strict=False)
                        if proposed.overlaps(other):raise ValueError('A sub-rede se sobrepõe a '+n['name']+'.')
        if root.find("ip[@family='ipv6']") is not None:raise ValueError('Esta rede tem IPv6 personalizado. Preserve sua configuração pelo administrador de rede antes de alterar o tipo.')
        old_ip=root.find('ip');new_ip=candidate.find('ip')
        if old_ip is not None and new_ip is not None:
            subnet=ipaddress.ip_network(spec['subnet'])
            for host in old_ip.findall('dhcp/host'):
                if host.get('ip') and ipaddress.ip_address(host.get('ip')) not in subnet:raise ValueError('Uma reserva DHCP existente ficaria fora da nova sub-rede.')
            old_ip.attrib.update(new_ip.attrib);old_ip.attrib.pop('prefix',None)
            old_dhcp=old_ip.find('dhcp');new_range=new_ip.find('dhcp/range')
            if old_dhcp is None:old_ip.append(copy.deepcopy(new_ip.find('dhcp')))
            else:
                for item in old_dhcp.findall('range'):old_dhcp.remove(item)
                old_dhcp.append(copy.deepcopy(new_range))
        elif old_ip is not None:root.remove(old_ip)
        elif new_ip is not None:root.append(copy.deepcopy(new_ip))
        for forward in root.findall('forward'):root.remove(forward)
        if candidate.find('forward') is not None:root.append(copy.deepcopy(candidate.find('forward')))
        bridge=root.find('bridge')
        if spec['mode']=='bridge':
            if bridge is None:root.append(copy.deepcopy(candidate.find('bridge')))
            else:bridge.set('name',spec['bridge'])
        self.connection.networkDefineXML(ET.tostring(root,encoding='unicode'))

    def hardware(self,identifier,spec):
        domain=self.domain(identifier)
        self.editable(identifier)
        if domain.isActive():raise ValueError('Desligue a VM antes de alterar firmware e dispositivos.')
        root=ET.fromstring(self.xml(identifier));operating=root.find('os');devices=root.find('devices')
        loader=operating.find('loader');feature=operating.find("firmware/feature[@name='secure-boot']")
        existing_secure=(loader is not None and loader.get('secure')=='yes') or (feature is not None and feature.get('enabled')=='yes')
        if operating.find('nvram') is not None and bool(spec.get('secure_boot'))!=existing_secure:
            raise ValueError('O firmware já possui chaves persistentes. Alterar Secure Boot exige revisar e recriar as variáveis de firmware; a configuração atual foi preservada. Crie uma VM com a opção desejada ou use a configuração avançada após guardar as chaves de recuperação.')
        if spec.get('uefi'):
            if operating.find('loader') is not None:
                operating.attrib.pop('firmware',None)
                for firmware in operating.findall('firmware'):operating.remove(firmware)
            else:
                operating.set('firmware','efi');firmware=operating.find('firmware')
                if firmware is None:firmware=child(operating,'firmware')
                for name in ('secure-boot','enrolled-keys'):
                    feature=next((f for f in firmware.findall('feature') if f.get('name')==name),None)
                    if feature is None:feature=child(firmware,'feature',name=name)
                    feature.set('enabled','yes' if spec.get('secure_boot') else 'no')
        elif operating.get('firmware')=='efi' or operating.find('loader') is not None:
            raise ValueError('A conversão de UEFI para BIOS pode impedir o boot. Crie outra VM com o firmware desejado; o disco atual será preservado.')
        if spec.get('secure_boot'):
            features=root.find('features')
            if features is None:features=child(root,'features')
            smm=features.find('smm')
            if smm is None:smm=child(features,'smm')
            smm.set('state','on')
        if spec.get('tpm') and devices.find('tpm') is None:
            if not spec.get('uefi'):raise ValueError('Selecione UEFI para adicionar o TPM virtual.')
            child(child(devices,'tpm',model='tpm-crb'),'backend',type='emulator',version='2.0')
        elif not spec.get('tpm') and devices.find('tpm') is not None:raise ValueError('O TPM existente foi preservado. Sua remoção pode bloquear volumes criptografados; use a configuração avançada após salvar as chaves de recuperação.')
        video=devices.find('video/model')
        if video is not None:
            if spec['video'] not in ('vga','virtio','qxl'):raise ValueError('Modelo de vídeo inválido.')
            video.set('type',spec['video'])
        sounds=devices.findall('sound')
        if spec.get('audio') and not sounds:child(devices,'sound',model='ich9')
        elif not spec.get('audio'):
            for sound in sounds:devices.remove(sound)
        self.connection.defineXML(ET.tostring(root,encoding='unicode'))

    def guest_options(self,identifier,spec):
        self.editable(identifier);root=ET.fromstring(self.xml(identifier));operating=root.find('os')
        order=spec.get('boot',['hd','cdrom','network'])
        if not isinstance(order,list) or not order or len(set(order))!=len(order) or any(value not in ('hd','cdrom','network') for value in order):raise ValueError('Ordem de inicialização inválida.')
        for boot in operating.findall('boot'):operating.remove(boot)
        for device in root.findall('devices/*'):
            for boot in device.findall('boot'):device.remove(boot)
        for value in order:child(operating,'boot',dev=value)
        menu=operating.find('bootmenu')
        if menu is None:menu=child(operating,'bootmenu')
        menu.set('enable','yes' if spec.get('bootmenu',True) else 'no')
        mode=spec.get('cpu','preserve')
        if mode not in ('preserve','host-model','host-passthrough'):raise ValueError('Modelo de CPU inválido.')
        if mode!='preserve':
            old=root.find('cpu')
            topology=copy.deepcopy(old.find('topology')) if old is not None and default_topology(root) else None
            if old is not None and any(old.find(tag) is not None for tag in ('topology','numa')) and topology is None:raise ValueError('A topologia personalizada deve ser ajustada nas opções avançadas.')
            if old is not None:root.remove(old)
            cpu=child(root,'cpu',mode=mode)
            if topology is not None:cpu.append(topology)
        quota=int(spec.get('cpu_percent',0))
        if not 0<=quota<=100:raise ValueError('Use de 1 a 100% de CPU ou zero para não limitar.')
        tuning=root.find('cputune')
        if tuning is None and quota:tuning=child(root,'cputune')
        if tuning is not None:
            for name in ('global_period','global_quota'):
                for node in tuning.findall(name):tuning.remove(node)
            if quota:child(tuning,'global_period',100000);child(tuning,'global_quota',int(root.findtext('vcpu','1'))*quota*1000)
        self.connection.defineXML(ET.tostring(root,encoding='unicode'))

    def snapshots(self,identifier):
        rows=[]
        for snapshot in self.domain(identifier).listAllSnapshots(0):
            root=ET.fromstring(snapshot.getXMLDesc(0));rows.append(dict(name=snapshot.getName(),parent=root.findtext('parent/name',''),created=root.findtext('creationTime',''),state=root.findtext('state','')))
        return rows

    def update_certificates(self,identifier):
        from datetime import datetime,timezone
        from virtualization_state import State
        import vm_firmware
        self.editable(identifier);root=ET.fromstring(self.xml(identifier));nvram=root.find('os/nvram')
        if nvram is None or nvram.get('format','raw')!='raw':raise ValueError('A atualização de certificados exige variáveis UEFI no formato raw. A configuração atual foi preservada.')
        state=State(self);captured=state.capture(identifier);record=next((item for item in captured['files'] if item['role']=='nvram'),None)
        if record is None:raise ValueError('Variáveis UEFI não encontradas.')
        updated=vm_firmware.enroll(record['data'])
        checkpoint='Antes dos certificados 2023 '+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        self.snapshot(identifier,'create',checkpoint);self.mark_restore(identifier,True)
        state.restore(identifier,dict(files=[dict(record,data=updated)],secrets=[]));self.mark_restore(identifier,False)
        return dict(status='PASS',checkpoint=checkpoint,secure_boot_unchanged=True)

    def snapshot(self,identifier,action,name,memory=False):
        from virtualization_state import State
        domain=self.domain(identifier);checked_name(name);state=State(self)
        if action!='remove' and domain.hasManagedSaveImage(0):raise ValueError('Retome o estado salvo e desligue o convidado antes de alterar checkpoints.')
        if action=='create':
            if any(s.getName()==name for s in domain.listAllSnapshots(0)):raise ValueError('Já existe um checkpoint com esse nome.')
            if memory:
                configuration=ET.fromstring(self.xml(identifier))
                if configuration.find('os/nvram') is not None or configuration.find('os/loader') is not None or configuration.find('os').get('firmware')=='efi' or configuration.find('devices/tpm') is not None:raise ValueError('Checkpoints com memória nesta edição exigem BIOS e ausência de TPM. Para UEFI/TPM, desligue e use um checkpoint combinado ou salve o estado para retomada.')
                if not domain.isActive():raise ValueError('Inicie a VM para capturar sua memória.')
                root=ET.Element('domainsnapshot');child(root,'name',name);child(root,'description','Linux BR: discos e memória da VM BIOS.');child(root,'memory',snapshot='internal')
                domain.snapshotCreateXML(ET.tostring(root,encoding='unicode'),0);return
            if domain.isActive():raise ValueError('Desligue a VM para criar um checkpoint consistente de disco nesta interface.')
            token=state.save(identifier,name);root=ET.Element('domainsnapshot');child(root,'name',name);child(root,'description','Linux BR: estado combinado de discos, firmware e TPM. '+token);child(root,'memory',snapshot='no')
            try:domain.snapshotCreateXML(ET.tostring(root,encoding='unicode'),0)
            except Exception:state.remove(identifier,name);raise
        elif action=='restore':
            if domain.isActive():raise ValueError('Desligue a VM antes de voltar a um checkpoint.')
            snapshot=domain.snapshotLookupByName(name,0);root=ET.fromstring(snapshot.getXMLDesc(0));combined=root.findtext('description','').startswith('Linux BR: estado combinado')
            files=state.load(identifier,name) if combined else None
            if not combined and (root.find('domain/os/nvram') is not None or root.find('domain/devices/tpm') is not None):raise ValueError('Este checkpoint não inclui uma cópia de firmware e TPM. Ele foi preservado para revisão pelo administrador; nenhuma restauração foi iniciada.')
            self.mark_restore(identifier,True)
            import libvirt
            flags=libvirt.VIR_DOMAIN_SNAPSHOT_REVERT_PAUSED if root.findtext('state') in ('running','paused') else 0
            domain.revertToSnapshot(snapshot,flags);self.mark_restore(identifier,True)
            if files:state.restore(identifier,files)
            self.mark_restore(identifier,False)
        elif action=='remove':
            snapshot=domain.snapshotLookupByName(name,0);combined=ET.fromstring(snapshot.getXMLDesc(0)).findtext('description','').startswith('Linux BR: estado combinado');snapshot.delete(0)
            if combined:state.remove(identifier,name)
        else:raise ValueError('Ação inválida.')

    def pending_restore(self,identifier):
        root=ET.fromstring(self.xml(identifier));return root.find('metadata/{https://linuxbr.local/vm-state}restore') is not None

    def mark_restore(self,identifier,pending):
        import libvirt
        value='<restore xmlns="https://linuxbr.local/vm-state" pending="yes"/>' if pending else None
        self.domain(identifier).setMetadata(libvirt.VIR_DOMAIN_METADATA_ELEMENT,value,'linuxbr','https://linuxbr.local/vm-state',libvirt.VIR_DOMAIN_AFFECT_CONFIG)

    def undefine(self,identifier):
        domain=self.domain(identifier)
        if domain.isActive():raise ValueError('Desligue a VM antes de remover sua definição.')
        if domain.listAllSnapshots(0):raise ValueError('Remova os metadados dos checkpoints antes de remover a definição.')
        # Keep firmware, TPM state and all storage; never unlink a disk here.
        import libvirt
        flags=getattr(libvirt,'VIR_DOMAIN_UNDEFINE_KEEP_NVRAM',0)|getattr(libvirt,'VIR_DOMAIN_UNDEFINE_KEEP_TPM',0)
        domain.undefineFlags(flags)

    def xml(self,identifier):return self.domain(identifier).XMLDesc(2)

    def editable(self,identifier):
        domain=self.domain(identifier)
        if domain.isActive():raise ValueError('Desligue a VM para editar sua configuração.')
        if domain.hasManagedSaveImage(0):raise ValueError('Retome o estado salvo e desligue o convidado antes de alterar seu hardware.')
        if self.pending_restore(identifier):raise ValueError('Conclua a restauração pendente antes de editar a VM.')

    def export_bundle(self,identifier,path):
        from virtualization_transfer import export_bundle
        return export_bundle(self,identifier,path)

    def import_bundle(self,path,pool,name,new_identity=True,network=''):
        from virtualization_transfer import import_bundle
        return import_bundle(self,path,pool,name,new_identity,network)

    def clone(self,identifier,pool,name):
        import tempfile
        checked_name(name);self.editable(identifier)
        with tempfile.TemporaryDirectory(prefix='linuxbr-vm-clone-') as folder:
            self.export_bundle(identifier,str(Path(folder)/'copy'))
            return self.import_bundle(str(Path(folder)/'copy'),pool,name,True,'preserve')

    def storage(self,identifier):
        rows=[]
        for i,disk in enumerate(ET.fromstring(self.xml(identifier)).findall('devices/disk')):
            source=disk.find('source');target=disk.find('target');driver=disk.find('driver')
            rows.append(dict(index=i,device=disk.get('device'),source=dict(source.attrib) if source is not None else {},target=dict(target.attrib) if target is not None else {},format=driver.get('type','') if driver is not None else '',xml=ET.tostring(disk,encoding='unicode')))
        return rows

    def storage_action(self,identifier,action,spec):
        domain=self.domain(identifier)
        self.editable(identifier)
        if domain.isActive():raise ValueError('Desligue a VM para alterar discos e mídias.')
        root=ET.fromstring(self.xml(identifier));devices=root.find('devices');disks=devices.findall('disk')
        if action=='detach':
            index=int(spec['index'])
            if not 0<=index<len(disks):raise ValueError('Dispositivo não encontrado.')
            devices.remove(disks[index])
        elif action=='iso':
            path=spec.get('path','')
            if path and (not Path(path).is_absolute() or '\x00' in path):raise ValueError('Informe o caminho absoluto da ISO no hospedeiro.')
            cd=next((disk for disk in disks if disk.get('device')=='cdrom'),None)
            if cd is None:
                cd=child(devices,'disk',type='file',device='cdrom');child(cd,'driver',name='qemu',type='raw');child(cd,'target',dev='sdd',bus='sata');child(cd,'readonly')
            for source in cd.findall('source'):cd.remove(source)
            if path:child(cd,'source',file=path)
        elif action=='attach':
            if spec['pool']=='linuxbr-vm-state':raise ValueError('O armazenamento de estado não pode ser conectado como disco de uma VM.')
            pool=self.connection.storagePoolLookupByName(spec['pool']);volume=pool.storageVolLookupByName(spec['volume'])
            for other in self.connection.listAllDomains(0):
                for disk in ET.fromstring(other.XMLDesc(2)).findall('devices/disk'):
                    source=disk.find('source')
                    if source is not None and (source.get('file')==volume.path() or source.get('pool')==spec['pool'] and source.get('volume')==spec['volume']):raise ValueError('O disco já pertence à VM '+other.name()+'. Não é seguro conectar o mesmo disco gravável a duas VMs.')
            self.no_backing_dependents(volume.path())
            info=ET.fromstring(volume.XMLDesc(0));format=info.find('target/format')
            if format is None or format.get('type') not in ('qcow2','raw'):raise ValueError('O formato do volume não é suportado neste editor.')
            if any(d.find('source') is not None and (d.find('source').attrib==dict(pool=spec['pool'],volume=spec['volume']) or d.find('source').get('file')==volume.path()) for d in disks):raise ValueError('Volume já conectado.')
            targets={d.find('target').get('dev') for d in disks if d.find('target') is not None}
            target=next(('sd'+letter for letter in 'abcdefghijklmnopqrstuvwxyz' if 'sd'+letter not in targets),None)
            if not target:raise ValueError('Não há posição livre neste controlador.')
            disk=child(devices,'disk',type='file',device='disk');child(disk,'driver',name='qemu',type=format.get('type'));child(disk,'source',file=volume.path());child(disk,'target',dev=target,bus='scsi')
            if not any(c.get('type')=='scsi' for c in devices.findall('controller')):child(devices,'controller',type='scsi',model='virtio-scsi')
        else:raise ValueError('Operação de armazenamento inválida.')
        self.connection.defineXML(ET.tostring(root,encoding='unicode'))

    def volumes(self,pool_name):
        pool=self.connection.storagePoolLookupByName(pool_name)
        return [dict(name=v.name(),path=v.path(),capacity=v.info()[1],allocated=v.info()[2]) for v in pool.listAllVolumes(0)]

    def no_backing_dependents(self,path):
        for pool in self.connection.listAllStoragePools(0):
            if not pool.isActive():continue
            for volume in pool.listAllVolumes(0):
                if any(node.text==path for node in ET.fromstring(volume.XMLDesc(0)).findall('.//backingStore/path')):raise ValueError('Este disco é base de '+volume.name()+'. Preserve sua cadeia de dependências antes de alterar ou conectar para gravação.')

    def create_volume(self,pool_name,name,size_gib):
        if pool_name=='linuxbr-vm-state':raise ValueError('Local reservado ao estado protegido de VMs.')
        checked_name(name);size=int(size_gib)
        if not 1<=size<=2048:raise ValueError('Tamanho fora do intervalo de 1 a 2048 GiB.')
        pool=self.connection.storagePoolLookupByName(pool_name)
        if pool.info()[3]<1024**3:raise ValueError('O local de armazenamento tem menos de 1 GiB livre.')
        xml=ET.Element('volume');child(xml,'name',name+'.qcow2');child(xml,'capacity',size,unit='GiB');target=child(xml,'target');child(target,'format',type='qcow2');self.volume_permissions(target)
        return pool.createXML(ET.tostring(xml,encoding='unicode'),0).name()

    def resize_volume(self,pool_name,name,size_gib):
        if pool_name=='linuxbr-vm-state':raise ValueError('Local reservado ao estado protegido de VMs.')
        pool=self.connection.storagePoolLookupByName(pool_name);volume=pool.storageVolLookupByName(name)
        target=int(size_gib)*1024**3
        if target<=volume.info()[1]:raise ValueError('Somente expansão é permitida; o tamanho novo deve ser maior que o atual.')
        path=volume.path()
        self.no_backing_dependents(path)
        for domain in self.connection.listAllDomains(0):
            for d in self.storage(domain.UUIDString()):
                source=d['source']
                if source.get('file')==path or (source.get('pool')==pool_name and source.get('volume')==name):
                    if domain.isActive() or self.snapshots(domain.UUIDString()):raise ValueError('Desligue a VM e remova seus checkpoints antes de expandir o volume.')
        volume.resize(target,0)

    def create_pool(self,name,path,internal=False):
        if name=='linuxbr-vm-state' and not internal:raise ValueError('Nome reservado ao estado protegido de VMs.')
        checked_name(name)
        if any(pool.name()==name for pool in self.connection.listAllStoragePools(0)):raise ValueError('Já existe um local com esse nome. Sua definição foi preservada.')
        if not Path(path).is_absolute() or path=='/' or '\x00' in path:raise ValueError('Informe um diretório absoluto de armazenamento no hospedeiro.')
        root=ET.Element('pool',type='dir');child(root,'name',name);child(child(root,'target'),'path',path)
        pool=self.connection.storagePoolDefineXML(ET.tostring(root,encoding='unicode'),0)
        try:pool.build(0);pool.create(0);pool.setAutostart(True)
        except Exception:
            pool.undefine();raise
        return pool.name()

    def pool_action(self,name,action):
        if name=='linuxbr-vm-state':raise ValueError('O armazenamento de estado é gerenciado junto aos checkpoints das VMs.')
        pool=self.connection.storagePoolLookupByName(name)
        if action=='start':pool.create(0);return
        if action=='autostart':pool.setAutostart(not pool.autostart());return
        root=ET.fromstring(pool.XMLDesc(0));path=root.findtext('target/path','')
        if action in ('stop','remove'):
            for domain in self.connection.listAllDomains(0):
                if action=='stop' and not domain.isActive():continue
                for source in ET.fromstring(domain.XMLDesc(0)).findall('.//disk/source'):
                    if source.get('pool')==name or path and any(value==path or value.startswith(path.rstrip('/')+'/') for value in source.attrib.values()):raise ValueError('O local ainda é utilizado por '+domain.name()+'.')
            if action=='stop':pool.destroy()
            else:
                if pool.isActive():raise ValueError('Desative o local antes de remover sua definição.')
                pool.undefine()
        else:raise ValueError('Ação de armazenamento inválida.')

    def replace_xml(self,identifier,text):
        domain=self.domain(identifier)
        self.editable(identifier)
        if domain.isActive():raise ValueError('Desligue a VM para editar sua configuração avançada.')
        if len(text)>1048576 or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('XML inválido.')
        root=ET.fromstring(text)
        if root.tag!='domain' or root.findtext('uuid')!=identifier or root.findtext('name')!=domain.name():raise ValueError('A edição deve preservar nome e identificador desta VM.')
        original=self.xml(identifier)
        folder=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'linuxbr/virtualization'
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        backup=folder/(str(uuid.uuid4())+'.xml');backup.write_text(original);backup.chmod(0o600)
        self.connection.defineXML(text)
        return str(backup)

    def migrate(self,identifier,destination,live=False):
        import libvirt
        checked_uri(destination)
        if destination==self.uri:raise ValueError('Escolha outro hospedeiro.')
        domain=self.domain(identifier)
        if domain.hasManagedSaveImage(0):raise ValueError('Retome e desligue a VM antes de migrar um estado salvo.')
        if domain.isActive() and not live:raise ValueError('Desligue a VM ou selecione migração ao vivo explicitamente.')
        target=libvirt.open(destination)
        if target is None:raise ValueError('Destino indisponível.')
        try:
            flags=libvirt.VIR_MIGRATE_PERSIST_DEST
            if domain.isPersistent():flags|=libvirt.VIR_MIGRATE_UNDEFINE_SOURCE
            if live:flags|=libvirt.VIR_MIGRATE_LIVE
            else:flags|=libvirt.VIR_MIGRATE_OFFLINE
            domain.migrate(target,flags,None,None,0)
        finally:target.close()
