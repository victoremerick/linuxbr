#!/usr/bin/python3
"""Deterministic cleanup races using private cache/trash directories."""
import errno
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import storage_cleanup as cleanup
from migration_backend import Cancelled


class CleanupRaces08(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.base=Path(temporary.name)
        self.home=self.base/'home';self.home.mkdir();self.cache=self.home/'.cache';self.cache.mkdir()
        self.data=self.home/'.local/share';self.data.mkdir(parents=True)
        environment=patch.dict(os.environ,{'HOME':str(self.home),'XDG_CACHE_HOME':str(self.cache),
            'XDG_DATA_HOME':str(self.data),'XDG_CONFIG_HOME':str(self.home/'.config')})
        environment.start();self.addCleanup(environment.stop)

    def old(self,name='item',data=b'old1'):
        path=self.cache/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        os.utime(path,(time.time()-90000,)*2);return path

    def trash(self,directory=False):
        root=self.data/'Trash';(root/'files').mkdir(parents=True);(root/'info').mkdir()
        item=root/'files'/'item'
        if directory:item.mkdir();(item/'child').write_bytes(b'old1')
        else:item.write_bytes(b'old1')
        metadata=root/'info/item.trashinfo';metadata.write_text('[Trash Info]\nPath=/original/item\n')
        return root,item,metadata

    def captures(self):return list(self.home.rglob('.linuxbr-limpeza-*'))

    def test_scan_records_stable_hashes_and_link_text_without_following(self):
        item=self.old();plan=cleanup.scan('cache')
        entry=plan['entries'][0];self.assertEqual(entry['sha256'],hashlib.sha256(item.read_bytes()).hexdigest())
        self.assertEqual(plan['hashed_bytes'],item.stat().st_size)
        self.assertEqual(plan['root_identity'],[self.cache.stat().st_dev,self.cache.stat().st_ino,os.geteuid()])
        root,trash,metadata=self.trash();outside=self.home/'outside';outside.write_bytes(b'personal')
        trash.unlink();trash.symlink_to(outside)
        preview=cleanup.scan('trash');link=next(entry for entry in preview['entries'] if entry['parts']==['files','item'])
        self.assertEqual(link['sha256'],hashlib.sha256(os.fsencode(str(outside))).hexdigest())
        result=cleanup.clean(preview);self.assertFalse(trash.is_symlink());self.assertFalse(metadata.exists())
        self.assertEqual(outside.read_bytes(),b'personal');self.assertEqual(result['errors'],[])

    def test_scan_rejects_a_file_modified_during_hash_with_restored_mtime(self):
        item=self.old(data=b'a'*(2*1024*1024));before=item.stat();changed=False
        def progress(info):
            nonlocal changed
            if info.get('hashed_bytes') and not changed:
                changed=True;item.write_bytes(b'b'*(2*1024*1024));os.utime(item,ns=(before.st_atime_ns,before.st_mtime_ns))
        fingerprint=cleanup.fingerprint
        # Emulate a filesystem whose change time cannot distinguish these writes.
        with patch.object(cleanup,'fingerprint',side_effect=lambda info:fingerprint(info)[:4]+(0,)):
            plan=cleanup.scan('cache',notify=progress)
        self.assertEqual(plan['entries'],[]);self.assertTrue(plan['errors']);self.assertEqual(item.read_bytes(),b'b'*(2*1024*1024))

    def test_scan_hash_can_be_cancelled_without_changes(self):
        item=self.old(data=b'a'*(3*1024*1024));cancel=threading.Event()
        with self.assertRaises(Cancelled):cleanup.scan('cache',cancel,lambda info:cancel.set() if info.get('hashed_bytes') else None)
        self.assertEqual(item.stat().st_size,3*1024*1024);self.assertEqual(self.captures(),[])

    def test_root_replacement_and_owner_mismatch_are_refused(self):
        item=self.old();plan=cleanup.scan('cache');original=self.home/'original-cache';self.cache.rename(original);self.cache.mkdir()
        (self.cache/'item').write_bytes(b'NEW2')
        with self.assertRaises(ValueError):cleanup.clean(plan)
        self.assertEqual((self.cache/'item').read_bytes(),b'NEW2');self.assertEqual((original/'item').read_bytes(),b'old1')
        plan=cleanup.scan('cache');current_uid=os.geteuid()
        with patch.object(cleanup.os,'geteuid',return_value=current_uid+1):
            with self.assertRaises(ValueError):cleanup.scan('cache')
            with self.assertRaises(ValueError):cleanup.clean(plan)

    def test_changed_file_with_preserved_size_and_mtime_is_kept(self):
        item=self.old();plan=cleanup.scan('cache');before=item.stat();item.write_bytes(b'NEW2')
        os.utime(item,ns=(before.st_atime_ns,before.st_mtime_ns));result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'NEW2');self.assertEqual(result['removed'],0);self.assertEqual(result['changed_or_retained'],1)

    def test_same_inode_edit_between_stat_and_capture_is_restored(self):
        item=self.old();plan=cleanup.scan('cache');before=item.stat();rename=cleanup.rename_noreplace
        def race(source_fd,source,destination_fd,destination):
            if source=='item':item.write_bytes(b'NEW2');os.utime(item,ns=(before.st_atime_ns,before.st_mtime_ns))
            return rename(source_fd,source,destination_fd,destination)
        with patch.object(cleanup,'rename_noreplace',side_effect=race):result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'NEW2');self.assertEqual(result['removed'],0);self.assertEqual(self.captures(),[])

    def test_new_inode_swap_before_capture_preserves_both_versions(self):
        item=self.old();plan=cleanup.scan('cache');before=item.stat();rename=cleanup.rename_noreplace
        moved=self.cache/'moved-original'
        def race(source_fd,source,destination_fd,destination):
            if source=='item':
                item.rename(moved);item.write_bytes(b'NEW2');os.utime(item,ns=(before.st_atime_ns,before.st_mtime_ns))
            return rename(source_fd,source,destination_fd,destination)
        with patch.object(cleanup,'rename_noreplace',side_effect=race):result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'NEW2');self.assertEqual(moved.read_bytes(),b'old1');self.assertEqual(result['removed'],0)

    def test_restore_never_overwrites_a_new_original_name_and_reports_capture(self):
        item=self.old();plan=cleanup.scan('cache');before=item.stat();rename=cleanup.rename_noreplace
        def race(source_fd,source,destination_fd,destination):
            value=rename(source_fd,source,destination_fd,destination)
            if source=='item':
                captured=self.cache/destination;captured.write_bytes(b'CHG2');os.utime(captured,ns=(before.st_atime_ns,before.st_mtime_ns))
                item.write_bytes(b'NEW3')
            return value
        with patch.object(cleanup,'rename_noreplace',side_effect=race):result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'NEW3');self.assertEqual(result['removed'],0);self.assertEqual(len(result['preserved']),1)
        self.assertEqual(Path(result['preserved'][0]).read_bytes(),b'CHG2');self.assertTrue(result['errors'])

    def test_cancel_immediately_after_capture_restores_the_item(self):
        item=self.old();plan=cleanup.scan('cache');cancel=threading.Event();rename=cleanup.rename_noreplace
        def race(source_fd,source,destination_fd,destination):
            value=rename(source_fd,source,destination_fd,destination)
            if source=='item':cancel.set()
            return value
        with patch.object(cleanup,'rename_noreplace',side_effect=race):result=cleanup.clean(plan,cancel)
        self.assertTrue(result['cancelled']);self.assertEqual(item.read_bytes(),b'old1');self.assertEqual(self.captures(),[])

    def test_cancel_during_captured_hash_restores_complete_bytes(self):
        item=self.old(data=b'a'*(3*1024*1024));plan=cleanup.scan('cache');cancel=threading.Event()
        result=cleanup.clean(plan,cancel,lambda info:cancel.set() if info.get('phase')=='verify' else None)
        self.assertTrue(result['cancelled']);self.assertEqual(item.read_bytes(),b'a'*(3*1024*1024));self.assertEqual(self.captures(),[])

    def test_file_swapped_for_a_link_before_capture_never_touches_its_target(self):
        item=self.old();plan=cleanup.scan('cache');rename=cleanup.rename_noreplace
        outside=self.home/'personal';outside.write_bytes(b'personal data');saved=self.cache/'previous-item'
        def race(source_fd,source,destination_fd,destination):
            if source=='item':item.rename(saved);item.symlink_to(outside)
            return rename(source_fd,source,destination_fd,destination)
        with patch.object(cleanup,'rename_noreplace',side_effect=race):result=cleanup.clean(plan)
        self.assertTrue(item.is_symlink());self.assertEqual(outside.read_bytes(),b'personal data')
        self.assertEqual(saved.read_bytes(),b'old1');self.assertEqual(result['removed'],0)

    def test_read_or_unlink_error_restores_the_captured_item(self):
        item=self.old();plan=cleanup.scan('cache')
        with patch.object(cleanup,'_hash_entry',side_effect=OSError('Falha de leitura')):result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'old1');self.assertTrue(result['errors']);self.assertEqual(self.captures(),[])
        plan=cleanup.scan('cache');unlink=os.unlink
        def fail_capture(name,*args,**kwargs):
            if str(name).startswith('.linuxbr-limpeza-'):raise PermissionError('Destino indisponível')
            return unlink(name,*args,**kwargs)
        with patch.object(cleanup.os,'unlink',side_effect=fail_capture):result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'old1');self.assertTrue(result['errors']);self.assertEqual(self.captures(),[])

    def test_trash_metadata_survives_preserved_capture_with_original_name_absent(self):
        root,item,metadata=self.trash();plan=cleanup.scan('trash');rename=cleanup.rename_noreplace
        def fail_restore(source_fd,source,destination_fd,destination):
            if str(source).startswith('.linuxbr-limpeza-') and destination=='item':raise PermissionError('Não foi possível restaurar o nome')
            return rename(source_fd,source,destination_fd,destination)
        with patch.object(cleanup,'rename_noreplace',side_effect=fail_restore),patch.object(cleanup,'_hash_entry',side_effect=OSError('Leitura indisponível')):
            result=cleanup.clean(plan)
        self.assertFalse(item.exists());self.assertTrue(metadata.exists());self.assertEqual(len(result['preserved']),1)
        self.assertEqual(Path(result['preserved'][0]).read_bytes(),b'old1')

    def test_directory_with_a_new_child_is_restored_and_keeps_trash_metadata(self):
        root,item,metadata=self.trash(directory=True);plan=cleanup.scan('trash');rename=cleanup.rename_noreplace
        def race(source_fd,source,destination_fd,destination):
            if source=='item':(item/'new').write_bytes(b'new personal data')
            return rename(source_fd,source,destination_fd,destination)
        with patch.object(cleanup,'rename_noreplace',side_effect=race):result=cleanup.clean(plan)
        self.assertTrue(metadata.exists());self.assertEqual((item/'new').read_bytes(),b'new personal data')
        self.assertFalse((item/'child').exists());self.assertEqual(self.captures(),[]);self.assertEqual(result['errors'],[])

    def test_replaced_parent_link_is_not_followed(self):
        item=self.old('folder/item');plan=cleanup.scan('cache');folder=item.parent;folder.rename(self.cache/'previous-folder')
        outside=self.home/'outside';outside.mkdir();(outside/'item').write_bytes(b'personal')
        folder.symlink_to(outside,target_is_directory=True);result=cleanup.clean(plan)
        self.assertEqual((outside/'item').read_bytes(),b'personal');self.assertTrue(folder.is_symlink());self.assertTrue(result['errors'])

    def test_new_mount_boundary_in_parent_is_refused_and_report_explains_writers(self):
        item=self.old('folder/item');plan=cleanup.scan('cache');fstat=os.fstat
        def other_volume(descriptor):
            info=fstat(descriptor)
            if os.readlink('/proc/self/fd/'+str(descriptor))==str(item.parent):
                return SimpleNamespace(**{name:getattr(info,name) for name in dir(info) if name.startswith('st_') and name!='st_dev'},st_dev=info.st_dev+1)
            return info
        with patch.object(cleanup.os,'fstat',side_effect=other_volume):result=cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'old1');self.assertTrue(result['errors']);self.assertIn('Arquivos em uso',result['limitations'][0])


if __name__=='__main__':unittest.main()
