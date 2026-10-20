import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
import capacity

class Capacity(unittest.TestCase):
    def test_reserved_space_is_not_reported_as_used(self):
        with patch('capacity.os.statvfs',return_value=SimpleNamespace(f_blocks=100,f_bfree=30,f_bavail=20,f_frsize=4096)):
            self.assertEqual(capacity.measure('/test'),dict(total=409600,used=286720,free=81920,reserved=40960))
    def test_invalid_statistics(self):
        with patch('capacity.os.statvfs',return_value=SimpleNamespace(f_blocks=0,f_bfree=0,f_bavail=0,f_frsize=4096)):
            with self.assertRaises(ValueError):capacity.measure('/test')
    def test_offline_and_network_do_not_probe(self):
        with patch('capacity.subprocess.run') as run:
            self.assertIsNone(capacity.query(dict(mounts=[])))
            self.assertIsNone(capacity.query(dict(mounts=['/network'],url='smb://server/share')))
            run.assert_not_called()
    def test_failed_probe_keeps_inventory(self):
        rows=[dict(key='system',mounts=['/'])]
        with patch('capacity.subprocess.run',side_effect=OSError('removed')):
            self.assertIs(capacity.enrich(rows),rows)
            self.assertIsNone(rows[0]['usage'])
    def test_timeout_does_not_invent_empty_space(self):
        import subprocess
        with patch('capacity.subprocess.run',side_effect=subprocess.TimeoutExpired('statvfs',2)):
            self.assertIsNone(capacity.query(dict(mounts=['/slow'])))

    def test_dolphin_icon_set(self):
        import importlib.util
        import tempfile
        import xml.etree.ElementTree as ET
        path=Path(__file__).resolve().parents[1]/'scripts/generate-drive-capacity-icons.py'
        spec=importlib.util.spec_from_file_location('icons',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);module.generate(root)
            self.assertEqual(len(list(root.glob('*.svg'))),202)
            for percent in (0,50,100):
                tree=ET.parse(root/f'disk-{percent:03d}.svg')
                fill=tree.findall('./{http://www.w3.org/2000/svg}rect')[-1]
                self.assertEqual(float(fill.get('width')),116*percent/100)
            self.assertIn('#c74b50',(root/'disk-095.svg').read_text())

    def test_real_query(self):
        usage=capacity.query(dict(mounts=['/']))
        self.assertGreater(usage['total'],0)
        self.assertEqual(usage['used']+usage['free']+usage['reserved'],usage['total'])

if __name__=='__main__': unittest.main()
