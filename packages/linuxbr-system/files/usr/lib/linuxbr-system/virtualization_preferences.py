"""Per-user host history and VM defaults without credentials."""
import json
import os
from pathlib import Path
from store_sources import atomic_write


def path():return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'linuxbr/virtualization.json'


def load():
    target=path()
    try:
        if target.is_symlink() or target.stat().st_size>65536:return {}
        value=json.loads(target.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def save(value):
    from virtualization_backend import checked_uri
    hosts=value.get('hosts',[])
    if not isinstance(hosts,list) or len(hosts)>40:raise ValueError('Muitos hospedeiros salvos.')
    for uri in hosts:checked_uri(uri)
    checked_uri(value.get('last_uri','qemu:///system'))
    target=path();target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if target.is_symlink():raise ValueError('O arquivo de preferências não pode ser um link.')
    atomic_write(target,json.dumps(value,ensure_ascii=False,indent=2).encode(),0o600)


def defaults(value,uri):
    rows=value.get('defaults',{})
    item=rows.get(uri,{}) if isinstance(rows,dict) else {}
    if not isinstance(item,dict):return {}
    result={}
    for key,minimum,maximum in [('memory',256,262144),('cpus',1,256),('disk_gib',4,2048)]:
        if type(item.get(key)) is int and minimum<=item[key]<=maximum:result[key]=item[key]
    for key in ('pool','network','directory'):
        if isinstance(item.get(key),str) and len(item[key])<=4096 and '\x00' not in item[key]:result[key]=item[key]
    return result
