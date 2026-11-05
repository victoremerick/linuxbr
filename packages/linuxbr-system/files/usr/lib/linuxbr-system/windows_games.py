"""Read Steam's local manifests without changing Proton or game configuration."""
import os
from pathlib import Path
import re


def fields(path):
    if not path.is_file() or path.stat().st_size>1024*1024:return {}
    text=path.read_text(encoding='utf-8',errors='replace')
    return {key:value.replace(r'\"','"').replace('\\\\','\\')
        for key,value in re.findall(r'"([^"\\]+)"\s*"((?:\\.|[^"\\])*)"',text)}


def installed_games(home=None):
    home=Path(home or Path.home())
    roots=[home/'.local/share/Steam',home/'.steam/steam',
        home/'.var/app/com.valvesoftware.Steam/.local/share/Steam']
    libraries={}
    for root in roots:
        if not root.is_dir():continue
        libraries[str(root.resolve())]=root
        folder=root/'steamapps/libraryfolders.vdf'
        try:
            if folder.is_file() and folder.stat().st_size<=1024*1024:
                for value in re.findall(r'"path"\s*"((?:\\.|[^"\\])*)"',folder.read_text(encoding='utf-8',errors='replace')):
                    path=Path(value.replace('\\\\','\\'))
                    if path.is_absolute() and path.is_dir():libraries[str(path.resolve())]=path
        except OSError:continue
    result=[];seen=set()
    for root in libraries.values():
        for index,path in enumerate((root/'steamapps').glob('appmanifest_*.acf')):
            if index>=1000:break
            try:
                value=fields(path);identifier=value.get('appid','');name=value.get('name','')
                if not re.fullmatch(r'[0-9]{1,12}',identifier) or not name or (identifier,str(root)) in seen:continue
                if any(ord(character)<32 for character in name):continue
                seen.add((identifier,str(root)))
                result.append(dict(id=identifier,name=name,library=str(root),
                    prefix=str(root/'steamapps/compatdata'/identifier),status='Não testado nesta versão'))
            except (OSError,ValueError):continue
    return sorted(result,key=lambda item:item['name'].casefold())


def details_uri(identifier):
    if not isinstance(identifier,str) or not re.fullmatch(r'[0-9]{1,12}',identifier):
        raise ValueError('Identificador Steam inválido.')
    return 'steam://nav/games/details/'+identifier
