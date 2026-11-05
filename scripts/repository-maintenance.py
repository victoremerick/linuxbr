#!/usr/bin/env python3
"""Inspect local repository health and renew its leaf certificate in place."""
import argparse
import ctypes
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime, format_datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import stat
import shutil
import subprocess
import sys
import tempfile
import uuid

UTC=timezone.utc


def run(*argv, timeout=30):
    try:
        result=subprocess.run(list(map(str,argv)),stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout,check=False)
    except FileNotFoundError as exc:raise ValueError('Componente necessário não encontrado: '+str(argv[0])) from exc
    except subprocess.TimeoutExpired as exc:raise ValueError('O componente '+str(argv[0])+' não respondeu no prazo.') from exc
    if result.returncode:raise ValueError('O componente '+str(argv[0])+' recusou a verificação ou a operação solicitada.')
    return result.stdout


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def regular(path, private=False):
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Arquivo ausente, não regular ou com link: '+str(path))
    if private and path.stat().st_mode & 0o077:
        raise ValueError('A chave privada precisa ter permissão 0600: '+str(path))
    return path


def hostname(value):
    try:return str(ipaddress.ip_address(value))
    except ValueError:pass
    try:value=value.encode('idna').decode('ascii').lower()
    except UnicodeError as exc:raise ValueError('Nome de servidor inválido.') from exc
    if (len(value)>253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',value)
        or any(not part or len(part)>63 or part.startswith('-') or part.endswith('-') for part in value.split('.'))):
        raise ValueError('Informe um nome DNS ou endereço IP válido, sem porta ou protocolo.')
    return value


def _date(value):
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(value),UTC)


def certificate_info(path):
    regular(path)
    output=run('openssl','x509','-in',path,'-noout','-dates','-serial').decode('utf-8')
    fields=dict(line.split('=',1) for line in output.splitlines() if '=' in line)
    sans=run('openssl','x509','-in',path,'-noout','-ext','subjectAltName').decode('utf-8').strip()
    return {'not_before':_date(fields['notBefore']),'not_after':_date(fields['notAfter']),
            'serial':fields['serial'],'san':sans,'sha256':digest(path)}


def _identity(host):
    try:ipaddress.ip_address(host);return '-verify_ip'
    except ValueError:return '-verify_hostname'


def check_tls(directory, host=None, ignore_time=False):
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('O diretório TLS não pode ser um link.')
    cert=regular(directory/'server.crt');ca=regular(directory/'ca.crt');key=regular(directory/'server.key',True)
    args=['openssl','verify','-CAfile',ca,'-purpose','sslserver']
    if ignore_time:args.append('-no_check_time')
    if host:args += [_identity(host),hostname(host)]
    run(*args,cert)
    if run('openssl','x509','-in',cert,'-pubkey','-noout')!=run('openssl','pkey','-in',key,'-passin','pass:','-pubout'):
        raise ValueError('O certificado de servidor não corresponde à chave existente.')
    info=certificate_info(cert);ca_info=certificate_info(ca)
    return info,ca_info


def _release_date(fields, key):
    try:
        value=parsedate_to_datetime(fields[key])
        if value.tzinfo is None:raise ValueError()
        return value.astimezone(UTC)
    except (KeyError,TypeError,ValueError,OverflowError) as exc:raise ValueError('Data ausente ou inválida nos metadados: '+key) from exc


def _publication_file(base, relative):
    parts=Path(relative)
    if parts.is_absolute() or '..' in parts.parts or '\\' in relative or not relative:
        raise ValueError('Caminho inválido no índice assinado.')
    candidate=base
    for part in parts.parts:
        candidate=candidate/part
        if candidate.is_symlink():raise ValueError('Um índice assinado aponta para um link.')
    regular(candidate)
    if not candidate.resolve().is_relative_to(base.resolve()):raise ValueError('Um índice está fora da publicação.')
    return candidate


