#!/usr/bin/python3
"""Translate a documented subset of Windows terminal commands without a shell."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from terminal import resolve


def path(value):
    if len(value)>1 and value[1]==':':
        return resolve(value)
    return value.replace('\\','/')


def command(name, args):
    options=[]; operands=[]
    supported={'dir':('/s','/b','/a'), 'copy':('/y','/-y'), 'move':('/y','/-y'),
               'del':('/p',), 'rd':(), 'md':(), 'type':(), 'explorer':()}
    for arg in args:
        if arg.lower() in supported.get(name,()):options.append(arg.lower())
        elif arg.startswith('/') and not os.path.exists(arg) and '/' not in arg[1:]:
            raise ValueError('Opção não suportada: '+arg)
        else:operands.append(path(arg))
    if name=='dir':
        if len(operands)>1:raise ValueError('Use dir [/s] [/b] [/a] [pasta].')
        return ['ls',*(['-R'] if '/s' in options else []),
                *(['-1'] if '/b' in options else ['-lh']),
                *(['-a'] if '/a' in options else []),'--',*(operands or ['.'])]
    if name in ('copy','move'):
        if len(operands)!=2:raise ValueError('Informe origem e destino; use aspas para espaços.')
        return [{'copy':'cp','move':'mv'}[name],'-f' if '/y' in options else '-i','--',*operands]
    if name in ('del','rd','md','type'):
        if not operands:raise ValueError('Informe pelo menos um caminho.')
        return {'del':['rm','-i','--'], 'rd':['rmdir','--'],
                'md':['mkdir','--'], 'type':['cat','--']}[name]+operands
    if name=='explorer':
        if len(operands)>1:raise ValueError('Use explorer [pasta].')
        return ['xdg-open',os.path.abspath(operands[0] if operands else '.')]
    fixed={'cls':['clear'],'ipconfig':['ip','-brief','address'],
           'tasklist':['ps','-eo','pid,user,pcpu,pmem,comm'], 'where':['which']}
    if name=='where':
        if not args or any(a.startswith('-') for a in args):raise ValueError('Use where nome-do-comando.')
        return ['which','--',*args]
    if name in fixed:
        if args:raise ValueError('Este comando não aceita opções nesta versão.')
        return fixed[name]
    raise ValueError('Comando não suportado. Use comandos-windows para consultar a lista.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command');parser.add_argument('args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    try:
        argv=command(args.command,args.args)
        if not shutil.which(argv[0]):raise ValueError('Ferramenta indisponível: '+argv[0])
        return subprocess.call(argv)
    except (ValueError,OSError) as error:
        print(str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
