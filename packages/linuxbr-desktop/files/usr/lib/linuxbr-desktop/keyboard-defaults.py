#!/usr/bin/python3
"""Initialize Plasma from the installed keyboard choice without replacing user settings."""
import os
from pathlib import Path
import re
import shlex
import subprocess


def read_keyboard(path):
    values={}
    for line in path.read_text().splitlines():
        key,separator,value=line.partition('=')
        if not separator or key.strip() not in ('XKBMODEL','XKBLAYOUT','XKBVARIANT','XKBOPTIONS'):
            continue
        tokens=shlex.split(value,comments=True)
        value=tokens[0] if tokens else ''
        if len(tokens)>1 or not re.fullmatch(r'[A-Za-z0-9_,:+-]{0,200}',value):
            raise ValueError('Configuração de teclado inválida: '+key.strip())
        values[key.strip()]=value
    if not values.get('XKBLAYOUT'):
        raise ValueError('Layout de teclado do sistema não configurado.')
    return values


def apply_defaults(source,target):
    if target.exists():
        return False
    values=read_keyboard(source)
    text='[Layout]\nUse=true\n'
    for key,value in (('Model',values.get('XKBMODEL','')),('LayoutList',values['XKBLAYOUT']),
                      ('VariantList',values.get('XKBVARIANT','')),('Options',values.get('XKBOPTIONS',''))):
        text+=key+'='+value+'\n'
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        with target.open('x',encoding='utf-8') as stream:
            stream.write(text)
    except FileExistsError:
        return False
    return True


if __name__=='__main__':
    if os.geteuid()==0:
        raise SystemExit('Execute na sessão do usuário, sem sudo.')
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'kxkbrc'
    if apply_defaults(Path('/etc/default/keyboard'),config):
        subprocess.run(['dbus-send','--session','--type=signal','/Layouts','org.kde.keyboard.reloadConfig'],check=True)