def _signature_fingerprints(status):
    if re.search(rb'\[GNUPG:\] (?:BADSIG|ERRSIG|EXPSIG|EXPKEYSIG|REVKEYSIG|KEYREVOKED|KEYEXPIRED|SIGEXPIRED|NO_PUBKEY)\b',status):
        raise ValueError('A assinatura ou a chave de assinatura é inválida, expirada, revogada ou indisponível.')
    fingerprints=set(re.findall(rb'\[GNUPG:\] VALIDSIG ([A-F0-9]+)',status))
    if not fingerprints:raise ValueError('A ferramenta não confirmou uma assinatura válida.')
    return fingerprints


def check_publication(publication, keyring=None, now=None):
    publication=Path(publication);now=now or datetime.now(UTC)
    if publication.is_symlink():raise ValueError('O diretório público não pode ser um link.')
    distribution=publication/'dists/trixie'
    if (publication/'dists').is_symlink() or distribution.is_symlink():raise ValueError('A estrutura pública contém um link no caminho dos metadados.')
    release=regular(distribution/'Release')
    if release.stat().st_size>4*1024*1024:raise ValueError('Os metadados Release excedem o limite de tamanho.')
    explicit=keyring is not None
    keyring=regular(Path(keyring) if explicit else publication/'linuxbr-archive-keyring.gpg').resolve()
    signatures=[];fingerprints=set()
    with tempfile.TemporaryDirectory(prefix='linuxbr-repository-check-') as temporary:
        home=Path(temporary);home.chmod(0o700)
        common=['gpgv','--homedir',home,'--keyring',keyring,'--status-fd','1']
        inline=distribution/'InRelease';detached=distribution/'Release.gpg'
        if inline.exists():
            regular(inline);verified=home/'verified-release'
            status=run(*common,'--output',verified,inline)
            if verified.read_bytes()!=release.read_bytes():raise ValueError('InRelease e Release contêm metadados diferentes.')
            signatures.append('InRelease')
            fingerprints.update(_signature_fingerprints(status))
        if detached.exists():
            regular(detached);status=run(*common,detached,release);signatures.append('Release.gpg')
            fingerprints.update(_signature_fingerprints(status))
        if not signatures or not fingerprints:raise ValueError('Não há assinatura verificável dos metadados.')
    text=release.read_text(encoding='utf-8');fields={};hashes=[];section=None
    for line in text.splitlines():
        if line.startswith((' ','\t')):
            if section=='SHA256':
                match=re.fullmatch(r'\s+([a-fA-F0-9]{64})\s+(\d+)\s+(.+)',line)
                if not match:raise ValueError('Entrada SHA256 inválida nos metadados.')
                hashes.append((match[1].lower(),int(match[2]),match[3]))
        elif ':' in line:
            section,value=line.split(':',1)
            if section in fields:raise ValueError('Campo duplicado nos metadados: '+section)
            fields[section]=value.strip()
    created=_release_date(fields,'Date');expires=_release_date(fields,'Valid-Until')
    if created>now+timedelta(minutes=5):raise ValueError('Os metadados têm uma data futura. Confira os relógios antes de publicar.')
    if expires<=created or expires<=now:raise ValueError('Os metadados expiraram ou têm intervalo de validade inválido. Prepare uma publicação nova e assinada.')
    if not hashes:raise ValueError('Os metadados não possuem índices SHA256.')
    seen=set()
    for expected,size,relative in hashes:
        if relative in seen:raise ValueError('Índice repetido nos metadados.')
        seen.add(relative);path=_publication_file(distribution,relative)
        if path.stat().st_size!=size or digest(path)!=expected:raise ValueError('Tamanho ou SHA256 divergente no índice: '+relative)
    return {'date':created.isoformat(),'valid_until':expires.isoformat(),'expires_at':expires,
            'indices_checked':len(hashes),'signatures':signatures,
            'fingerprints':sorted(value.decode('ascii') for value in fingerprints),
            'keyring':str(keyring),'independent_keyring':explicit}


