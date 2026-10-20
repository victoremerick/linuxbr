#!/usr/bin/python3
"""Regression tests without changing the host settings or installing packages."""
from pathlib import Path
import os,sys,tempfile,subprocess,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication
from installer import inspect_package,Installer
from proxy import validate_url
from appearance import Appearance
APP=QApplication([])
class Settings(unittest.TestCase):
 def test_invalid_proxy(self):
  for text in ('file:///tmp/x','http://user:password@proxy:8080','http://proxy:99999','http://host\nother'):
   with self.assertRaises(ValueError):validate_url(text,('http','https'))
  self.assertEqual(validate_url('http://proxy.example:8080',('http','https')),'http://proxy.example:8080')
 def test_packages(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);invalid=root/'bad.deb';invalid.write_text('no package')
   with self.assertRaises(ValueError):inspect_package(invalid)
   rpm=root/'foreign.rpm';rpm.write_text('not executable')
   self.assertFalse(inspect_package(rpm)[1])
   window=Installer(str(rpm));self.assertFalse(window.install.isEnabled())
   package=root/'package';(package/'DEBIAN').mkdir(parents=True)
   (package/'DEBIAN/control').write_text('Package: linuxbr-test-fixture\nVersion: 1\nArchitecture: all\nMaintainer: Test <test@example.invalid>\nDescription: Disposable metadata-only test\n')
   file=root/'name with spaces.deb'
   subprocess.run(['dpkg-deb','--build',str(package),str(file)],check=True,stdout=subprocess.DEVNULL)
   self.assertTrue(inspect_package(file)[1]);window.load(str(file));self.assertTrue(window.install.isEnabled())
   with patch('installer.QProcess.startDetached',return_value=(True,1)) as start:
    window.start();self.assertEqual(start.call_args.args,('plasma-discover',['--local-filename',str(file)]))
 def test_appearance_restricted(self):
  with patch('appearance.subprocess.check_output',return_value='LinuxBRDarkBlue\n'):
   page=Appearance()
  self.assertEqual(page.mode.currentData(),'Dark');self.assertEqual(page.accent.currentData(),'Blue')
  self.assertEqual(page.mode.count(),2);self.assertEqual(page.accent.count(),4)
  self.assertTrue(page.preview.dark)
  page.mode.setCurrentIndex(0);self.assertFalse(page.preview.dark)
  page.accent.setCurrentIndex(2);self.assertEqual(page.preview.accent,'#147050')
 def test_decoration_assets(self):
  import xml.etree.ElementTree as ET
  root=ROOT/'packages/linuxbr-desktop/files/usr/share/aurorae/themes'
  for theme in root.iterdir():
   for name in ('close','maximize','minimize','restore'):
    ids={e.get('id') for e in ET.parse(theme/(name+'.svg')).iter()}
    self.assertTrue({'active-center','hover-center','pressed-center'} <= ids)
if __name__=='__main__':unittest.main()
