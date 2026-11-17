from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOOK=ROOT/'config/hooks/live/0310-linuxbr-live-editions.hook.binary'


class LiveEditions(unittest.TestCase):
    def test_desktop_boot_menu(self):
        self.check_boot_menu('desktop')

    def test_vm_server_boot_menu(self):
        self.check_boot_menu('vm-server')

    def check_boot_menu(self, edition):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);grub=root/'boot/grub/grub.cfg';bios=root/'isolinux/live.cfg'
            grub.parent.mkdir(parents=True);bios.parent.mkdir()
            original='menuentry "Iniciar Linux BR" --hotkey=l {\n linux /live/vmlinuz boot=live components findiso=${iso_path}\n initrd /live/initrd.img\n}\n'
            legacy='label live-amd64\n menu label ^Iniciar Linux BR\n menu default\n linux /live/vmlinuz\n initrd /live/initrd.img\n append boot=live components\n'
            expected_grub, expected_bios = original, legacy
            if edition == 'vm-server':
                original = original.replace('boot=live components', 'boot=live components linuxbr.edition=virtualization')
                legacy = legacy.replace('boot=live components', 'boot=live components linuxbr.edition=virtualization')
                expected_grub = original.replace('Iniciar Linux BR', 'Iniciar Linux BR VM Server')
                expected_bios = legacy.replace('Iniciar Linux BR', 'Iniciar Linux BR VM Server')
            grub.write_text(original);bios.write_text(legacy)
            for _ in range(2):
                subprocess.run(['sh',str(HOOK)],cwd=root,check=True,capture_output=True,
                               env={**os.environ, 'LINUXBR_BUILD_EDITION': edition})
            self.assertTrue(grub.read_text().startswith(expected_grub))
            self.assertTrue(bios.read_text().startswith(expected_bios))
            for path in [grub,bios]:
                text=path.read_text()
                self.assertNotIn('linuxbr.edition=server',text)
                self.assertNotIn('linuxbr-live-virtualization',text)
                self.assertEqual('linuxbr.edition=virtualization' in text, edition == 'vm-server')
                self.assertEqual(text.count('linuxbr.mode=recovery systemd.unit=linuxbr-safe.target'),1)
                self.assertEqual(text.count('linuxbr.mode=safe-terminal systemd.unit=linuxbr-safe.target'),1)
                self.assertNotIn('autologin=',text)
            self.assertEqual(bios.read_text().count('menu default'),1)
            self.assertIn('--hotkey=f8',grub.read_text())


if __name__=='__main__':unittest.main()
