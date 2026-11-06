"""Versioned, signed web application catalogs and local update receipts."""
import base64
import fcntl
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from store_sources import atomic_write, https_url, SLUG

DEFAULTS=Path('/usr/share/linuxbr/catalog-sources')


def initialize_defaults():
    """Copy signed distribution sources once, preserving opt-outs and local keys."""
    if not DEFAULTS.is_dir():
        return
    destination=folder();destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock_path=destination/'.defaults.lock'
    descriptor=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for bundled in sorted(DEFAULTS.glob('*.json')):
            name=bundled.stem
            if not SLUG.fullmatch(name) or bundled.is_symlink() or bundled.stat().st_size>4194304:
                continue
            marker=destination/('.initialized-'+name)
            if marker.exists() or marker.is_symlink():
                continue
            if not path(name).exists():
                source=json.loads(bundled.read_text())
                actual=hashlib.sha256(key_bytes(source['public_key'])).hexdigest()
                if actual!=source['fingerprint']:
                    raise ValueError('Chave da fonte distribuída inválida.')
                https_url(source['catalog_url']);https_url(source['discovery_url'])
                data=verify(source['envelope'],source,True)
                source.update(revision=data['revision'],payload_sha256=data['payload_sha256'],enabled=True)
                write(name,source)
            atomic_write(marker,b'1\n',0o600)


def folder():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'linuxbr/store/signed-catalogs'


def path(name):
    if not isinstance(name, str) or not SLUG.fullmatch(name):
        raise ValueError('Nome da fonte inválido.')
    destination=folder()/(name+'.json')
    if destination.is_symlink():
        raise ValueError('Arquivo de fonte inválido.')
    return destination


def read(name):
    target=path(name)
    if target.stat().st_size>4194304:
        raise ValueError('Arquivo de fonte muito grande.')
    return json.loads(target.read_text())


def write(name, value):
    folder().mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(path(name),json.dumps(value,ensure_ascii=False).encode(),0o600)


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,url):
        https_url(url)
        return super().redirect_request(request,fp,code,msg,headers,url)


def fetch(url):
    https_url(url)
    request=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'LinuxBR-Store/0.9'})
    with urllib.request.build_opener(HTTPSRedirect()).open(request,timeout=20) as response:
        https_url(response.url)
        data=response.read(3145729)
    if len(data)>3145728:
        raise ValueError('Catálogo maior que o limite de 3 MiB.')
    return json.loads(data)


def key_bytes(value):
    try:
        raw=base64.b64decode(value,validate=True)
    except (ValueError,TypeError):
        raise ValueError('Chave pública inválida.') from None
    if len(raw)!=32:
        raise ValueError('Chave pública inválida.')
    return raw


def inspect(url):
    data=fetch(url)
    if data.get('schema')!=1 or not SLUG.fullmatch(str(data.get('source_id',''))):
        raise ValueError('Protocolo de catálogo não reconhecido.')
    public=key_bytes(data.get('public_key'))
    fingerprint=hashlib.sha256(public).hexdigest()
    if fingerprint!=data.get('fingerprint'):
        raise ValueError('A impressão digital não corresponde à chave.')
    https_url(data.get('catalog_url',''))
    return dict(source_id=data['source_id'],name=str(data.get('name',''))[:120],public_key=data['public_key'],
                fingerprint=fingerprint,catalog_url=data['catalog_url'],discovery_url=url)


