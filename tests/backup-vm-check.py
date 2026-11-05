#!/usr/bin/env python3
"""Exercise versioned backup and restoration on a separate disposable VM disk."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

parser=argparse.ArgumentParser()
parser.add_argument('destination',type=Path)
args=parser.parse_args()
destination=args.destination.resolve(strict=True)
if os.geteuid()==0:parser.exit(1,'Execute na conta de teste, sem sudo.\n')
if destination.stat().st_dev==Path.home().stat().st_dev:
    parser.exit(1,'O destino deve estar em outro disco montado na VM de teste.\n')
work=Path(tempfile.mkdtemp(prefix='linuxbr-backup-qa-',dir=Path.home()))
repository=Path(tempfile.mkdtemp(prefix='LinuxBR-QA-',dir=destination))
source=work/'Documentos de teste';source.mkdir()
original={'Relatório com acentos.txt':'Primeira versão — ação, coração e ç.\n'.encode(),
          'apagar.txt':b'Arquivo que deve ser recuperado depois de excluido.\n',
          'perfil-web/Default/Preferences':b'{"test_profile":"Conta de teste"}\n',
          'dados.bin':bytes(range(256))*4096}
for name,data in original.items():
    path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def bup(*arguments):
    result=subprocess.run(['bup','-d',str(repository),*arguments],capture_output=True,text=True)
    print(json.dumps({'command':['bup',*arguments],'exit':result.returncode,'output':result.stdout+result.stderr},ensure_ascii=False),flush=True)
    result.check_returncode();return result.stdout


bup('init');bup('index','-u',str(source))
bup('save','-n','kup','--date',str(int(time.time())-60),'--strip',str(source))
listing=bup('ls','kup/')
revision=re.search(r'\d{4}-\d{2}-\d{2}-\d{6}',listing)
if not revision:raise RuntimeError('A versão inicial não foi encontrada no repositório.')
revision=revision.group()
(source/'Relatório com acentos.txt').write_text('Segunda versão, com alterações adicionais.\n',encoding='utf-8')
(source/'apagar.txt').unlink()
bup('index','-u',str(source));bup('save','-n','kup','--date',str(int(time.time())-30),'--strip',str(source))
restored=work/'Restaurado';restored.mkdir()
bup('restore','-C',str(restored),f'/kup/{revision}/')
for name,data in original.items():
    actual=(restored/name).read_bytes()
    assert actual==data,name
assert not (source/'apagar.txt').exists()
assert (source/'Relatório com acentos.txt').read_bytes()!=original['Relatório com acentos.txt']
result={'status':'PASS','repository':str(repository),'first_revision':revision,
        'source':str(source),'restored':str(restored),
        'checks':['versão anterior','arquivo excluído','acentos e espaços','perfil em subpastas','integridade binária','originais atuais preservados'],
        'restored_sha256':{name:hashlib.sha256((restored/name).read_bytes()).hexdigest() for name in original}}
(work/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
