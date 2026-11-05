#!/usr/bin/env python3
"""Translate generated labels while preserving kernel commands and boot IDs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'config/hooks/live/0300-linuxbr-boot-language.hook.binary'


class BootLanguage(unittest.TestCase):
    def test_generated_bios_and_uefi_entries_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                'isolinux/live.cfg': 'label live-amd64\n menu label ^Live system (amd64)\n linux /live/vmlinuz\n append boot=live components locales=pt_BR.UTF-8\nlabel live-amd64-failsafe\n menu label Live system (amd64 fail-safe mode)\n',
                'isolinux/stdmenu.cfg': 'menu tabmsg Press ENTER to boot or TAB to edit a menu entry\n',
                'boot/grub/grub.cfg': 'menuentry "Live system (amd64)" {\n linux /live/vmlinuz boot=live\n initrd /live/initrd.img\n}\nsubmenu \'Utilities...\' --hotkey=u {\n menuentry "UEFI Firmware Settings" { fwsetup; }\n}\n',
            }
            for name, data in paths.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            subprocess.run(['sh', str(HOOK)], cwd=root, check=True, capture_output=True)
            once = {name: (root / name).read_text() for name in paths}
            self.assertIn('^Iniciar Linux BR (amd64)', once['isolinux/live.cfg'])
            self.assertIn('modo de compatibilidade', once['isolinux/live.cfg'])
            self.assertIn('Ferramentas...', once['boot/grub/grub.cfg'])
            self.assertIn('ENTER para iniciar', once['isolinux/stdmenu.cfg'])
            for name, original in paths.items():
                for line in original.splitlines():
                    if line.lstrip().startswith(('linux ', 'append ', 'initrd ', 'label ')):
                        self.assertIn(line, once[name])
            subprocess.run(['sh', str(HOOK)], cwd=root, check=True, capture_output=True)
            self.assertEqual(once, {name: (root / name).read_text() for name in paths})


if __name__ == '__main__':
    unittest.main()
