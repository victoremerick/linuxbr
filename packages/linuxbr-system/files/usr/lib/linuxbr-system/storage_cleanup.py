"""Preview and verify selected cache/trash items with writers stopped."""
from datetime import datetime, timezone
import errno
import hashlib
import os
from pathlib import Path
import stat
import time
import uuid

from migration_backend import Cancelled, beneath, check_cancel, directory_fd, fingerprint, rename_noreplace


def locations():
    home = Path.home().resolve()
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(home/'.cache'))).absolute()
    data = Path(os.environ.get('XDG_DATA_HOME', str(home/'.local/share'))).absolute()
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(home/'.config'))).absolute()
    protected = [home, data, config, home/'Documents', home/'Documentos', home/'Downloads',
                 home/'Pictures', home/'Imagens', home/'Videos', home/'Vídeos', home/'Desktop', home/'Área de Trabalho']
    if cache in protected or cache == Path('/') or cache in home.parents:
        raise ValueError('A pasta de cache coincide com uma pasta pessoal ou de sistema.')
    return {'cache': cache, 'trash': data/'Trash', 'protected': protected[1:]}


def _identity(info):
    return info.st_dev, info.st_ino, info.st_uid


def _mount_id(descriptor):
    """Identify the held mount, including bind mounts that share st_dev."""
    try:
        values=[line.split(':',1)[1].strip() for line in Path('/proc/self/fdinfo',str(descriptor)).read_text().splitlines()
                if line.startswith('mnt_id:')]
        if len(values)!=1 or not values[0].isdigit() or int(values[0])<=0:raise ValueError('mnt_id')
        return int(values[0])
    except (OSError,UnicodeError,ValueError) as error:
        raise ValueError('Não foi possível identificar a montagem. A limpeza foi recusada.') from error


def _protected_identities(paths):
    identities=set()
    for path in [Path.home().resolve()]+paths['protected']:
        try:info=path.stat()
        except FileNotFoundError:continue
        except OSError as error:raise ValueError('Não foi possível conferir uma pasta pessoal protegida: '+str(path)) from error
        identities.add((info.st_dev,info.st_ino))
    return identities


def _check_root(info,paths,category):
    if info.st_uid!=os.geteuid():raise ValueError('A pasta de limpeza não pertence à conta atual.')
    if (info.st_dev,info.st_ino) in _protected_identities(paths):
        raise ValueError('A pasta de limpeza corresponde a uma pasta pessoal protegida.')
    if category=='cache' and any(path==paths['cache'] or path in paths['cache'].parents for path in paths['protected']):
        raise ValueError('A pasta de cache fica dentro de uma pasta pessoal protegida.')


def _entry(parts, info, directory=False, sha256=None):
    return {'parts':parts,'device':info.st_dev,'inode':info.st_ino,'size':info.st_size,
            'mtime_ns':info.st_mtime_ns,'ctime_ns':info.st_ctime_ns,'mode':info.st_mode,
            'uid':info.st_uid,'gid':info.st_gid,'directory':directory,'sha256':sha256}


def _matches(info, item, directory=False, renamed=False):
    if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid) != (
            item['device'],item['inode'],item['mode'],item['uid'],item['gid']):return False
    if directory:return stat.S_ISDIR(info.st_mode)
    expected=(item['device'],item['inode'],item['size'],item['mtime_ns'],item['ctime_ns'])
    return fingerprint(info)[:4] == expected[:4] if renamed else fingerprint(info) == expected


def _hash_entry(parent, name, expected, cancel=None, progress=None):
    """Read twice and compare content, descriptor metadata and the directory entry."""
    check_cancel(cancel)
    def unchanged(info):
        return (fingerprint(info)==fingerprint(expected) and
                (info.st_mode,info.st_uid,info.st_gid)==(expected.st_mode,expected.st_uid,expected.st_gid))
    if stat.S_ISLNK(expected.st_mode):
        descriptor=os.open(name,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        try:
            if _mount_id(descriptor)!=_mount_id(parent):raise ValueError('O link está em outra montagem: '+name)
            value=os.readlink('',dir_fd=descriptor)
            current=os.stat(name,dir_fd=parent,follow_symlinks=False)
            check_cancel(cancel)
            if not unchanged(os.fstat(descriptor)) or not unchanged(current) or os.readlink(name,dir_fd=parent)!=value:
                raise ValueError('O link mudou durante a conferência: '+name)
            return hashlib.sha256(os.fsencode(value)).hexdigest()
        finally:os.close(descriptor)
    if not stat.S_ISREG(expected.st_mode):raise ValueError('O item não é um arquivo regular: '+name)
    descriptor=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=parent)
    try:
        if _mount_id(descriptor)!=_mount_id(parent):raise ValueError('O arquivo está em outra montagem: '+name)
        before=os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not unchanged(before):
            raise ValueError('O arquivo mudou antes da leitura: '+name)
        previous=None
        for reading in range(2):
            check_cancel(cancel);os.lseek(descriptor,0,os.SEEK_SET);digest=hashlib.sha256()
            while True:
                check_cancel(cancel)
                block=os.read(descriptor,1024*1024)
                if not block:break
                digest.update(block)
                # A verification pass stays responsive without counting the file twice.
                if progress:progress(len(block) if reading==0 else 0)
            after=os.fstat(descriptor);current=os.stat(name,dir_fd=parent,follow_symlinks=False)
            value=digest.hexdigest()
            if not unchanged(after) or not unchanged(current) or (previous is not None and value!=previous):
                raise ValueError('O arquivo mudou durante a leitura: '+name)
            previous=value
        check_cancel(cancel)
        return previous
    finally:os.close(descriptor)


