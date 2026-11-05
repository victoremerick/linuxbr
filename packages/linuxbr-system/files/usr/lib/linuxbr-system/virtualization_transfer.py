"""Offline VM bundles with disk, firmware and TPM integrity checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import uuid
import xml.etree.ElementTree as ET
from virtualization_state import State,element


def file_hash(path,cancelled=None):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(1024*1024):
            if cancelled and cancelled():raise ValueError('Conferência de integridade cancelada.')
            value.update(data)
    return value.hexdigest()


def local_file(root,name):
    if not isinstance(name,str) or '/' in name or '\\' in name or name in ('','.','..'):raise ValueError('Nome de arquivo inválido na cópia da VM.')
    path=root/name
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):raise ValueError('A cópia deve conter somente arquivos regulares, sem links.')
    return path


def validate_disk(path,format,capacity):
    with path.open('rb') as source:header=source.read(104)
    validate_header(header,path.stat().st_size,format,capacity)


def validate_header(header,length,format,capacity):
    if not isinstance(capacity,int) or not 0<capacity<=64*1024**4:raise ValueError('Capacidade do disco inválida.')
    if format=='raw':
        if length!=capacity:raise ValueError('O tamanho do disco bruto não corresponde à capacidade.')
        return
    if format!='qcow2':raise ValueError('Formato de disco não permitido.')
    if len(header)<72 or header[:4]!=b'QFI\xfb':raise ValueError('Cabeçalho QCOW2 inválido.')
    version=struct.unpack_from('>I',header,4)[0]
    if version not in (2,3):raise ValueError('Versão QCOW2 não suportada.')
    backing,backing_size=struct.unpack_from('>QI',header,8)
    size=struct.unpack_from('>Q',header,24)[0];encryption=struct.unpack_from('>I',header,32)[0]
    features=struct.unpack_from('>Q',header,72)[0] if version==3 and len(header)>=104 else 0
    if backing or backing_size or encryption or features & ~0x18:raise ValueError('O disco precisa ser independente, íntegro e sem arquivos externos ou criptografia do hospedeiro.')
    if size!=capacity:raise ValueError('A capacidade QCOW2 não confere com o manifesto.')


def download(manager,volume,path):
    stream=manager.connection.newStream(0);count=0;previous=-1
    size=int(ET.fromstring(volume.XMLDesc(0)).findtext('physical','0'))
    with path.open('xb') as output:
        path.chmod(0o600)
        def receive(_stream,data,_opaque):
            nonlocal count,previous
            if getattr(manager,'cancelled',lambda:False)():raise ValueError('Exportação cancelada. A VM original foi preservada.')
            output.write(data);count+=len(data);percent=min(99,int(count*100/size)) if size else 0
            if percent!=previous and hasattr(manager,'progress'):manager.progress(percent);previous=percent
            return len(data)
        try:volume.download(stream,0,0,0);stream.recvAll(receive,None);stream.finish();output.flush();os.fsync(output.fileno())
        except Exception:
            stream.abort();raise
    return count


def upload(manager,volume,path,record=None):
    size=path.stat().st_size;stream=manager.connection.newStream(0);count=0;previous=-1;digest=hashlib.sha256();header=bytearray()
    with path.open('rb') as source:
        def send(_stream,amount,_opaque):
            nonlocal count,previous
            if getattr(manager,'cancelled',lambda:False)():raise ValueError('Importação cancelada; confira o resultado e os arquivos preservados.')
            data=source.read(amount);count+=len(data);percent=min(99,int(count*100/size)) if size else 0
            digest.update(data)
            if len(header)<104:header.extend(data[:104-len(header)])
            if percent!=previous and hasattr(manager,'progress'):manager.progress(percent);previous=percent
            return data
        try:volume.upload(stream,0,size,0);stream.sendAll(send,None);stream.finish()
        except Exception:
            stream.abort();raise
    if record is not None:
        if count!=record['size'] or digest.hexdigest()!=record['sha256']:raise ValueError('O arquivo foi alterado durante a cópia. A importação foi cancelada antes de iniciar a VM.')
        validate_header(header,count,record['format'],record['capacity'])


def export_bundle(manager,identifier,destination):
    domain=manager.domain(identifier)
    if domain.isActive() or domain.hasManagedSaveImage(0):raise ValueError('Desligue o convidado normalmente antes de exportar. Um estado salvo deve ser retomado e desligado primeiro.')
    if manager.pending_restore(identifier):raise ValueError('Conclua a restauração pendente antes de exportar.')
    folder=Path(destination).expanduser().absolute()
    if folder.exists() or folder.is_symlink():raise ValueError('Escolha um novo diretório para a cópia, sem substituir arquivos existentes.')
    if not folder.parent.is_dir():raise ValueError('O diretório de destino não existe.')
    root=ET.fromstring(manager.xml(identifier));state=State(manager);hardware=state.capture(identifier);root=ET.fromstring(manager.xml(identifier));connection=manager.connection
    info=dict(kind='linuxbr-vm-bundle',version=1,name=domain.name(),uuid=identifier,disks=[],files=[],secrets=[],snapshot_catalog_included=False)
    folder.mkdir(mode=0o700);created=[]
    try:
        for index,disk in enumerate(root.findall('devices/disk')):
            if disk.get('device')!='disk':continue
            source=disk.find('source')
            if source is None:raise ValueError('Um dos discos não tem origem identificada.')
            if disk.get('type')=='volume':
                pool=connection.storagePoolLookupByName(source.get('pool'));volume=pool.storageVolLookupByName(source.get('volume'))
                context=None
            elif disk.get('type')=='file':
                context=state.file_volume(source.get('file'));volume=context.__enter__()
            else:raise ValueError('Exporte separadamente os discos de rede ou de bloco antes de criar este tipo de cópia.')
            temporary=None
            try:
                volume_xml=ET.fromstring(volume.XMLDesc(0));format=volume_xml.find('target/format');format=format.get('type') if format is not None else 'raw'
                if format not in ('qcow2','raw') or volume_xml.find('backingStore/path') is not None:
                    pool=state.pool();capacity=volume.info()[1]
                    if pool.info()[3]<capacity:raise ValueError('O servidor precisa de espaço livre equivalente à capacidade do disco para consolidar sua cadeia antes de exportar.')
                    target=ET.Element('volume');element(target,'name','export-'+uuid.uuid4().hex+'.qcow2');element(target,'capacity',capacity,unit='bytes');element(element(target,'target'),'format',type='qcow2')
                    temporary=pool.createXMLFrom(ET.tostring(target,encoding='unicode'),volume,0);volume=temporary;format='qcow2';volume_xml=ET.fromstring(volume.XMLDesc(0))
                size=int(volume_xml.findtext('physical','0'))
                if os.statvfs(folder).f_bavail*os.statvfs(folder).f_frsize<size+512*1024**2:raise ValueError('O destino não tem espaço suficiente para copiar o próximo disco e manter uma reserva de 512 MiB.')
                filename='disk-'+str(index)+'.'+format;path=folder/filename;download(manager,volume,path)
                info['disks'].append(dict(index=index,file=filename,format=format,capacity=volume.info()[1],size=path.stat().st_size,sha256=file_hash(path)))
            finally:
                if temporary is not None:temporary.delete(0)
                if context is not None:context.__exit__(None,None,None)
        for group in ('files','secrets'):
            for index,item in enumerate(hardware[group]):
                filename='state-'+group+'-'+str(index)+'.bin';path=folder/filename
                with path.open('xb') as stream:stream.write(item['data']);stream.flush();os.fsync(stream.fileno())
                path.chmod(0o600);info[group].append(dict({k:v for k,v in item.items() if k not in ('data','path')},file=filename,size=path.stat().st_size,sha256=file_hash(path)))
        if domain.isActive():raise ValueError('A VM foi iniciada por outro cliente durante a cópia. A exportação foi recusada; mantenha a VM desligada até concluir.')
        xml=folder/'domain.xml';xml.write_text(ET.tostring(root,encoding='unicode'));xml.chmod(0o600);info['xml_sha256']=file_hash(xml)
        manifest=folder/'manifest.json';manifest.write_text(json.dumps(info,ensure_ascii=False,indent=2));manifest.chmod(0o600)
        return dict(path=str(folder),disks=len(info['disks']),hardware_files=len(info['files']),contains_private_state=True)
    except Exception:
        # This directory was exclusively created for the current export.
        if folder.resolve().parent==folder.parent.resolve() and not folder.is_symlink():shutil.rmtree(folder)
        raise


def inspect_bundle(directory,cancelled=None):
    folder=Path(directory).expanduser().resolve(strict=True)
    if not folder.is_dir():raise ValueError('Selecione o diretório da cópia de VM.')
    path=local_file(folder,'manifest.json')
    if path.stat().st_size>1048576:raise ValueError('Manifesto muito grande.')
    manifest=json.loads(path.read_text())
    if manifest.get('kind')!='linuxbr-vm-bundle' or manifest.get('version')!=1:raise ValueError('Formato de cópia não reconhecido.')
    uuid.UUID(manifest['uuid']);xml=local_file(folder,'domain.xml')
    if xml.stat().st_size>1048576 or file_hash(xml)!=manifest.get('xml_sha256'):raise ValueError('A configuração não confere com o manifesto.')
    text=xml.read_text()
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('Configuração XML inválida.')
    root=ET.fromstring(text)
    if root.tag!='domain' or root.findtext('uuid')!=manifest['uuid']:raise ValueError('A configuração não corresponde à identidade da cópia.')
    if root.get('type') not in ('kvm','qemu') or root.findtext('os/type')!='hvm' or root.find('os/type').get('arch')!='x86_64':raise ValueError('Esta cópia não é uma máquina QEMU x86_64 compatível.')
    for group in ('disks','files','secrets'):
        rows=manifest.get(group,[])
        if not isinstance(rows,list) or len(rows)>64:raise ValueError('Lista de arquivos inválida.')
        for item in rows:
            path=local_file(folder,item['file'])
            if group!='disks' and path.stat().st_size>64*1024**2:raise ValueError('Arquivo de estado muito grande.')
            if path.stat().st_size!=item['size'] or file_hash(path,cancelled)!=item['sha256']:raise ValueError('Integridade divergente em '+item['file']+'. Nenhuma VM foi criada.')
    disks=root.findall('devices/disk');indexes=[item['index'] for item in manifest['disks']]
    if any(type(index) is not int for index in indexes) or len(set(indexes))!=len(indexes) or set(indexes)!={index for index,disk in enumerate(disks) if disk.get('device')=='disk'}:raise ValueError('A cópia não contém exatamente todos os discos da definição.')
    for item in manifest['disks']:validate_disk(local_file(folder,item['file']),item['format'],item['capacity'])
    identities=set()
    if sum(item['size'] for item in manifest['files'])>128*1024**2 or sum(item['size'] for item in manifest['secrets'])>4*1024**2:raise ValueError('O conjunto de estados excede os limites desta edição.')
    for item in manifest['files']:
        identity=(item.get('role'),item.get('index'))
        if identity in identities or identity[0] not in ('nvram','tpm') or identity[0]=='nvram' and identity[1] is not None or identity[0]=='tpm' and (type(identity[1]) is not int or not 0<=identity[1]<8):raise ValueError('Identidade de estado de firmware ou TPM inválida.')
        identities.add(identity);checked_state_data(folder,item,root)
    for item in manifest['secrets']:
        if item['size']>65536:raise ValueError('Segredo do TPM muito grande.')
        secret=ET.fromstring(item['xml']);uuid.UUID(item['id'])
        if secret.tag!='secret' or secret.findtext('uuid')!=item['id'] or secret.find('usage').get('type')!='vtpm':raise ValueError('Segredo do TPM inválido.')
    return manifest,root


def checked_state_data(folder,item,root):
    data=local_file(folder,item['file']).read_bytes()
    if len(data)!=item['size'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Um arquivo de estado mudou depois da conferência. A importação foi interrompida.')
    if item.get('role')=='nvram':
        nvram=root.find('os/nvram')
        if nvram is not None and nvram.get('format')=='qcow2':
            if len(data)<104:raise ValueError('Imagem de variáveis UEFI inválida.')
            capacity=struct.unpack_from('>Q',data,24)[0]
            if capacity>64*1024**2:raise ValueError('Imagem de variáveis UEFI muito grande.')
            validate_header(data[:104],len(data),'qcow2',capacity)
    return data


def import_bundle(manager,directory,pool_name,name,new_identity=True,network=''):
    from virtualization_backend import checked_name
    checked_name(name);manifest,root=inspect_bundle(directory,getattr(manager,'cancelled',None));folder=Path(directory).resolve();connection=manager.connection;state=State(manager)
    if pool_name=='linuxbr-vm-state':raise ValueError('Escolha um local de discos de VM, não o armazenamento de estado.')
    if any(row['name']==name or not new_identity and row['id']==manifest['uuid'] for row in manager.domains()):raise ValueError('Já existe uma VM com esse nome ou identidade. Nenhuma VM existente foi substituída.')
    if any(root.findall('devices/'+tag) for tag in ('hostdev','filesystem','shmem')) or any(node.tag.startswith('{') for node in root if node.tag!='metadata'):raise ValueError('Esta cópia contém acesso direto ao hospedeiro ou extensões personalizadas. Revise esses recursos pela importação avançada de definição antes de usar em outro computador.')
    if any(root.find(tag) is not None for tag in ('bootloader','bootloader_args','sysinfo','os/kernel','os/initrd','os/init','os/dtb','os/acpi','os/nvram/source','launchSecurity')):raise ValueError('A cópia depende de arquivos ou inicialização personalizados do hospedeiro. Revise a definição antes de importar.')
    memory=root.find('memory');unit=memory.get('unit','KiB');factors={'bytes':1,'B':1,'KiB':1024,'k':1024,'MiB':1024**2,'M':1024**2,'GiB':1024**3,'G':1024**3}
    if unit not in factors or not memory.text.isdigit():raise ValueError('Memória da cópia inválida.')
    if int(memory.text)*factors[unit]>connection.getInfo()[1]*1024**2:raise ValueError('A cópia exige mais memória que a memória física deste hospedeiro. Ajuste os recursos antes de importar.')
    root.set('type',manager.capabilities()['kind'])
    for tag in ('resource','memoryBacking'):
        for node in root.findall(tag):root.remove(node)
    identifier=str(uuid.uuid4()) if new_identity else manifest['uuid'];root.find('name').text=name;root.find('uuid').text=identifier
    if root.find('genid') is not None:root.find('genid').text=str(uuid.uuid4())
    for label in root.findall('seclabel'):root.remove(label)
    operating=root.find('os');nvram=operating.find('nvram');loader=operating.find('loader')
    if nvram is not None or operating.get('firmware')=='efi':
        secure=loader is not None and loader.get('secure')=='yes'
        operating.set('firmware','efi')
        if secure:
            firmware=operating.find('firmware')
            if firmware is None:firmware=element(operating,'firmware')
            for name in ('secure-boot','enrolled-keys'):
                feature=firmware.find("feature[@name='"+name+"']")
                if feature is None:feature=element(firmware,'feature',name=name)
                feature.set('enabled','yes')
        if loader is not None:operating.remove(loader)
        if nvram is not None:
            format=nvram.get('format','raw')
            if format not in ('raw','qcow2'):raise ValueError('Formato de firmware não suportado.')
            operating.remove(nvram);element(operating,'nvram',format=format)
    devices=root.find('devices');disks=devices.findall('disk');pool=connection.storagePoolLookupByName(pool_name)
    allowed={'emulator','disk','controller','interface','channel','input','graphics','audio','sound','video','watchdog','memballoon','tpm','panic','rng','vsock','iommu'}
    if any(node.tag not in allowed for node in devices):raise ValueError('A cópia contém dispositivos que exigem revisão de compatibilidade antes da importação.')
    for emulator in devices.findall('emulator'):devices.remove(emulator)
    for device in devices.findall('vsock'):
        devices.remove(device);element(element(devices,'vsock',model='virtio'),'cid',auto='yes')
    for tag in ('graphics','audio','video','rng','input'):
        for node in devices.findall(tag):devices.remove(node)
    graphics=element(devices,'graphics',type='spice',autoport='yes');element(graphics,'listen',type='address',address='127.0.0.1');element(devices,'audio',id='1',type='spice');element(element(devices,'video'),'model',type='vga',heads='1',primary='yes');element(devices,'input',type='tablet',bus='usb')
    for sound in devices.findall('sound'):
        for audio in sound.findall('audio'):sound.remove(audio)
        element(sound,'audio',id='1')
    if not pool.isActive():raise ValueError('Ative o local de armazenamento antes de importar.')
    if pool.info()[3]<sum(item['size'] for item in manifest['disks'])+512*1024**2:raise ValueError('O hospedeiro não tem espaço suficiente para a cópia e uma reserva de 512 MiB.')
    for disk in disks:
        if disk.get('device') not in ('disk','cdrom') or disk.find('encryption') is not None:raise ValueError('A cópia contém um disco especial ou criptografia do hospedeiro que exige revisão de chaves.')
        if disk.get('device')=='cdrom':
            for source in disk.findall('source'):disk.remove(source)
        for label in disk.findall('seclabel'):disk.remove(label)
        for node in list(disk):
            if node.tag not in ('source','target','driver','address','alias','boot','readonly','serial','wwn','vendor','product'):disk.remove(node)
        driver=disk.find('driver')
        if driver is not None:driver.attrib.clear();driver.set('name','qemu')
    for interface in devices.findall('interface'):
        for node in interface.findall('target'):interface.remove(node)
        if new_identity:
            for mac in interface.findall('mac'):interface.remove(mac)
        if network!='preserve':
            for node in list(interface):
                if node.tag not in ('model','mac','link','address','alias'):interface.remove(node)
            interface.set('type','network' if network else 'user')
            if network:element(interface,'source',network=network)
        else:
            if interface.get('type') not in ('network','bridge','user'):raise ValueError('O adaptador personalizado precisa ser remapeado para uma rede do destino.')
            if any(node.tag not in ('source','model','mac','link','address','alias','boot','vlan','bandwidth') for node in interface):raise ValueError('Revise as extensões do adaptador antes de preservar a rede original.')
    for channel in devices.findall('channel'):
        if channel.get('type')!='unix':raise ValueError('Revise o canal personalizado da cópia antes de importar.')
        for source in channel.findall('source'):channel.remove(source)
    for tag in ('serial','parallel','console','redirdev'):
        for node in devices.findall(tag):devices.remove(node)
    for tpm in devices.findall('tpm'):
        backend=tpm.find('backend')
        if backend is None or backend.get('type')!='emulator':raise ValueError('A cópia depende de um TPM físico não transferível.')
        for source in backend.findall('source'):backend.remove(source)
        encryption=backend.find('encryption')
        if encryption is not None and encryption.get('secret') not in {item['id'] for item in manifest['secrets']}:raise ValueError('A cópia não contém a chave de criptografia do TPM.')
    created=[];domain=None;new_secrets=[]
    try:
        for item in manifest['secrets']:
            data=checked_state_data(folder,item,root)
            try:secret=connection.secretLookupByUUIDString(item['id'])
            except __import__('libvirt').libvirtError as error:
                if error.get_error_code()!=__import__('libvirt').VIR_ERR_NO_SECRET:raise
                secret=connection.secretDefineXML(item['xml'],0);new_secrets.append(secret)
            else:
                if bytes(secret.value(0))!=data:raise ValueError('O destino já tem um segredo com a mesma identidade e outro conteúdo. O segredo existente foi preservado.')
            secret.setValue(data,0)
        for item in manifest['disks']:
            index=int(item['index'])
            if not 0<=index<len(disks) or disks[index].get('device')!='disk' or item['format'] not in ('qcow2','raw'):raise ValueError('Disco da cópia não corresponde à configuração.')
            xml=ET.Element('volume');element(xml,'name',name+'-'+str(index)+'.'+item['format']);element(xml,'capacity',int(item['capacity']),unit='bytes');target=element(xml,'target');element(target,'format',type=item['format']);manager.volume_permissions(target)
            volume=pool.createXML(ET.tostring(xml,encoding='unicode'),0);created.append(volume);upload(manager,volume,local_file(folder,item['file']),item)
            disk=disks[index];disk.set('type','file')
            for source in disk.findall('source'):disk.remove(source)
            element(disk,'source',file=volume.path());driver=disk.find('driver')
            if driver is None:driver=element(disk,'driver',name='qemu')
            driver.set('type',item['format'])
        expected={int(item['index']) for item in manifest['disks']}
        if expected!={index for index,disk in enumerate(disks) if disk.get('device')=='disk'}:raise ValueError('A cópia não contém todos os discos da definição.')
        domain=connection.defineXML(ET.tostring(root,encoding='unicode'));domain.setAutostart(False)
        if manifest['files']:
            import libvirt
            # Initialize destination ownership and security state while all
            # virtual CPUs remain paused; no guest software is executed.
            domain.createWithFlags(libvirt.VIR_DOMAIN_START_PAUSED);domain.destroy();dest=state.capture(identifier);records=[]
            for item in manifest['files']:
                target=next((record for record in dest['files'] if record['role']==item['role'] and record.get('index')==item.get('index')),None)
                if target is None:raise ValueError('O hardware do destino não corresponde ao estado exportado.')
                records.append(dict(target,data=checked_state_data(folder,item,root)))
            state.restore(identifier,dict(files=records,secrets=[]))
        return dict(id=identifier,name=name,disks=len(created),state='Desligada')
    except Exception:
        if domain is not None:
            if domain.isActive():domain.destroy()
            import libvirt
            domain.undefineFlags(getattr(libvirt,'VIR_DOMAIN_UNDEFINE_NVRAM',0)|getattr(libvirt,'VIR_DOMAIN_UNDEFINE_TPM',0))
        for volume in reversed(created):volume.delete(0)
        for secret in new_secrets:secret.undefine()
        raise
