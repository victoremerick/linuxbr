"""Append pinned public Secure Boot certificates without changing other variables."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import uuid
from store_sources import atomic_write

ASSETS=Path(__file__).resolve().parents[2]/'share/linuxbr/firmware'
TEMPLATE=Path('/var/lib/linuxbr/firmware/OVMF_VARS_4M.ms-2023.fd')
BASE=Path('/usr/share/OVMF/OVMF_VARS_4M.ms.fd')


def certificates():
    from cryptography import x509
    manifest=json.loads((ASSETS/'certificates.json').read_text());records=[]
    if manifest.get('commit')!='3d762aecbaecd12402efd21ba89c8c7bd40da4bd':raise ValueError('Origem dos certificados de firmware não reconhecida.')
    for row in manifest['certificates']:
        name=row['file']
        if Path(name).name!=name or row['variable'] not in ('db','KEK'):raise ValueError('Manifesto de certificados inválido.')
        data=(ASSETS/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Integridade divergente no certificado '+name+'.')
        certificate=x509.load_der_x509_certificate(data)
        if not certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:raise ValueError('O arquivo não é uma autoridade de certificação.')
        records.append((row['variable'],certificate))
    if len(records)!=4:raise ValueError('Conjunto incompleto de autoridades de certificação.')
    return manifest,records


def signatures(variable):
    return {(str(group.guid),str(item['guid']),item['data']) for group in variable.sigdb for item in group} if variable.sigdb else set()


def variables(path):
    from virt.firmware.varstore.edk2 import Edk2VarStore
    from virt.firmware.efi import efivar,ucs16
    try:store=Edk2VarStore(str(path))
    except SystemExit:raise ValueError('Formato de variáveis UEFI não suportado.') from None
    result=efivar.EfiVarList();offset=store.start
    while offset<store.end:
        magic,state=struct.unpack_from('<HB',store.filedata,offset)
        if magic!=0x55aa:break
        pk_index,name_size,data_size=struct.unpack_from('<III',store.filedata,offset+32)
        if name_size<2 or name_size%2 or offset+60+name_size+data_size>store.end:raise ValueError('Registro de variável UEFI inválido.')
        if state==0x3f:
            name=ucs16.from_ucs16(store.filedata[offset+60:offset+60+name_size]);guid=uuid.UUID(bytes_le=store.filedata[offset+44:offset+60]);canonical=str(name) in ('PK','KEK','db','dbx') and str(guid)==efivar.efivar_defaults[str(name)]['guid'];key=str(name) if canonical else str(name)+'\0'+str(guid)
            if key in result:raise ValueError('Há registros ativos duplicados da mesma variável UEFI. O conteúdo foi preservado para revisão.')
            attr,count=struct.unpack_from('<IQ',store.filedata,offset+4);value=store.filedata[offset+60+name_size:offset+60+name_size+data_size];item=efivar.EfiVar(name,guid=guid,attr=attr,data=value,count=count,pkidx=pk_index);item.parse_time(store.filedata,offset+16);result[key]=item
        offset=(offset+60+name_size+data_size+3)&~3
    return store,result


def enroll(data):
    from cryptography.hazmat.primitives import serialization
    if not isinstance(data,bytes) or not 4096<=len(data)<=16*1024**2:raise ValueError('Tamanho de variáveis UEFI inválido.')
    manifest,records=certificates()
    with tempfile.TemporaryDirectory(prefix='linuxbr-uefi-') as directory:
        root=Path(directory);source=root/'source.fd';source.write_bytes(data);source.chmod(0o600);store,before=variables(source)
        if not all(name in before for name in ('PK','KEK','db')):raise ValueError('O firmware não possui a cadeia de chaves esperada. O gerenciador não altera PK nem ativa Secure Boot implicitamente.')
        snapshots={name:(item.guid,item.attr,item.data,item.count,item.pkidx,item.time) for name,item in before.items()};old={name:signatures(before[name]) for name in ('db','KEK')}
        for index,(name,certificate) in enumerate(records):
            pem=root/(str(index)+'.pem');pem.write_bytes(certificate.public_bytes(serialization.Encoding.PEM));before.add_cert(name,manifest['owner_guid'],str(pem))
        try:output=store.bytes_varstore(before)
        except SystemExit:raise ValueError('Não há espaço suficiente nas variáveis UEFI para adicionar os certificados. O conteúdo original foi preservado.') from None
        target=root/'target.fd';target.write_bytes(output);target.chmod(0o600);_,after=variables(target)
        if set(after)!=set(snapshots):raise ValueError('A lista de variáveis foi alterada inesperadamente.')
        for name,values in snapshots.items():
            if name in ('db','KEK'):continue
            item=after[name]
            if (item.guid,item.attr,item.data,item.count,item.pkidx,item.time)!=values:raise ValueError('Uma variável que deveria ser preservada foi alterada: '+name)
        for name in ('db','KEK'):
            if not old[name]<=signatures(after[name]):raise ValueError('Uma assinatura existente foi removida durante a preparação.')
        for name,certificate in records:
            if certificate.public_bytes(serialization.Encoding.DER) not in after[name].data:raise ValueError('O certificado esperado não foi incluído.')
        return output


def prepare():
    if os.geteuid()!=0:raise PermissionError('Preparar o firmware do computador exige autorização administrativa.')
    source=BASE.read_bytes();manifest,_=certificates();identity=hashlib.sha256(source+(ASSETS/'certificates.json').read_bytes()).hexdigest();record=TEMPLATE.with_suffix('.json')
    TEMPLATE.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    if TEMPLATE.parent.is_symlink() or TEMPLATE.parent.stat().st_uid!=0 or TEMPLATE.parent.stat().st_mode&0o022:raise ValueError('Diretório de firmware com permissões inseguras.')
    if TEMPLATE.is_symlink() or record.is_symlink():raise ValueError('Os arquivos de firmware não podem ser links simbólicos.')
    try:previous=json.loads(record.read_text())
    except (OSError,ValueError):previous={}
    if previous.get('source')==identity and TEMPLATE.exists() and hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()==previous.get('sha256'):return dict(status='PASS',unchanged=True)
    output=enroll(source);atomic_write(TEMPLATE,output,0o644);value=dict(source=identity,sha256=hashlib.sha256(output).hexdigest(),certificates_commit=manifest['commit']);atomic_write(record,json.dumps(value,indent=2).encode(),0o644)
    return dict(status='PASS',template=str(TEMPLATE),sha256=value['sha256'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    if not args.prepare:parser.error('Informe --prepare para preparar os modelos de novas VMs.')
    print(json.dumps(prepare(),ensure_ascii=False))
