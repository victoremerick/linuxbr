"""User catalogs contain descriptions and URLs, never executable commands."""
import json
import os
from pathlib import Path
import re
import urllib.request
from store_sources import https_url,atomic_write,SLUG


def folder():return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'linuxbr/store/catalogs'


def checked(value,name):
    if not isinstance(value,dict) or not isinstance(value.get('apps'),list) or len(value['apps'])>1000:raise ValueError('O catálogo deve ter uma lista apps com até 1.000 itens.')
    rows=[];seen=set()
    for item in value['apps']:
        if not isinstance(item,dict) or item.get('kind') not in ('web','windows'):raise ValueError('Catálogos adicionais aceitam apenas webapps e links de programas Windows. Programas Linux usam fontes assinadas APT ou Flatpak.')
        identifier=item.get('id','')
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',identifier) or identifier in seen:raise ValueError('Identificador de aplicativo inválido ou repetido.')
        seen.add(identifier);row={}
        for key in ('name','description','category'):
            text=item.get(key,'')
            if not isinstance(text,str) or not text.strip() or len(text)>2000 or '\x00' in text:raise ValueError('Nome, descrição ou categoria inválidos.')
            row[key]=text.strip()
        row.update(id='extra:'+name+':'+identifier,kind=item['kind'],source=https_url(item['source']),catalog_source=name,note='Catálogo adicional: '+name+'. Compatibilidade e disponibilidade dependem do fornecedor.')
        if item['kind']=='web':row['url']=https_url(item['url'])
        rows.append(row)
    return rows


def sources():
    result=[]
    for path in sorted(folder().glob('*.json')):
        try:
            if path.is_symlink() or path.stat().st_size>2097152:continue
            value=json.loads(path.read_text());checked(value,path.stem)
            result.append(dict(kind='Catálogo',name=path.stem,url=value.get('source_url',''),scope='user',enabled=value.get('enabled',True),apps=len(value['apps'])))
        except (OSError,ValueError,KeyError,TypeError):continue
    return result


def entries():
    rows=[]
    for source in sources():
        if source['enabled']:rows.extend(checked(json.loads((folder()/(source['name']+'.json')).read_text()),source['name']))
    import signed_catalog
    return rows+signed_catalog.entries()


def add(name,url):
    if not SLUG.fullmatch(name):raise ValueError('Identificador do catálogo inválido.')
    https_url(url);destination=folder()/(name+'.json')
    if destination.exists():raise ValueError('Já existe um catálogo com esse nome.')
    request=urllib.request.Request(url,headers={'User-Agent':'LinuxBR-Store/0.8.5','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=20) as response:
        https_url(response.url);raw=response.read(1048577)
    if len(raw)>1048576:raise ValueError('Catálogo maior que 1 MiB.')
    value=json.loads(raw);checked(value,name);value['enabled']=True;value['source_url']=url
    folder().mkdir(parents=True,exist_ok=True,mode=0o700);atomic_write(destination,json.dumps(value,ensure_ascii=False).encode(),0o600)
    return len(value['apps'])


def change(name,remove=False):
    if not SLUG.fullmatch(name):raise ValueError('Identificador inválido.')
    path=folder()/(name+'.json')
    if path.is_symlink():raise ValueError('Catálogo inválido.')
    if remove:path.unlink()
    else:
        value=json.loads(path.read_text());value['enabled']=not value.get('enabled',True);atomic_write(path,json.dumps(value,ensure_ascii=False).encode(),0o600)
