"""Per-user Flatpak overrides and camera portal decisions."""
import argparse
import json
import os
import re
import subprocess
import sys

APP=re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}')
OPTIONS={'network':('--share=network','--unshare=network'),'audio':('--socket=pulseaudio','--nosocket=pulseaudio'),'home':('--filesystem=home','--nofilesystem=home'),'documents':('--filesystem=xdg-documents','--nofilesystem=xdg-documents'),'downloads':('--filesystem=xdg-download','--nofilesystem=xdg-download'),'devices':('--device=all','--nodevice=all')}


def applications():
    rows=[]
    for scope in ('user','system'):
        result=subprocess.run(['/usr/bin/flatpak','--'+scope,'list','--app','--columns=application,name'],capture_output=True,text=True,timeout=15)
        for line in result.stdout.splitlines() if result.returncode==0 else []:
            fields=line.split('\t')
            if len(fields)==2 and APP.fullmatch(fields[0]):rows.append(dict(id=fields[0],name=fields[1],scope=scope))
    return rows


def details(app,scope):
    if not APP.fullmatch(app) or scope not in ('user','system'):raise ValueError('Aplicativo inválido.')
    result=subprocess.run(['/usr/bin/flatpak','--'+scope,'info','--show-permissions',app],capture_output=True,text=True,timeout=10)
    if result.returncode:raise ValueError(result.stderr.strip() or 'Permissões não disponíveis.')
    return result.stdout


def commands(app,changes):
    if not APP.fullmatch(app) or not isinstance(changes,dict):raise ValueError('Pedido inválido.')
    options=[];result=[]
    for key,value in changes.items():
        if not isinstance(value,bool):raise ValueError('Permissão inválida.')
        if key=='camera':result.append(['/usr/bin/flatpak','permission-set','devices','camera',app,'yes' if value else 'no'])
        elif key in OPTIONS:options.append(OPTIONS[key][0 if value else 1])
        else:raise ValueError('Permissão desconhecida.')
    if options:result.insert(0,['/usr/bin/flatpak','override','--user',*options,app])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply or os.geteuid()==0:raise SystemExit('Abra as permissões na conta normal do usuário.')
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise ValueError('Pedido muito grande.')
        request=json.loads(raw)
        for command in commands(request['app'],request['changes']):
            result=subprocess.run(command,capture_output=True,text=True,timeout=30)
            print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
            if result.returncode:raise ValueError('A alteração não foi concluída. As etapas anteriores podem ter sido aplicadas; confira as permissões atuais.')
        print('Permissões atualizadas para sua conta. Encerre e abra novamente o aplicativo para aplicar as restrições de ambiente.')
    except Exception as error:print(str(error),file=sys.stderr);raise SystemExit(1)