def _same_volume_parent(root, parts, device, mount_id):
    current=os.dup(root)
    try:
        if _mount_id(current)!=mount_id:raise ValueError('A montagem da pasta de limpeza mudou.')
        for part in parts:
            following=beneath(current,[part])
            try:
                if os.fstat(following).st_dev!=device or _mount_id(following)!=mount_id:
                    raise ValueError('O caminho passou a atravessar outra montagem.')
            except BaseException:os.close(following);raise
            os.close(current);current=following
        return current
    except BaseException:os.close(current);raise


def scan(category, cancel=None, notify=None, now=None):
    if category not in ('cache','trash'):raise ValueError('Escolha cache ou lixeira.')
    paths=locations();root=paths[category]
    if root.is_symlink():raise ValueError('A pasta selecionada é um link. A limpeza automática foi recusada.')
    result={'category':category,'root':str(root),'root_identity':None,'root_mount_id':None,'entries':[],'bytes':0,'hashed_bytes':0,
            'skipped':0,'errors':[],'scanned_at':datetime.now(timezone.utc).isoformat()}
    if not root.exists():return result
    now=time.time() if now is None else now
    fd=directory_fd(root)
    try:
        root_info=os.fstat(fd)
        _check_root(root_info,paths,category);mount_id=_mount_id(fd)
        result['root_identity']=list(_identity(root_info));result['root_mount_id']=mount_id;device=root_info.st_dev
        roots=['.'] if category=='cache' else ['files','info']
        for start in roots:
            check_cancel(cancel)
            try:base_fd=_same_volume_parent(fd,[] if start=='.' else [start],device,mount_id)
            except FileNotFoundError:continue
            except (OSError,ValueError) as error:result['skipped']+=1;result['errors'].append(str(error));continue
            try:
                for base,directories,files,current in os.fwalk('.',dir_fd=base_fd,follow_symlinks=False,
                        onerror=lambda error:result['errors'].append(str(error))):
                    check_cancel(cancel)
                    try:
                        if os.fstat(current).st_dev!=device or _mount_id(current)!=mount_id:
                            directories[:]=[];result['skipped']+=1;continue
                    except (OSError,ValueError) as error:
                        directories[:]=[];result['skipped']+=1;result['errors'].append(str(error));continue
                    parts=([] if start=='.' else [start])+([] if base=='.' else list(Path(base).parts))
                    for name in directories[:]:
                        target=root.joinpath(*parts,name)
                        try:
                            info=os.stat(name,dir_fd=current,follow_symlinks=False)
                            if info.st_dev!=device or (category=='cache' and any(target==item or item in target.parents for item in paths['protected'])):
                                directories.remove(name);result['skipped']+=1;continue
                            if stat.S_ISLNK(info.st_mode):directories.remove(name);files.append(name)
                            else:
                                child=_same_volume_parent(current,[name],device,mount_id)
                                os.close(child)
                        except (OSError,ValueError) as error:directories.remove(name);result['skipped']+=1;result['errors'].append(str(error))
                    for name in files:
                        check_cancel(cancel)
                        try:
                            info=os.stat(name,dir_fd=current,follow_symlinks=False)
                            if category=='cache' and (now-info.st_mtime<86400 or not stat.S_ISREG(info.st_mode)):
                                result['skipped']+=1;continue
                            if not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)) or info.st_dev!=device:
                                result['skipped']+=1;continue
                            if category=='trash' and start=='info' and (len(parts)!=1 or not name.endswith('.trashinfo')):
                                result['skipped']+=1;continue
                            def progress(size):
                                result['hashed_bytes']+=size
                                if notify:notify({'phase':'scan','entries':len(result['entries']),'bytes':result['bytes'],
                                                  'hashed_bytes':result['hashed_bytes'],'path':'/'.join(parts+[name])})
                            value=_hash_entry(current,name,info,cancel,progress)
                            result['entries'].append(_entry(parts+[name],info,sha256=value))
                            result['bytes']+=getattr(info,'st_blocks',0)*512
                        except (OSError,ValueError) as error:result['errors'].append(str(error))
                    if parts and parts not in (['files'],['info']):result['entries'].append(_entry(parts,os.fstat(current),directory=True))
                    if notify:notify({'phase':'scan','entries':len(result['entries']),'bytes':result['bytes'],'hashed_bytes':result['hashed_bytes']})
                    if len(result['entries'])>200000:raise ValueError('Há muitos itens. Limpe uma parte pelo Explorador de arquivos.')
            finally:os.close(base_fd)
    finally:os.close(fd)
    return result


