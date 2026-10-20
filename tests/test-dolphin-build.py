"""Build-cache orchestration only; never compiles or installs on the host."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Build(unittest.TestCase):
    def test_cache_and_explicit_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for d in ('scripts','packages/linuxbr-dolphin','bin','build'): (root/d).mkdir(parents=True)
            script=root/'scripts/build-dolphin.sh'
            script.write_text((ROOT/'scripts/build-dolphin.sh').read_text().replace('/src',str(root)))
            patch=root/'scripts/patch-dolphin.py'; patch.write_text('fixture patch')
            cards=root/'packages/linuxbr-dolphin/cards.cpp.inc';cards.write_text('fixture cards')
            sidebar=root/'packages/linuxbr-dolphin/sidebar.h'; sidebar.write_text('fixture sidebar')
            state=root/'packages/linuxbr-dolphin/sidebar-state.h'; state.write_text('fixture state')
            for name,body in [('apt-cache','echo "Version: 1.0"'),('apt-get','exit 17')]:
                p=root/'bin'/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
            key=hashlib.sha256(b'1.0\n'+patch.read_bytes()+cards.read_bytes()+sidebar.read_bytes()+state.read_bytes()+script.read_bytes()).hexdigest()
            cache=root/'.cache/dolphin-packages'/key;cache.mkdir(parents=True)
            (cache/'complete').touch();(cache/'dolphin_1.0_all.deb').write_bytes(b'test archive')
            env={**os.environ,'PATH':str(root/'bin')+':'+os.environ['PATH'],'LINUXBR_NO_CACHE':'0'}
            result=subprocess.run(['bash',str(script),str(root/'output')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((root/'output/dolphin_1.0_all.deb').read_bytes(),b'test archive')
            env['LINUXBR_NO_CACHE']='1'
            result=subprocess.run(['bash',str(script),str(root/'output2')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,17)
            self.assertFalse(list((root/'output2').glob('*.deb')))
if __name__=='__main__':unittest.main()
