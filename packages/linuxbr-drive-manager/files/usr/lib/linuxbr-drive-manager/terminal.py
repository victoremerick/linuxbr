#!/usr/bin/python3
"""Interactive shell adapter to the existing session drive service; no second aliases DB."""
import json
import fcntl
import os
import posixpath
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, unquote


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))/'linuxbr/terminal.json'


def mode():
    try:
        value=json.loads(config_path().read_text()).get('mode')
        return value if value in ('linux','letras') else 'letras'
    except (OSError, ValueError, AttributeError): return 'letras'


def atomic_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.terminal-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream,ensure_ascii=False)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def set_mode(value):
    if value not in ('linux','letras'): raise ValueError('Use terminal-modo letras ou terminal-modo linux.')
    atomic_json(config_path(),{'mode':value})


def service_state():
    import dbus
    obj=dbus.SessionBus().get_object('org.linuxbr.DriveManager1','/org/linuxbr/DriveManager1',introspect=False)
    return json.loads(dbus.Interface(obj,'org.linuxbr.DriveManager1').GetState(timeout=0.5))


def fuse_path(url):
    import dbus
    obj=dbus.SessionBus().get_object('org.kde.KIOFuse','/org/kde/KIOFuse')
    path=str(dbus.Interface(obj,'org.kde.KIOFuse.VFS').mountUrl(url,timeout=150))
    if not os.path.isabs(path): raise ValueError('KIO FUSE não retornou um caminho local válido.')
    return path


def mount_cache():
    runtime=os.environ.get('XDG_RUNTIME_DIR')
    # Optional display-only cache. Never fall back to a shared /tmp pathname.
    if not runtime: return None
    base=Path(runtime)
    if base.stat().st_uid!=os.getuid(): return None
    return base/'linuxbr-terminal-mounts.json'


def remember(url,path):
    try:
        cache=mount_cache()
        if cache is None: return
        fd=os.open(str(cache)+'.lock',os.O_CREAT|os.O_RDWR,0o600)
        with os.fdopen(fd,'w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            try: data=json.loads(cache.read_text())
            except (OSError,ValueError): data={}
            if not isinstance(data,dict): data={}
            data[url]=path
            atomic_json(cache,data)
    except OSError: pass


def resolve(text, resolver=None, fuse=fuse_path):
    match=re.fullmatch(r'([C-Zc-z]):(?:[/\\](.*))?',text)
    if not match: raise ValueError('Use C:, D: ou cd "D:/Minha pasta" (letras C a Z).')
    letter=match[1].upper()
    if letter=='C': url='file:///'
    else:
        if resolver is None:
            from client import interface
            resolver=lambda value: str(interface().Resolve(value,timeout=150))
        url=resolver(letter)
    parts=urlsplit(url)
    if parts.scheme=='file' and parts.netloc in ('','localhost'): root=unquote(parts.path)
    elif parts.scheme=='smb':
        root=fuse(url); remember(url,root)
    else: raise ValueError('A unidade não possui um caminho compatível com o terminal.')
    suffix=posixpath.normpath('/'+(match[2] or '').replace('\\','/')).lstrip('/')
    target=os.path.join(root,suffix)
    if not os.path.isabs(target) or any(ord(c)<32 or ord(c)==127 for c in target):
        raise ValueError('Caminho inválido para navegação por letra.')
    return target


def display(path, state=None):
    if state is None:
        try: state=service_state()
        except Exception: state={}
    mappings=[('/', 'C')]
    letters=state.get('data',{}).get('letters',{})
    for row in state.get('rows',[]):
        letter=letters.get(row.get('key'))
        if letter and not row.get('protected'):
            mappings.extend((mount,letter) for mount in row.get('mounts',[]) if mount.startswith('/'))
    try:
        cache=mount_cache()
        remote=json.loads(cache.read_text()) if cache else {}
        for key,letter in letters.items():
            mount=remote.get(key[4:]) if key.startswith('smb:') else None
            if mount and os.path.isdir(mount): mappings.append((mount,letter))
    except (OSError,ValueError,AttributeError): pass
    for root,letter in sorted(mappings,key=lambda x:len(x[0]),reverse=True):
        base=root.rstrip('/')
        if path==root or path.startswith(base+'/'):
            result=letter+':/'+path[len(base):].lstrip('/')
            return ''.join(c if ord(c)>=32 and ord(c)!=127 else '?' for c in result)
    return path


def main(argv):
    try:
        if argv==['mode']: print(mode())
        elif len(argv)==2 and argv[0]=='mode': set_mode(argv[1])
        elif len(argv)==2 and argv[0]=='resolve': print(resolve(argv[1]))
        elif len(argv)==2 and argv[0]=='prompt':
            print('letras'); print(display(argv[1]))
        elif argv==['list']:
            state=service_state()
            print('Unidade  Nome')
            for place in sorted(state.get('places',[]),key=lambda p:p['url']):
                name=place.get('card',{}).get('title',place.get('name',''))
                print(place['url'].rsplit('/',1)[-1]+':       '+''.join(c if ord(c)>=32 and ord(c)!=127 else '?' for c in name))
        else: raise ValueError('Comandos: unidades; terminal-modo letras|linux; cd D:/pasta; D:')
        return 0
    except Exception as error:
        print('Linux BR: '+str(error),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main(sys.argv[1:]))