def verify(envelope, source, allow_expired=False):
    try:
        public=key_bytes(source['public_key'])
        if envelope['algorithm']!='ed25519' or envelope['key_id']!=hashlib.sha256(public).hexdigest():
            raise ValueError('A chave do catálogo mudou. Revise a confiança na fonte.')
        payload=base64.b64decode(envelope['payload'],validate=True)
        signature=base64.b64decode(envelope['signature'],validate=True)
        if len(payload)>2097152:
            raise ValueError('Catálogo muito grande.')
        Ed25519PublicKey.from_public_bytes(public).verify(signature,payload)
        data=json.loads(payload)
        if data['schema']!=1 or data['source_id']!=source['source_id'] or type(data['revision']) is not int or data['revision']<1:
            raise ValueError('Identidade ou revisão do catálogo inválida.')
        issued=datetime.fromisoformat(data['issued_at'].replace('Z','+00:00'))
        expires=datetime.fromisoformat(data['expires_at'].replace('Z','+00:00'))
        now=datetime.now(timezone.utc)
        if issued.tzinfo is None or expires.tzinfo is None or issued>now+timedelta(minutes=5) or expires<=issued or expires-issued>timedelta(days=14):
            raise ValueError('Período de validade inválido.')
        if expires<=now and not allow_expired:
            raise ValueError('Catálogo expirado. Atualize a fonte antes de aplicar mudanças.')
        revision=source.get('revision',0)
        digest=hashlib.sha256(payload).hexdigest()
        if data['revision']<revision or data['revision']==revision and source.get('payload_sha256',digest)!=digest:
            raise ValueError('Uma revisão antiga ou inconsistente foi recusada.')
        if not isinstance(data['apps'],list) or len(data['apps'])>1000:
            raise ValueError('Lista de aplicativos inválida.')
        from webapps_backend import clean_url
        from catalog_sources import checked
        checked({'apps':data['apps']},'validation')
        for app in data['apps']:
            clean_url(app['url']);https_url(app['favicon'])
            if type(app['revision']) is not int or app['revision']<1 or app['status'] not in ('published','disabled'):
                raise ValueError('Revisão de aplicativo inválida.')
        data['expired']=expires<=now;data['payload_sha256']=digest
        return data
    except InvalidSignature:
        raise ValueError('Assinatura do catálogo inválida.') from None
    except (KeyError,TypeError,AttributeError):
        raise ValueError('Formato do catálogo inválido.') from None


def add(name, descriptor, fingerprint):
    if path(name).exists():
        raise ValueError('Já existe uma fonte com esse nome.')
    if descriptor['fingerprint']!=fingerprint:
        raise ValueError('Confiança na chave não confirmada.')
    source=dict(descriptor,enabled=True,revision=0)
    envelope=fetch(source['catalog_url']);data=verify(envelope,source)
    source.update(envelope=envelope,revision=data['revision'],payload_sha256=data['payload_sha256'])
    write(name,source)
    return len(data['apps'])


def refresh(name):
    source=read(name)
    if not source.get('enabled',True):
        return 0
    envelope=fetch(source['catalog_url']);data=verify(envelope,source)
    source.update(envelope=envelope,revision=data['revision'],payload_sha256=data['payload_sha256'])
    write(name,source)
    return len(data['apps'])


def rotate(name, descriptor, old_fingerprint, new_fingerprint):
    """Replace a pinned key only after explicit review; retain the revision floor."""
    source=read(name)
    if source['fingerprint']!=old_fingerprint:
        raise ValueError('A fonte mudou durante a revisão. Abra os detalhes novamente.')
    if descriptor['source_id']!=source['source_id'] or descriptor['discovery_url']!=source['discovery_url']:
        raise ValueError('A identidade ou o endereço da fonte mudou. Cadastre uma fonte separada.')
    actual=hashlib.sha256(key_bytes(descriptor['public_key'])).hexdigest()
    if actual!=new_fingerprint or actual!=descriptor['fingerprint']:
        raise ValueError('Confiança na nova chave não confirmada.')
    updated=dict(source,**descriptor)
    envelope=fetch(updated['catalog_url']);data=verify(envelope,updated)
    if read(name)!=source:
        raise ValueError('A fonte mudou durante a revisão. Tente novamente.')
    updated.update(envelope=envelope,revision=data['revision'],payload_sha256=data['payload_sha256'])
    write(name,updated)
    return len(data['apps'])


def sources():
    initialize_defaults()
    rows=[]
    for file in sorted(folder().glob('*.json')):
        try:
            source=read(file.stem);data=verify(source['envelope'],source,True)
            rows.append(dict(kind='Catálogo assinado',name=file.stem,url=source['discovery_url'],scope='user',
                             enabled=source.get('enabled',True),expired=data['expired'],fingerprint=source['fingerprint'],revision=data['revision']))
        except (OSError,ValueError,KeyError):
            continue
    return rows


