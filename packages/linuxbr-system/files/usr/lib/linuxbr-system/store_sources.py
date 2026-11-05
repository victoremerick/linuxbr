"""Repository inventory and narrowly scoped APT source changes."""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import urllib.parse

SOURCE_DIR=Path('/etc/apt/sources.list.d')
SLUG=re.compile(r'[a-z0-9][a-z0-9-]{0,59}')


def digest(data):return hashlib.sha256(data).hexdigest()


def apt_sources():
    paths=[Path('/etc/apt/sources.list')]+sorted(SOURCE_DIR.glob('*.list'))+sorted(SOURCE_DIR.glob('*.sources'))
    rows=[]
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file():continue
            raw=path.read_bytes()
            if len(raw)>1048576:continue
            text=raw.decode('utf-8');active=bool(re.search(r'^\s*deb(?:-src)?\s',text,re.M)) if path.suffix=='.list' or path.name=='sources.list' else any('Types:' in p and not re.search(r'^Enabled:\s*no\s*$',p,re.M|re.I) for p in re.split(r'\n\s*\n',text))
            rows.append(dict(kind='APT',name=path.name,path=str(path),enabled=active,sha256=digest(raw),content=text,managed=path.name.startswith('linuxbr-extra-')))
        except (OSError,UnicodeError):continue
    return rows


def flatpak_sources(scope='user'):
    result=subprocess.run(['/usr/bin/flatpak','--'+scope,'remotes','--show-disabled','--columns=name,title,url,options'],capture_output=True,text=True,timeout=15)
    if result.returncode:return []
    rows=[]
    for line in result.stdout.splitlines():
        values=line.split('\t')
        if len(values)>=4:rows.append(dict(kind='Flatpak',name=values[0],title=values[1],url=values[2],scope=scope,enabled='disabled' not in values[3],options=values[3]))
    return rows


def https_url(value):
    url=urllib.parse.urlsplit(value)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment or any(c.isspace() for c in value):raise ValueError('Informe uma URL HTTPS sem credenciais ou fragmentos.')
    return value


def checked_key(value):
    path=Path(value)
    if not path.is_absolute() or path.suffix not in ('.gpg','.asc'):raise ValueError('Escolha uma chave .gpg ou .asc instalada no sistema.')
    if path.parent not in (Path('/usr/share/keyrings'),Path('/etc/apt/keyrings')) or path.lstat().st_uid!=0:raise ValueError('Escolha uma chave instalada pelo administrador no diretório de chaves.')
    resolved=path.resolve(strict=True)
    if resolved.parent not in (Path('/usr/share/keyrings'),Path('/etc/apt/keyrings')):raise ValueError('A chave deve estar em /usr/share/keyrings ou /etc/apt/keyrings.')
    info=resolved.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise ValueError('A chave deve pertencer ao administrador e não permitir escrita por outros usuários.')
    return str(resolved)


def source_text(request):
    url=https_url(request['url']);suite=request['suite'].strip();components=request['components'].split()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,99}',suite):raise ValueError('Distribuição ou suíte inválida.')
    if not components or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_/-]{0,79}',c) for c in components):raise ValueError('Informe componentes válidos, como main ou main contrib non-free-firmware.')
    key=checked_key(request['key'])
    return 'Types: deb\nURIs: '+url+'\nSuites: '+suite+'\nComponents: '+' '.join(components)+'\nSigned-By: '+key+'\nEnabled: yes\n'


def inspect_key(data):
    if not isinstance(data,bytes) or not 0<len(data)<=32768:raise ValueError('Selecione uma chave pública de até 32 KiB.')
    with tempfile.TemporaryDirectory(prefix='linuxbr-key-') as folder:
        result=subprocess.run(['/usr/bin/gpg','--no-options','--homedir',folder,'--batch','--with-colons','--show-keys'],input=data,capture_output=True,timeout=10)
    if result.returncode:raise ValueError('O arquivo não contém uma chave pública OpenPGP válida.')
    lines=[line.split(':') for line in result.stdout.decode('utf-8',errors='replace').splitlines()]
    if any(row[0] in ('sec','ssb') for row in lines) or sum(row[0]=='pub' for row in lines)!=1:raise ValueError('Use somente uma chave pública, sem chaves privadas.')
    fingerprint=next((row[9] for row in lines if row[0]=='fpr' and len(row)>9),'')
    if not re.fullmatch(r'[A-F0-9]{40}|[A-F0-9]{64}',fingerprint):raise ValueError('A impressão digital da chave não foi reconhecida.')
    return fingerprint


