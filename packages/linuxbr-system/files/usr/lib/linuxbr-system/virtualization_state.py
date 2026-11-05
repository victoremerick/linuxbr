"""Offline firmware and TPM state stored through authenticated libvirt streams."""
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

POOL='linuxbr-vm-state'


def element(parent,tag,text=None,**attrs):
    value=ET.SubElement(parent,tag,{key:str(value) for key,value in attrs.items()})
    if text is not None:value.text=str(text)
    return value


class State:
    def __init__(self,manager):self.manager=manager;self.connection=manager.connection

    @contextmanager
    def file_volume(self,path):
        import libvirt
        owned=None
        try:
            try:volume=self.connection.storageVolLookupByPath(path)
            except libvirt.libvirtError as error:
                if error.get_error_code() not in (libvirt.VIR_ERR_NO_STORAGE_VOL,libvirt.VIR_ERR_NO_STORAGE_POOL):raise
                parent=str(Path(path).parent);pool=None
                for candidate in self.connection.listAllStoragePools(0):
                    if candidate.isActive() and ET.fromstring(candidate.XMLDesc(0)).findtext('target/path')==parent:pool=candidate;break
                if pool is None:
                    root=ET.Element('pool',type='dir');element(root,'name','linuxbr-transfer-'+uuid.uuid4().hex);element(element(root,'target'),'path',parent)
                    pool=self.connection.storagePoolDefineXML(ET.tostring(root,encoding='unicode'),0);owned=pool;pool.create(0)
                pool.refresh(0);volume=pool.storageVolLookupByName(Path(path).name)
            yield volume
        finally:
            if owned is not None:
                if owned.isActive():owned.destroy()
                owned.undefine()

    def read(self,volume,limit=64*1024**2):
        output=io.BytesIO();stream=self.connection.newStream(0)
        def receive(_stream,data,_opaque):
            if output.tell()+len(data)>limit:raise ValueError('O arquivo de estado excede o limite permitido.')
            return output.write(data)
        try:volume.download(stream,0,0,0);stream.recvAll(receive,None);stream.finish()
        except Exception:
            stream.abort();raise
        return output.getvalue()

    def write(self,volume,data):
        source=io.BytesIO(data);stream=self.connection.newStream(0)
        try:volume.upload(stream,0,len(data),0);stream.sendAll(lambda _stream,count,_opaque:source.read(count),None);stream.finish()
        except Exception:
            stream.abort();raise

    def capture(self,identifier,bootstrap=True):
        domain=self.manager.domain(identifier)
        if domain.isActive():raise ValueError('Desligue a VM para copiar seu estado persistente.')
        if domain.hasManagedSaveImage(0):raise ValueError('Retome a VM e desligue o convidado antes de copiar seu estado persistente.')
        try:return self.capture_files(identifier)
        except Exception as error:
            import libvirt
            missing=isinstance(error,libvirt.libvirtError) and (error.get_error_code() in (libvirt.VIR_ERR_NO_STORAGE_VOL,libvirt.VIR_ERR_NO_STORAGE_POOL) or 'No such file or directory' in str(error))
            if not bootstrap or not missing:raise
            root=ET.fromstring(self.manager.xml(identifier))
            if any(root.findall('devices/'+tag) for tag in ('hostdev','filesystem','shmem')) or any(node.tag.startswith('{') for node in root if node.tag!='metadata'):raise ValueError('Inicialize e desligue esta VM manualmente antes de copiar o estado de seu hardware personalizado.') from error
            # Provision firmware and TPM without executing guest instructions.
            domain.createWithFlags(libvirt.VIR_DOMAIN_START_PAUSED)
            domain.destroy()
            return self.capture(identifier,False)

    def capture_files(self,identifier):
        root=ET.fromstring(self.manager.xml(identifier));files=[];secrets=[];nvram=root.find('os/nvram')
        if nvram is not None and nvram.text:
            with self.file_volume(nvram.text) as volume:data=self.read(volume)
            files.append(dict(role='nvram',path=nvram.text,data=data))
        for index,tpm in enumerate(root.findall('devices/tpm')):
            backend=tpm.find('backend')
            if backend is None or backend.get('type')!='emulator':raise ValueError('O estado deste tipo de TPM não pode ser copiado pela interface.')
            source=backend.find('source')
            if source is not None and source.get('path'):directory=Path(source.get('path'))
            elif self.manager.uri=='qemu:///session':
                home=Path.home();candidates=[home/'.config/libvirt/qemu/swtpm'/identifier/'tpm2',home/'.local/share/libvirt/swtpm'/identifier/'tpm2',home/'.local/share/libvirt/qemu/swtpm'/identifier/'tpm2',home/'.cache/libvirt/qemu/swtpm'/identifier/'tpm2'];directory=next((p for p in candidates if (p/'tpm2-00.permall').is_file()),None)
                if directory is None:raise ValueError('O estado do TPM pessoal não foi localizado. Inicialize e desligue a VM antes de criar uma cópia de estado.')
            else:directory=Path('/var/lib/libvirt/swtpm')/identifier/'tpm2'
            path=directory/'tpm2-00.permall'
            with self.file_volume(str(path)) as volume:data=self.read(volume)
            files.append(dict(role='tpm',index=index,path=str(path),data=data))
            encryption=backend.find('encryption')
            if encryption is not None:
                secret=self.connection.secretLookupByUUIDString(encryption.get('secret'));secrets.append(dict(id=secret.UUIDString(),xml=secret.XMLDesc(0),data=bytes(secret.value(0))))
        return dict(files=files,secrets=secrets)

    def pool(self):
        import libvirt
        path=str(Path.home()/'.local/share/libvirt/linuxbr-vm-state') if self.manager.uri=='qemu:///session' else '/var/lib/libvirt/images/linuxbr-vm-state'
        try:pool=self.connection.storagePoolLookupByName(POOL)
        except libvirt.libvirtError as error:
            if error.get_error_code()!=libvirt.VIR_ERR_NO_STORAGE_POOL:raise
            self.manager.create_pool(POOL,path,internal=True);pool=self.connection.storagePoolLookupByName(POOL)
        if ET.fromstring(pool.XMLDesc(0)).findtext('target/path')!=path:raise ValueError('O nome reservado para estado de VMs está associado a outro diretório. Preserve esse local e revise a configuração.')
        if not pool.isActive():pool.create(0)
        return pool

    def store(self,pool,name,data):
        root=ET.Element('volume');element(root,'name',name);element(root,'capacity',len(data),unit='bytes');target=element(root,'target');element(target,'format',type='raw')
        permissions=element(target,'permissions');element(permissions,'mode','0600')
        if self.manager.uri!='qemu:///session':element(permissions,'owner','0');element(permissions,'group','0')
        volume=pool.createXML(ET.tostring(root,encoding='unicode'),0)
        try:self.write(volume,data)
        except Exception:volume.delete(0);raise
        return volume

    def key(self,identifier,name):return hashlib.sha256((identifier+'\x00'+name).encode()).hexdigest()

    def save(self,identifier,name):
        captured=self.capture(identifier);pool=self.pool();key=self.key(identifier,name);manifest=dict(version=1,domain=identifier,snapshot=name,files=[],secrets=[]);created=[]
        try:
            for group in ('files','secrets'):
                for index,record in enumerate(captured[group]):
                    data=record['data'];volume_name=key+'-'+group+'-'+str(index)+'-'+uuid.uuid4().hex+'.raw';volume=self.store(pool,volume_name,data);created.append(volume)
                    manifest[group].append(dict({key:value for key,value in record.items() if key!='data'},volume=volume_name,sha256=hashlib.sha256(data).hexdigest(),size=len(data)))
            volume=self.store(pool,key+'.json',json.dumps(manifest,ensure_ascii=False).encode());created.append(volume)
        except Exception:
            for volume in reversed(created):volume.delete(0)
            raise
        return key

    def load(self,identifier,name):
        pool=self.pool();manifest=json.loads(self.read(pool.storageVolLookupByName(self.key(identifier,name)+'.json'),1048576))
        if manifest.get('version')!=1 or manifest.get('domain')!=identifier or manifest.get('snapshot')!=name:raise ValueError('O estado não corresponde a este checkpoint.')
        result=dict(files=[],secrets=[])
        for group in ('files','secrets'):
            for record in manifest.get(group,[]):
                if not record.get('volume','').startswith(self.key(identifier,name)+'-') or '/' in record['volume']:raise ValueError('Volume de estado inválido.')
                data=self.read(pool.storageVolLookupByName(record['volume']))
                if len(data)!=record['size'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('A integridade da cópia de estado não confere.')
                result[group].append(dict(record,data=data))
        return result

    def restore(self,identifier,state):
        domain=self.manager.domain(identifier)
        if domain.isActive():raise ValueError('A restauração do estado exige a VM desligada.')
        current=ET.fromstring(self.manager.xml(identifier));nvram=current.findtext('os/nvram');tpms=current.findall('devices/tpm')
        for record in state.get('files',[]):
            if record['role']=='nvram':
                if nvram!=record['path']:raise ValueError('O destino de firmware mudou. A cópia foi preservada para revisão.')
            elif record['role']=='tpm':
                if not 0<=record.get('index',-1)<len(tpms):raise ValueError('O TPM da cópia não corresponde ao dispositivo atual.')
                expected=Path('/var/lib/libvirt/swtpm')/identifier/'tpm2/tpm2-00.permall'
                if self.manager.uri!='qemu:///session' and Path(record['path'])!=expected:
                    backend=tpms[record['index']].find('backend/source')
                    if backend is None or Path(record['path']).parent!=Path(backend.get('path','')):raise ValueError('Destino de TPM inesperado.')
            else:raise ValueError('Tipo de estado desconhecido.')
        for record in state.get('secrets',[]):
            if not any(node.get('secret')==record['id'] for node in current.findall('devices/tpm/backend/encryption')):raise ValueError('O segredo de TPM não corresponde à VM atual.')
            secret=self.connection.secretLookupByUUIDString(record['id'])
            if bytes(secret.value(0))!=record['data']:
                for other in self.connection.listAllDomains(0):
                    if other.UUIDString()!=identifier and any(node.get('secret')==record['id'] for node in ET.fromstring(other.XMLDesc(2)).findall('devices/tpm/backend/encryption')):raise ValueError('O segredo de TPM está compartilhado com outra VM e foi alterado. A restauração exige revisão administrativa.')
        for record in state.get('secrets',[]):self.connection.secretLookupByUUIDString(record['id']).setValue(record['data'],0)
        for record in state.get('files',[]):
            with self.file_volume(record['path']) as volume:self.write(volume,record['data'])

    def remove(self,identifier,name):
        pool=self.pool();key=self.key(identifier,name);volume=pool.storageVolLookupByName(key+'.json');manifest=json.loads(self.read(volume,1048576))
        if manifest.get('domain')!=identifier or manifest.get('snapshot')!=name:raise ValueError('Estado de checkpoint inválido.')
        for group in ('files','secrets'):
            for record in manifest.get(group,[]):
                if not record.get('volume','').startswith(key+'-') or '/' in record['volume']:raise ValueError('Volume de estado inválido.')
                pool.storageVolLookupByName(record['volume']).delete(0)
        volume.delete(0)
