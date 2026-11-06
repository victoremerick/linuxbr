from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
spec=importlib.util.spec_from_file_location('publisher',root/'scripts/publish-github-release.py')
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)


class UploadTests(unittest.TestCase):
    def test_split_reassembles_exactly_and_keeps_parts_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source=folder/'linuxbr-test.iso';payload=bytes(range(256))*9
            source.write_bytes(payload);output=folder/'upload';output.mkdir()
            parts=publisher.stage_artifact(source,output,limit=512)
            self.assertEqual(len(parts),5)
            self.assertTrue(all(p.stat().st_size<=512 for p in parts))
            self.assertEqual(b''.join(p.read_bytes() for p in parts),payload)
            self.assertEqual(source.read_bytes(),payload)

    def test_small_artifact_is_not_split_or_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source=folder/'checks.json';source.write_text('{}')
            output=folder/'upload';output.mkdir()
            self.assertEqual(publisher.stage_artifact(source,output,limit=512)[0].name,source.name)
            with self.assertRaises(ValueError):publisher.stage_artifact(source,output,limit=512)

    def test_existing_part_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source=folder/'image.iso';source.write_bytes(b'a'*12)
            output=folder/'upload';output.mkdir();(output/'image.iso.part001').write_bytes(b'keep')
            with self.assertRaises(ValueError):publisher.stage_artifact(source,output,limit=4)
            self.assertEqual((output/'image.iso.part001').read_bytes(),b'keep')

    def test_publish_waits_until_every_upload_completes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);artifact=folder/'test.iso';artifact.write_bytes(b'iso')
            notes=folder/'notes.md';notes.write_text('Notas da candidata.')
            calls=[]
            def run(argv,**kwargs):calls.append(argv)
            def git(argv,**kwargs):return 'abc123' if kwargs.get('text') else b''
            with patch.object(publisher.subprocess,'run',side_effect=run), \
                 patch.object(publisher.subprocess,'check_output',side_effect=git), \
                 patch.object(publisher.shutil,'disk_usage',return_value=SimpleNamespace(free=10**12)), \
                 patch.object(publisher,'release_info',return_value={'channel':'rc','version':'1.0.0~rc2','display_version':'1.0.0 RC 2'}):
                publisher.main(['--artifact',str(artifact),'--notes',str(notes),'--publish'])
            self.assertIn('--draft',calls[0]);self.assertIn('--prerelease',calls[0])
            self.assertEqual([c[2] for c in calls],['create','upload','upload','upload','edit'])
            self.assertIn('--draft=false',calls[-1])

    def test_upload_failure_never_publishes_partial_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);artifact=folder/'test.iso';artifact.write_bytes(b'iso')
            notes=folder/'notes.md';notes.write_text('Notas da candidata.')
            calls=[]
            def run(argv,**kwargs):
                calls.append(argv)
                if argv[2]=='upload':raise subprocess.CalledProcessError(1,argv)
            def git(argv,**kwargs):return 'abc123' if kwargs.get('text') else b''
            with patch.object(publisher.subprocess,'run',side_effect=run), \
                 patch.object(publisher.subprocess,'check_output',side_effect=git), \
                 patch.object(publisher.shutil,'disk_usage',return_value=SimpleNamespace(free=10**12)), \
                 patch.object(publisher,'release_info',return_value={'channel':'rc','version':'1.0.0~rc2','display_version':'1.0.0 RC 2'}):
                with self.assertRaises(subprocess.CalledProcessError):
                    publisher.main(['--artifact',str(artifact),'--notes',str(notes),'--publish'])
            self.assertFalse(any(c[2]=='edit' for c in calls))


if __name__=='__main__':unittest.main()