def health(publication, tls_dir, keyring=None, host=None, warn_days=3, now=None):
    now=now or datetime.now(UTC);checks=[]
    def add(name,level,message,**details):checks.append({'check':name,'status':level,'message':message,**details})
    try:
        result=check_publication(publication,keyring,now);expires=result.pop('expires_at')
        near=expires-now<=timedelta(days=warn_days)
        add('publication','warning' if near else 'ok','Metadados assinados e índices conferidos.' if not near else 'Metadados próximos do vencimento; prepare uma nova publicação.',**result)
        if not result['independent_keyring']:
            add('trust-reference','warning','A assinatura corresponde ao keyring da própria publicação. Use --keyring de uma referência já confiável para conferir a identidade de forma independente.')
    except (OSError,ValueError,KeyError,UnicodeError) as exc:add('publication','error',str(exc))
    try:
        cert,ca=check_tls(tls_dir,hostname(host) if host else None,ignore_time=True)
        for name,info in [('server-certificate',cert),('certificate-authority',ca)]:
            if info['not_before']>now or info['not_after']<=now:
                add(name,'error','Certificado fora do intervalo de validade.',
                    not_before=info['not_before'].isoformat(),not_after=info['not_after'].isoformat(),sha256=info['sha256'])
            else:
                near=info['not_after']-now<=timedelta(days=warn_days)
                add(name,'warning' if near else 'ok','Certificado próximo do vencimento.' if near else 'Certificado dentro da validade.',
                    not_before=info['not_before'].isoformat(),not_after=info['not_after'].isoformat(),sha256=info['sha256'])
        add('tls-identity','ok','Cadeia TLS e correspondência entre certificado e chave conferidas.',
            hostname=host,hostname_verified=bool(host),san=cert['san'])
        if not host:add('tls-hostname','warning','Informe --hostname para conferir o nome usado pelos clientes.')
    except (OSError,ValueError,KeyError,UnicodeError) as exc:add('tls','error',str(exc))
    status='error' if any(check['status']=='error' for check in checks) else 'warning' if any(check['status']=='warning' for check in checks) else 'ok'
    return {'status':status,'checked_at':now.isoformat(),'checks':checks}