def entries():
    result=[]
    from catalog_sources import checked
    for source in sources():
        if not source['enabled']:
            continue
        record=read(source['name']);data=verify(record['envelope'],record,True)
        active=[app for app in data['apps'] if app['status']=='published']
        rows=checked({'apps':active},source['name'])
        for row,app in zip(rows,active):
            row.update(id='signed:'+source['name']+':'+app['id'],signed_source=source['name'],signed_source_id=data['source_id'],signed_app=app['id'],
                       revision=app['revision'],favicon=app['favicon'],screenshots=app.get('screenshots',[]),
                       note=('Cópia local expirada; atualize a fonte. ' if data['expired'] else '')+'Fonte assinada: '+source['name']+'. Revisão '+str(app['revision']))
        result.extend(rows)
    return result


def change(name,remove=False):
    if remove:
        path(name).unlink()
    else:
        source=read(name);source['enabled']=not source.get('enabled',True);write(name,source)


def application(name, identifier):
    source=read(name)
    if not source.get('enabled',True):
        raise ValueError('Esta fonte está desabilitada.')
    data=verify(source['envelope'],source)
    app=next((row for row in data['apps'] if row['id']==identifier),None)
    if app is None:
        raise ValueError('O aplicativo não consta nesta revisão do catálogo.')
    return app


def track(profile, offer):
    name=offer.get('signed_source');identifier=offer.get('signed_app')
    if not name or not identifier:
        return
    import webapps_backend as web
    app=application(name,identifier);record=web.read_record(profile)
    if web.clean_url(app['url'])!=record['url'] or app['status']!='published':
        raise ValueError('A origem do aplicativo não corresponde ao perfil instalado.')
    record['catalog_subscription']=dict(source=name,app=identifier,revision=app['revision'])
    web.save_record(profile,record)


def updates():
    import webapps_backend as web
    rows=[]
    for record in web.installed():
        subscription=record.get('catalog_subscription')
        if not subscription:
            continue
        try:
            app=application(subscription['source'],subscription['app'])
            if app['revision']<=subscription['revision']:
                continue
            rows.append(dict(profile=record['id'],name=web.display_name(record),source=subscription['source'],
                app=subscription['app'],revision=app['revision'],changelog=app.get('changelog',''),
                url=app['url'],upstream_version=app.get('upstream_version'),upstream_release_url=app.get('upstream_release_url'),
                changed_url=web.clean_url(app['url'])!=record['url'],disabled=app['status']=='disabled'))
        except (OSError,ValueError,KeyError):
            continue
    return rows


def apply_update(profile, revision, acknowledge=False):
    import webapps_backend as web
    record=web.read_record(profile);subscription=record['catalog_subscription']
    app=application(subscription['source'],subscription['app'])
    if app['revision']!=revision:
        raise ValueError('A revisão mudou. Consulte novamente antes de aplicar.')
    if not acknowledge:
        if app['status']!='published' or web.clean_url(app['url'])!=record['url']:
            raise ValueError('Mudança de endereço ou desativação exige revisão. Os perfis existentes serão preservados.')
        record['name']=web.clean_name(app['name'])
    subscription['revision']=revision
    web.save_record(profile,record)
    return 'Revisão registrada. As sessões, cookies e preferências foram preservados.'


def refresh_all(notify=False):
    errors=[]
    for source in sources():
        if not source['enabled']:continue
        try:refresh(source['name'])
        except Exception as error:errors.append(source['name']+': '+str(error))
    pending=updates()
    if notify and pending:
        import subprocess
        receipt=folder()/'.notifications'
        try:previous=json.loads(receipt.read_text())
        except (OSError,ValueError):previous={}
        current={row['profile']:str(row['source'])+':'+str(row['revision']) for row in pending}
        if any(previous.get(key)!=value for key,value in current.items()):
            result=subprocess.run(['/usr/bin/notify-send','--app-name=Loja Linux BR','--icon=internet-web-browser',
                                   'Revisões de aplicativos web',str(len(pending))+' revisões disponíveis. Abra a Loja para conferir.'],capture_output=True,timeout=5)
            if result.returncode==0:atomic_write(receipt,json.dumps(current).encode(),0o600)
    return dict(pending=len(pending),errors=errors)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');parser.add_argument('--notify',action='store_true');args=parser.parse_args()
    if args.refresh:print(json.dumps(refresh_all(args.notify),ensure_ascii=False))