def atomic_write(path,data,mode=0o644):
    fd,name=tempfile.mkstemp(prefix='.linuxbr-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(name,mode);os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)


def apply(request):
    if os.geteuid()!=0:raise PermissionError('Esta alteração exige autorização administrativa.')
    if not isinstance(request,dict):raise ValueError('Pedido inválido.')
    action=request.get('action')
    if action=='install-key':
        name=request.get('name','')
        if not SLUG.fullmatch(name):raise ValueError('Identificador da chave inválido.')
        data=base64.b64decode(request.get('data',''),validate=True);fingerprint=inspect_key(data)
        if fingerprint!=request.get('fingerprint'):raise ValueError('A chave não corresponde à impressão digital revisada.')
        folder=Path('/etc/apt/keyrings');folder.mkdir(mode=0o755,parents=True,exist_ok=True)
        if folder.is_symlink() or folder.stat().st_uid!=0 or folder.stat().st_mode&0o022:raise ValueError('O diretório de chaves não possui permissões seguras.')
        path=folder/('linuxbr-'+name+('.asc' if data.lstrip().startswith(b'-----BEGIN PGP PUBLIC KEY BLOCK-----') else '.gpg'))
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        return dict(status='PASS',path=str(path),fingerprint=fingerprint)
    if action=='add':
        name=request.get('name','')
        if not SLUG.fullmatch(name):raise ValueError('Use letras minúsculas, números e traços no identificador da fonte.')
        path=SOURCE_DIR/('linuxbr-extra-'+name+'.sources')
        if path.exists() or path.is_symlink():raise ValueError('Já existe uma fonte com esse identificador.')
        SOURCE_DIR.mkdir(mode=0o755,parents=True,exist_ok=True)
        text=source_text(request)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'wb') as stream:stream.write(text.encode());stream.flush();os.fsync(stream.fileno())
        return dict(status='PASS',path=str(path))
    if action not in ('enable','disable','edit','remove'):raise ValueError('Operação inválida.')
    path=Path(request.get('path',''))
    if path!=Path('/etc/apt/sources.list') and (path.parent!=SOURCE_DIR or path.suffix not in ('.list','.sources')):raise ValueError('Arquivo fora dos locais de fontes permitidos.')
    if path.is_symlink():raise ValueError('Links simbólicos não podem ser editados por esta interface.')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Propriedade ou permissões do arquivo não são seguras.')
        raw=stream.read(1048577)
        if len(raw)>1048576 or digest(raw)!=request.get('sha256'):raise ValueError('A fonte foi alterada por outro processo. Atualize a lista antes de continuar.')
        current=path.lstat()
        if current.st_ino!=info.st_ino or current.st_dev!=info.st_dev:raise ValueError('O arquivo mudou durante a edição.')
        if action in ('edit','remove') and not path.name.startswith('linuxbr-extra-'):raise ValueError('Esta fonte não foi criada pela Loja. É possível habilitar ou desabilitar sem substituir seu conteúdo.')
        backup=Path('/var/backups/linuxbr-sources');backup.mkdir(parents=True,exist_ok=True,mode=0o700)
        save=backup/(path.name+'.'+digest(raw)+'.bak')
        if not save.exists():
            with save.open('xb') as output:output.write(raw)
            save.chmod(0o600)
        if action=='remove':path.unlink()
        else:
            if action=='edit':text=source_text(request)
            elif path.suffix=='.sources':
                paragraphs=[]
                for part in re.split(r'\n\s*\n',raw.decode('utf-8')):
                    if re.search(r'^Types:',part,re.M):
                        enabled='Enabled: '+('yes' if action=='enable' else 'no')
                        part=re.sub(r'^Enabled:[^\n]*',enabled,part,flags=re.M|re.I) if re.search(r'^Enabled:',part,re.M|re.I) else part.rstrip()+'\n'+enabled
                    paragraphs.append(part)
                text='\n\n'.join(paragraphs).rstrip()+'\n'
            else:
                lines=[]
                for line in raw.decode('utf-8').splitlines():
                    if action=='disable' and re.match(r'^\s*deb(?:-src)?\s',line):line='# '+line
                    elif action=='enable' and re.match(r'^\s*#\s*deb(?:-src)?\s',line):line=re.sub(r'^\s*#\s*','',line,count=1)
                    lines.append(line)
                text='\n'.join(lines)+'\n'
            atomic_write(path,text.encode('utf-8'))
        return dict(status='PASS',path=str(path),backup=str(save))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:raise SystemExit(2)
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise ValueError('Pedido muito grande.')
        print(json.dumps(apply(json.loads(raw)),ensure_ascii=False))
    except Exception as error:print(json.dumps(dict(status='FAIL',error=str(error)),ensure_ascii=False));raise SystemExit(1)