def renew_metadata(publication, keyring, fingerprint, warn_days=3, force=False, now=None):
    """Renew dates and signatures while preserving the reviewed package indexes."""
    publication=Path(publication).absolute();keyring=Path(keyring).absolute()
    if not re.fullmatch(r'[A-Fa-f0-9]{40,64}',fingerprint):raise ValueError('Informe a impressão digital completa da chave confiável.')
    if not 0<=warn_days<=13:raise ValueError('O limite de renovação deve ser de 0 a 13 dias.')
    fingerprint=fingerprint.upper();now=now or datetime.now(UTC)
    with renewal_lock(publication.parent):
        checked=check_publication(publication,keyring,now)
        if checked['fingerprints']!=[fingerprint]:raise ValueError('A publicação não corresponde à identidade de assinatura esperada.')
        if not force and checked['expires_at']-now>timedelta(days=warn_days):
            return {'status':'unchanged','valid_until':checked['valid_until'],'fingerprint':fingerprint}
        current=publication/'dists/trixie';original=(current/'Release').read_bytes()
        replacement=re.sub(r'^Date: .+$','Date: '+format_datetime(now,usegmt=True),original.decode('utf-8'),flags=re.M)
        replacement=re.sub(r'^Valid-Until: .+$','Valid-Until: '+format_datetime(now+timedelta(days=14),usegmt=True),replacement,flags=re.M)
        with tempfile.TemporaryDirectory(prefix='.metadata-renewal-',dir=publication.parent) as temporary:
            temporary=Path(temporary);staged=temporary/'publication';distribution=staged/'dists/trixie'
            shutil.copytree(current,distribution)
            shutil.copyfile(keyring,staged/'linuxbr-archive-keyring.gpg')
            (distribution/'Release').write_text(replacement,encoding='utf-8')
            for args in [('--clearsign','--output',distribution/'InRelease'),('--armor','--detach-sign','--output',distribution/'Release.gpg')]:
                run('gpg','--batch','--yes','--local-user',fingerprint,*args,distribution/'Release')
            verified=check_publication(staged,keyring,now)
            if verified['fingerprints']!=[fingerprint]:raise ValueError('A nova assinatura não corresponde à identidade esperada.')
            for path in distribution.rglob('*'):
                if path.is_file():
                    with path.open('rb') as stream:os.fsync(stream.fileno())
            if (current/'Release').read_bytes()!=original:raise ValueError('A publicação mudou durante a renovação.')
            # Exchange complete directories on the same filesystem without a publication gap.
            library=ctypes.CDLL(None,use_errno=True);exchange=getattr(library,'renameat2',None)
            if exchange is None:raise ValueError('Troca atômica de metadados indisponível neste servidor.')
            exchange.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
            exchange.restype=ctypes.c_int
            if exchange(-100,os.fsencode(current),-100,os.fsencode(distribution),2):
                code=ctypes.get_errno();raise OSError(code,os.strerror(code))
            try:
                final=check_publication(publication,keyring,now)
                if final['fingerprints']!=[fingerprint]:raise ValueError('Identidade alterada após a publicação.')
            except Exception:
                if exchange(-100,os.fsencode(current),-100,os.fsencode(distribution),2):
                    recovery=publication.parent/('.metadata-recovery-'+uuid.uuid4().hex)
                    os.rename(temporary,recovery)
                    raise RuntimeError('Reversão incompleta. Metadados anteriores preservados em '+str(recovery))
                raise
        return {'status':'renewed','fingerprint':fingerprint,'valid_until':verified['valid_until'],
                'package_indexes_preserved':True,'atomic':True}


@contextmanager
def renewal_lock(directory):
    lock=directory/'.certificate-renewal.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:raise ValueError('Há uma renovação em andamento ou uma trava anterior. Confira o processo antes de remover a trava.') from exc
    try:
        os.write(fd,str(os.getpid()).encode('ascii'));os.close(fd);yield
    finally:lock.unlink(missing_ok=True)


