#!/usr/bin/python3
"""Reject nested mounts by held mount identity, including same-device binds."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0,str(LIB))
import storage_cleanup as cleanup


class CleanupMounts08(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.base=Path(temporary.name)
        self.home=self.base/'home';self.home.mkdir();self.cache=self.home/'.cache';self.cache.mkdir()
        self.data=self.home/'.local/share';self.data.mkdir(parents=True)
        environment=patch.dict(os.environ,{'HOME':str(self.home),'XDG_CACHE_HOME':str(self.cache),
            'XDG_DATA_HOME':str(self.data),'XDG_CONFIG_HOME':str(self.home/'.config')})
        environment.start();self.addCleanup(environment.stop)

    def old(self,name='item'):
        path=self.cache/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'personal')
        os.utime(path,(time.time()-90000,)*2);return path

    def foreign_mount(self,path,active=lambda:True):
        original=cleanup._mount_id;identity=(path.stat().st_dev,path.stat().st_ino)
        def mounted(descriptor):
            info=os.fstat(descriptor)
            return original(descriptor)+(1000 if active() and (info.st_dev,info.st_ino)==identity else 0)
        return patch.object(cleanup,'_mount_id',side_effect=mounted)

    def test_same_device_directory_bind_is_skipped_before_hashing(self):
        item=self.old('bound/item');self.assertEqual(item.stat().st_dev,self.cache.stat().st_dev)
        with self.foreign_mount(item.parent),patch.object(cleanup,'_hash_entry') as hashing:
            plan=cleanup.scan('cache');hashing.assert_not_called()
        self.assertEqual(plan['entries'],[]);self.assertGreater(plan['skipped'],0)
        self.assertEqual(item.read_bytes(),b'personal')

    def test_fwalk_current_mount_is_checked_again_after_directory_prefilter(self):
        item=self.old('bound/item');entered=False;walking=os.fwalk
        def walk(*args,**kwargs):
            nonlocal entered
            for result in walking(*args,**kwargs):
                if Path(result[0]).name=='bound':entered=True
                yield result
        with self.foreign_mount(item.parent,lambda:entered),patch.object(cleanup.os,'fwalk',side_effect=walk),patch.object(cleanup,'_hash_entry') as hashing:
            plan=cleanup.scan('cache');hashing.assert_not_called()
        self.assertTrue(entered);self.assertEqual(plan['entries'],[]);self.assertGreater(plan['skipped'],0)

    def test_same_device_file_bind_is_refused_before_any_content_read(self):
        item=self.old()
        with self.foreign_mount(item),patch.object(cleanup.os,'read',side_effect=AssertionError('O arquivo montado não pode ser lido')):
            plan=cleanup.scan('cache')
        self.assertEqual(plan['entries'],[]);self.assertTrue(plan['errors']);self.assertEqual(plan['hashed_bytes'],0)
        self.assertEqual(item.read_bytes(),b'personal')

    def test_new_directory_bind_after_preview_is_retained_without_capture(self):
        item=self.old('bound/item');plan=cleanup.scan('cache')
        with self.foreign_mount(item.parent),patch.object(cleanup,'rename_noreplace') as rename:
            result=cleanup.clean(plan);rename.assert_not_called()
        self.assertEqual(result['removed'],0);self.assertTrue(result['errors']);self.assertEqual(item.read_bytes(),b'personal')

    def test_file_mount_after_capture_is_restored_without_read_or_unlink(self):
        item=self.old();plan=cleanup.scan('cache')
        with self.foreign_mount(item),patch.object(cleanup.os,'read',side_effect=AssertionError('Não ler outra montagem')):
            result=cleanup.clean(plan)
        self.assertEqual(result['removed'],0);self.assertTrue(result['errors']);self.assertEqual(item.read_bytes(),b'personal')
        self.assertEqual(list(self.cache.glob('.linuxbr-limpeza-*')),[])

    def test_mount_id_unavailable_refuses_scan_and_clean(self):
        item=self.old();plan=cleanup.scan('cache');reading=Path.read_text
        def unavailable(path,*args,**kwargs):
            if str(path).startswith('/proc/self/fdinfo/'):return 'pos:\t0\nflags:\t0100000\n'
            return reading(path,*args,**kwargs)
        with patch.object(Path,'read_text',unavailable):
            with self.assertRaisesRegex(ValueError,'montagem'):cleanup.scan('cache')
            with self.assertRaisesRegex(ValueError,'montagem'):cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'personal')

    def test_root_mount_replacement_is_refused_even_with_same_inode_and_device(self):
        item=self.old();plan=cleanup.scan('cache');self.assertIsInstance(plan['root_mount_id'],int)
        with self.foreign_mount(self.cache):
            with self.assertRaisesRegex(ValueError,'montagem'):cleanup.clean(plan)
        self.assertEqual(item.read_bytes(),b'personal')

    def test_root_identity_alias_of_a_personal_directory_is_refused(self):
        item=self.old();identity=(self.cache.stat().st_dev,self.cache.stat().st_ino)
        with patch.object(cleanup,'_protected_identities',return_value={identity}):
            with self.assertRaisesRegex(ValueError,'protegida'):cleanup.scan('cache')
        self.assertEqual(item.read_bytes(),b'personal')

    def test_cache_nested_in_a_protected_personal_directory_is_refused(self):
        target=self.home/'Documentos/cache';target.mkdir(parents=True);item=target/'personal';item.write_bytes(b'keep')
        with patch.dict(os.environ,{'XDG_CACHE_HOME':str(target)}):
            with self.assertRaisesRegex(ValueError,'protegida'):cleanup.scan('cache')
        self.assertEqual(item.read_bytes(),b'keep')

    @unittest.skipUnless(Path('/dev/shm').is_dir() and os.access('/dev/shm',os.W_OK),'Unidade temporária separada indisponível')
    def test_genuine_cache_on_a_separate_unit_is_allowed(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm',prefix='linuxbr-cleanup-') as directory:
            target=Path(directory)
            if target.stat().st_dev==self.home.stat().st_dev:self.skipTest('As pastas de teste estão no mesmo dispositivo')
            item=target/'cache';item.write_bytes(b'cache');os.utime(item,(time.time()-90000,)*2)
            with patch.dict(os.environ,{'XDG_CACHE_HOME':str(target)}):
                plan=cleanup.scan('cache');result=cleanup.clean(plan)
            self.assertEqual(result['removed'],1);self.assertFalse(item.exists())

    @unittest.skipUnless(shutil.which('unshare') and shutil.which('mount'),'Namespaces de montagem indisponíveis')
    def test_real_bind_mounts_in_a_private_user_and_mount_namespace(self):
        prefix=['unshare','--user','--map-root-user','--mount','--propagation','private']
        probe=subprocess.run(prefix+['true'],capture_output=True,text=True)
        if probe.returncode:self.skipTest('Namespace privado recusado: '+probe.stderr.strip()[:160])
        program=r'''
import os,sys,tempfile,time,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import storage_cleanup as cleanup
with tempfile.TemporaryDirectory(dir=sys.argv[2]) as directory:
 base=Path(directory);home=base/'home';home.mkdir();cache=home/'.cache';cache.mkdir()
 docs=home/'Documentos';docs.mkdir();personal=docs/'personal';personal.write_bytes(b'personal')
 bound=cache/'bound';bound.mkdir();mounted_file=cache/'mounted-file';mounted_file.touch()
 normal=cache/'normal';normal.write_bytes(b'cache')
 for path in (personal,normal):os.utime(path,(time.time()-90000,)*2)
 os.environ.update(HOME=str(home),XDG_CACHE_HOME=str(cache),XDG_DATA_HOME=str(home/'.local/share'),XDG_CONFIG_HOME=str(home/'.config'))
 subprocess.run(['mount','--bind',str(docs),str(bound)],check=True)
 subprocess.run(['mount','--bind',str(personal),str(mounted_file)],check=True)
 assert cache.stat().st_dev==bound.stat().st_dev==mounted_file.stat().st_dev
 plan=cleanup.scan('cache');assert [item['parts'] for item in plan['entries']]==[['normal']],plan
 result=cleanup.clean(plan);assert result['removed']==1 and not normal.exists(),result
 assert personal.read_bytes()==b'personal' and mounted_file.read_bytes()==b'personal'
 subprocess.run(['umount',str(mounted_file)],check=True);subprocess.run(['umount',str(bound)],check=True)
 subprocess.run(['mount','--bind',str(docs),str(cache)],check=True)
 try:
  try:cleanup.scan('cache')
  except ValueError:pass
  else:raise AssertionError('O alias da pasta pessoal foi aceito como cache')
 finally:subprocess.run(['umount',str(cache)],check=True)
 print('PASS: binds reais de diretório, arquivo e raiz protegida em namespace privado')
'''
        result=subprocess.run(prefix+[sys.executable,'-c',program,str(LIB),str(self.base)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)


if __name__=='__main__':unittest.main()
