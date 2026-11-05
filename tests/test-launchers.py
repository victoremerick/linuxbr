#!/usr/bin/env python3
"""Exercise launchers with stub QEMU/firmware; never starts a VM."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
class Launchers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.bin = self.dir / 'bin'; self.bin.mkdir()
        self.log = self.dir / 'args.json'
        self.iso = self.dir / 'test.iso'; self.iso.write_bytes(b'iso fixture')
        self.disk = self.dir / 'nested/disk.qcow2'
        self.code = self.dir / 'OVMF_CODE.fd'; self.code.write_bytes(b'code')
        self.vars = self.dir / 'OVMF_VARS.fd'; self.vars.write_bytes(b'vars')
        for name, body in {
            'qemu-system-x86_64': 'import os,json,sys\nopen(os.environ["CAPTURE"],"w").write(json.dumps(sys.argv[1:]))',
            'qemu-img': 'import sys\nopen(sys.argv[-2],"wb").write(b"qcow2 fixture")',
            'xorriso': 'print("El Torito boot img : 1 BIOS")\nprint("El Torito boot img : 2 UEFI")',
        }.items():
            p = self.bin / name; p.write_text('#!/usr/bin/env python3\n' + body + '\n');p.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin)+':'+os.environ['PATH'],
                    'ISO': str(self.iso), 'DISK_IMAGE': str(self.disk), 'CAPTURE': str(self.log),
                    'OVMF_CODE': str(self.code), 'OVMF_VARS_TEMPLATE': str(self.vars)}
        for key in ['OVMF_VARS', 'CHECKSUM_FILE']:
            self.env.pop(key, None)

    def run_script(self, script, *args, success=True):
        result = subprocess.run(['bash', str(ROOT / 'tests' / script), *args], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(self.log.read_text()) if self.log.exists() else []

    def test_bios_creates_parent_and_attaches_iso(self):
        args = self.run_script('test-iso.sh','bios')
        self.assertTrue(self.disk.exists()); self.assertIn('-cdrom',args)
        self.assertFalse(any('pflash' in arg for arg in args))

    def test_uefi_vars_persist_and_installed_omits_iso(self):
        args = self.run_script('test-iso.sh','uefi')
        nvram = self.disk.with_suffix('.vars.fd')
        self.assertEqual(nvram.read_bytes(), b'vars')
        nvram.write_bytes(b'installed state')
        args = self.run_script('test-iso.sh','uefi','installed')
        self.assertNotIn('-cdrom',args)
        self.assertEqual(nvram.read_bytes(),b'installed state')
        self.assertEqual(self.vars.read_bytes(),b'vars')

    def test_invalid_mode_has_no_side_effects(self):
        self.run_script('test-iso.sh','wrong',success=False)
        self.assertFalse(self.disk.exists())

    def test_installed_requires_existing_disk(self):
        self.run_script('test-iso.sh','bios','installed',success=False)
        self.assertFalse(self.disk.exists())

    def test_missing_firmware_creates_no_disk(self):
        self.code.unlink()
        self.run_script('test-iso.sh','uefi',success=False)
        self.assertFalse(self.disk.exists())

    def test_checksum_targets_selected_iso(self):
        import hashlib
        checksum = self.iso.with_suffix('.iso.sha256')
        checksum.write_text(hashlib.sha256(self.iso.read_bytes()).hexdigest()+'  '+self.iso.name+'\n')
        self.run_script('verify-iso.sh')
        self.iso.write_bytes(b'corrupt')
        self.run_script('verify-iso.sh',success=False)

    def test_checksum_rejects_other_version(self):
        self.iso.with_suffix('.iso.sha256').write_text('0'*64+'  other.iso\n')
        self.run_script('verify-iso.sh',success=False)

if __name__ == '__main__': unittest.main()