def renew_certificate(tls_dir, host, days=397, now=None):
    now=now or datetime.now(UTC);host=hostname(host);directory=Path(tls_dir)
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Escolha o diretório TLS existente, sem links.')
    if not 1<=days<=397:raise ValueError('A validade deve ser de 1 a 397 dias.')
    with renewal_lock(directory):
        cert,ca=check_tls(directory,host,ignore_time=True)
        ca_key=regular(directory/'ca.key',True)
        if ca['not_before']>now or ca['not_after']<=now+timedelta(days=days,seconds=60):
            raise ValueError('A CA não cobre a validade solicitada. Reduza --days ou planeje a renovação da autoridade e a confiança dos clientes separadamente.')
        run('openssl','verify','-CAfile',directory/'ca.crt',directory/'ca.crt')
        if run('openssl','x509','-in',directory/'ca.crt','-pubkey','-noout')!=run('openssl','pkey','-in',ca_key,'-passin','pass:','-pubout'):
            raise ValueError('A chave da CA não corresponde ao certificado da autoridade.')
        constraints=run('openssl','x509','-in',directory/'server.crt','-noout','-ext','basicConstraints')
        if b'CA:FALSE' not in constraints or not cert['san']:
            raise ValueError('O arquivo atual deve ser um certificado de servidor com SAN e CA:FALSE.')
        preserved={name:digest(directory/name) for name in ('ca.crt','ca.key','server.key')}
        original=regular(directory/'server.crt');original_bytes=original.read_bytes();original_mode=stat.S_IMODE(original.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix='.certificate-',dir=directory) as temporary:
            temporary=Path(temporary);request=temporary/'server.csr';renewed=temporary/'server.crt'
            run('openssl','x509','-x509toreq','-in',original,'-signkey',directory/'server.key',
                '-passin','pass:','-copy_extensions','copy','-out',request)
            run('openssl','x509','-req','-in',request,'-CA',directory/'ca.crt','-CAkey',ca_key,
                '-passin','pass:','-set_serial',str(int.from_bytes(os.urandom(20),'big')>>1 or 1),
                '-days',str(days),'-sha256','-copy_extensions','copy','-out',renewed)
            new=certificate_info(renewed)
            if cert['san']!=new['san']:raise ValueError('Os nomes SAN não foram preservados. O certificado anterior continua em uso.')
            run('openssl','verify','-CAfile',directory/'ca.crt','-purpose','sslserver',_identity(host),host,renewed)
            if run('openssl','x509','-in',renewed,'-pubkey','-noout')!=run('openssl','pkey','-in',directory/'server.key','-passin','pass:','-pubout'):
                raise ValueError('O novo certificado não corresponde à chave de servidor existente.')
            if any(digest(directory/name)!=expected for name,expected in preserved.items()) or original.read_bytes()!=original_bytes:
                raise ValueError('Um arquivo TLS mudou durante a operação. A substituição foi cancelada.')
            backup=directory/('server.crt.previous-'+now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.pem')
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,original_mode)
            with os.fdopen(fd,'wb') as stream:stream.write(original_bytes);stream.flush();os.fsync(stream.fileno())
            renewed.chmod(original_mode)
            with renewed.open('rb') as stream:os.fsync(stream.fileno())
            os.replace(renewed,original)
            directory_fd=os.open(directory,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        return {'status':'renewed','hostname':host,'certificate':str(original),'backup':str(backup),
                'old_sha256':cert['sha256'],'new_sha256':new['sha256'],'not_after':new['not_after'].isoformat(),
                'san':new['san'],'authority_preserved':True,'server_key_preserved':True,
                'service_reloaded':False,'message':'Certificado renovado. Recarregue o servidor pelo procedimento de operação e confira a conexão antes de remover o backup.'}


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0]=='--renew-certificate':argv[0]='renew-certificate'
    parser=argparse.ArgumentParser(description='Conferir publicação APT e renovar somente o certificado TLS de servidor.')
    commands=parser.add_subparsers(dest='command',required=True)
    check=commands.add_parser('health');check.add_argument('--publication',type=Path,required=True);check.add_argument('--tls-dir',type=Path,required=True)
    check.add_argument('--keyring',type=Path);check.add_argument('--hostname');check.add_argument('--warn-days',type=int,default=3)
    renew=commands.add_parser('renew-certificate');renew.add_argument('--tls-dir',type=Path,required=True);renew.add_argument('--hostname',required=True);renew.add_argument('--days',type=int,default=397)
    metadata=commands.add_parser('renew-metadata');metadata.add_argument('--publication',type=Path,required=True);metadata.add_argument('--keyring',type=Path,required=True)
    metadata.add_argument('--fingerprint',required=True);metadata.add_argument('--warn-days',type=int,default=3);metadata.add_argument('--force',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.command=='health':
            if not 0<=args.warn_days<=365:raise ValueError('O aviso de validade deve ser de 0 a 365 dias.')
            result=health(args.publication,args.tls_dir,args.keyring,args.hostname,args.warn_days)
            print(json.dumps(result,ensure_ascii=False,indent=2));return {'ok':0,'warning':1,'error':2}[result['status']]
        if args.command=='renew-metadata':
            print(json.dumps(renew_metadata(args.publication,args.keyring,args.fingerprint,args.warn_days,args.force),ensure_ascii=False,indent=2));return 0
        print(json.dumps(renew_certificate(args.tls_dir,args.hostname,args.days),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,UnicodeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False,indent=2));return 2


if __name__=='__main__':sys.exit(main())