def _restore_capture(parent,capture,name,path,result):
    try:rename_noreplace(parent,capture,parent,name)
    except FileNotFoundError:
        result['errors'].append('O item capturado deixou de estar disponível: '+str(path))
    except OSError:
        result['preserved'].append(str(path))
        result['errors'].append('O nome original está ocupado ou não pôde ser restaurado. Item preservado em '+str(path))


def clean(plan, cancel=None, notify=None):
    paths=locations();current_root=paths.get(plan['category'])
    if current_root is None or str(current_root)!=plan['root']:raise ValueError('O destino de limpeza mudou. Confira novamente.')
    result={'removed':0,'changed_or_retained':0,'errors':[],'cancelled':False,'preserved':[],
            'limitations':['Feche os aplicativos antes de conferir e limpar. Arquivos em uso podem continuar mudando durante a limpeza.']}
    root=directory_fd(current_root)
    try:
        root_info=os.fstat(root)
        _check_root(root_info,paths,plan['category']);mount_id=_mount_id(root)
        if root_info.st_uid!=os.geteuid() or list(_identity(root_info))!=plan.get('root_identity'):
            raise ValueError('A identidade ou o proprietário da pasta de limpeza mudou. Confira novamente.')
        if mount_id!=plan.get('root_mount_id'):raise ValueError('A montagem da pasta de limpeza mudou. Confira novamente.')
        device=root_info.st_dev;blocked_trash=set()
        entries=sorted(plan['entries'],key=lambda item:(item['parts'][0]=='info' if plan['category']=='trash' else False,
                                                        item['directory'],-len(item['parts'])))
        for item in entries:
            check_cancel(cancel);parent=None;capture=None;removed=False
            parts=item['parts'];name=parts[-1]
            trash_name=parts[1] if plan['category']=='trash' and len(parts)>1 and parts[0]=='files' else None
            try:
                parent=_same_volume_parent(root,parts[:-1],device,mount_id)
                if plan['category']=='trash' and parts[0]=='info':
                    counterpart=name[:-10] if len(parts)==2 and name.endswith('.trashinfo') else None
                    if counterpart is None or counterpart in blocked_trash:
                        result['changed_or_retained']+=1;continue
                    files=None
                    try:
                        files=_same_volume_parent(root,['files'],device,mount_id)
                        os.stat(counterpart,dir_fd=files,follow_symlinks=False)
                    except FileNotFoundError:pass
                    else:result['changed_or_retained']+=1;continue
                    finally:
                        if files is not None:os.close(files)
                info=os.stat(name,dir_fd=parent,follow_symlinks=False)
                if info.st_dev!=device or not _matches(info,item,directory=item['directory']):
                    result['changed_or_retained']+=1;continue
                if item['directory']:
                    child=_same_volume_parent(parent,[name],device,mount_id)
                    os.close(child)
                capture='.linuxbr-limpeza-'+uuid.uuid4().hex
                try:rename_noreplace(parent,name,parent,capture)
                except BaseException:capture=None;raise
                check_cancel(cancel)
                captured=os.stat(capture,dir_fd=parent,follow_symlinks=False)
                if not _matches(captured,item,directory=item['directory'],renamed=True):
                    result['changed_or_retained']+=1;continue
                if item['directory']:
                    check_cancel(cancel)
                    try:os.rmdir(capture,dir_fd=parent)
                    except OSError as error:
                        if error.errno in (errno.ENOTEMPTY,errno.EEXIST):
                            result['changed_or_retained']+=1;continue
                        raise
                else:
                    verified_bytes=0
                    def progress(size):
                        nonlocal verified_bytes
                        verified_bytes+=size
                        if notify:notify({**result,'phase':'verify','path':'/'.join(parts),'verified_bytes':verified_bytes,'file_bytes':item['size']})
                    if _hash_entry(parent,capture,captured,cancel,progress)!=item['sha256']:
                        result['changed_or_retained']+=1;continue
                    check_cancel(cancel);os.unlink(capture,dir_fd=parent)
                capture=None;removed=True;result['removed']+=1
            except FileNotFoundError:result['changed_or_retained']+=1
            except Cancelled:
                result['changed_or_retained']+=1;raise
            except (OSError,ValueError) as error:
                result['changed_or_retained']+=1;result['errors'].append(str(error))
            finally:
                if not removed and trash_name:blocked_trash.add(trash_name)
                if capture is not None and parent is not None:
                    path=Path(plan['root'],*parts[:-1],capture)
                    _restore_capture(parent,capture,name,path,result)
                if parent is not None:os.close(parent)
            if notify:notify({**result,'phase':'clean'})
    except Cancelled:result['cancelled']=True
    finally:os.close(root)
    return result
