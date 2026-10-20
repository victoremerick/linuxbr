#!/usr/bin/env python3
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-device-manager/files/usr/lib/linuxbr-device-manager'))
import proprietary as p
import firmware_admin as admin

CARD=dict(id='pci:0000:01:00.0',name='GPU teste',bus='PCI',category='Vídeo',hardware_id='0x10de:0x2684')
class Nvidia(unittest.TestCase):
    def runner(self,args,**kwargs):
        if args[0]=='/usr/bin/nvidia-detect':return 0,'It is recommended to install the\n    nvidia-driver\npackage.',''
        if args[0]=='dpkg-query':return (0,'installed 550.1','') if args[-1]=='nvidia-detect' else (1,'','')
        if args[0]=='apt-cache':return 0,' Candidate: 550.1\n',''
        return 1,'',''
    def ready(self,runner):return ['linux-headers-test','linux-headers-amd64','dkms'],''
    def test_supported_and_non_gpu(self):
        option=p.nvidia_options([CARD],self.runner,self.ready)[0]
        self.assertEqual(option['action'],'install');self.assertEqual(option['package'],'nvidia-driver')
        self.assertEqual(p.nvidia_options([{**CARD,'category':'Áudio e multimídia'}],self.runner,self.ready),[])
    def test_unknown_and_multiple_conflicting_cards(self):
        def runner(args):
            if args[0]=='/usr/bin/nvidia-detect' and args[1]=='10de:0000':return 1,'not supported',''
            return self.runner(args)
        options=p.nvidia_options([CARD,{**CARD,'id':'pci:other','hardware_id':'0x10de:0x0000'}],runner,self.ready)
        self.assertTrue(all(not r['action'] for r in options))
        def conflict(args):
            if args[0]=='/usr/bin/nvidia-detect' and args[1]=='10de:0000':return 0,'It is recommended to install the\n nvidia-tesla-535-driver\npackage.',''
            return self.runner(args)
        self.assertTrue(all(not r['action'] for r in p.nvidia_options([CARD,{**CARD,'hardware_id':'0x10de:0x0000'}],conflict,self.ready)))
    def test_no_legacy_or_arbitrary_package(self):
        for text in ('nvidia-legacy-390xx-driver','bash','nvidia-driver/unstable'):
            def runner(args):
                return (0,'It is recommended to install the\n '+text+'\npackage.','') if args[0]=='/usr/bin/nvidia-detect' else self.runner(args)
            self.assertFalse(p.nvidia_options([CARD],runner,self.ready)[0]['action'])
    def test_detector_must_match_candidate(self):
        def runner(args):
            if args[0]=='apt-cache':return 0,' Candidate: 555.1\n',''
            if args[0]=='dpkg':return 0,'',''
            return self.runner(args)
        rows=p.nvidia_options([CARD],runner,self.ready)
        self.assertFalse(rows[0]['action'])
        self.assertEqual(rows[1]['package'],'nvidia-detect');self.assertEqual(rows[1]['action'],'upgrade')
    def test_secure_boot_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            efi=Path(tmp)/'efi';key=Path(tmp)/'mok.pub'
            self.assertEqual(p.secure_boot_ready(self.runner,efi,key),'')
            efi.mkdir()
            self.assertTrue(p.secure_boot_ready(self.runner,efi,key))
            enabled=lambda args:(0,'SecureBoot enabled','')
            self.assertIn('cadastre',p.secure_boot_ready(enabled,efi,key))
            key.touch();self.assertEqual(p.secure_boot_ready(enabled,efi,key),'')
            self.assertEqual(p.secure_boot_ready(lambda args:(0,'SecureBoot disabled',''),efi,key),'')
    def test_live_and_missing_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('Live',p.prerequisites(self.runner,live=Path(tmp))[1])
            with patch('proprietary.platform.machine',return_value='x86_64'):
                _,reason=p.prerequisites(lambda args:(1,'',''),release='6.12-test',live=Path(tmp)/'absent')
                self.assertIn('Headers',reason)
    def test_root_rechecks_before_apt(self):
        with patch.dict(os.environ,dict(os.environ)),patch('firmware_admin.os.geteuid',return_value=0),patch('firmware_admin.Path.read_text',return_value='ID=linuxbr\n'),patch('firmware_admin.discover',return_value=([CARD],[])),patch('firmware_admin.nvidia_options',return_value=[]),patch('firmware_admin.subprocess.call') as apt:
            with self.assertRaises(ValueError):admin.main(['nvidia-driver'])
            apt.assert_not_called()
        option=dict(package='nvidia-driver',action='install',prerequisites=['linux-headers-test','linux-headers-amd64','dkms'])
        with patch.dict(os.environ,dict(os.environ)),patch('firmware_admin.os.geteuid',return_value=0),patch('firmware_admin.Path.read_text',return_value='ID=linuxbr\n'),patch('firmware_admin.discover',return_value=([CARD],[])),patch('firmware_admin.nvidia_options',return_value=[option]),patch('firmware_admin.subprocess.call',return_value=0) as apt:
            self.assertEqual(admin.main(['nvidia-driver']),0)
            self.assertEqual(apt.call_args.args[0][-3:],option['prerequisites'])

if __name__=='__main__':unittest.main()
