import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-boot-tools/files/usr/lib/linuxbr-boot'))
import boot_policy as policy
import grub_modes as grub
import boot_backend as backend

STANZA="""menuentry 'Linux BR' --id=original {
 insmod ext2
 search --no-floppy --fs-uuid --set=root 1234-abcd
 linux /vmlinuz root=UUID=1234-abcd ro quiet $vt_handoff
 initrd /initrd.img
}
"""


class BootTests(unittest.TestCase):
    def test_normal_mode_does_not_change_units(self):
        self.assertIsNone(policy.mode('root=UUID=abc quiet'))
        self.assertEqual(policy.generate('a','b','c',commandline='quiet'),[])

    def test_mode_restrictions(self):
        for mode in policy.MODES:
            for unit in ['sshd.service','smbd.service','libvirtd.service','libvirtd.socket','cron.service','backup.timer','custom.path']:
                self.assertFalse(policy.allowed(unit,mode),(unit,mode))
            for unit in ['polkit.service','firewalld.service','systemd-cryptsetup@root.service','systemd-logind.service']:
                self.assertTrue(policy.allowed(unit,mode),(unit,mode))
            self.assertEqual(policy.allowed('NetworkManager.service',mode),mode=='safe-network')
            self.assertFalse(policy.allowed('sddm.service','safe-terminal'))
            self.assertFalse(policy.allowed('plasma-plasmashell.service',mode,user=True))
            self.assertTrue(policy.allowed('systemd-exit.service',mode,user=True))

    def test_server_session_keeps_network_and_optional_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.assertTrue(policy.server_edition('linuxbr.edition=server',root/'missing'))
            self.assertFalse(policy.server_edition('linuxbr.edition=desktop',root/'missing'))
            config=root/'edition';config.write_text('server\n')
            self.assertTrue(policy.server_edition('',config))
            self.assertFalse(policy.server_edition('linuxbr.edition=desktop',config))
            output=root/'early'
            self.assertEqual(policy.generate(root/'normal',output,root/'late',commandline='linuxbr.edition=server'),[])
            self.assertIn('linuxbr-safe-prepare.service',(output/'sddm.service.d/90-linuxbr-safe.conf').read_text())
            self.assertFalse((output/'NetworkManager.service').exists())
            self.assertFalse((output/'libvirtd.socket').exists())

    def test_generator_masks_socket_timer_and_user_autostart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);units=root/'units';units.mkdir()
            for name in ['custom.service','custom.socket','custom.timer','custom.path','dbus.service']:(units/name).touch()
            output=root/'out'
            for _ in range(2):policy.generate(root/'normal',output,root/'late',user=True,commandline='linuxbr.mode=safe',search_paths=[units])
            for name in ['custom.service','custom.socket','custom.timer','custom.path','xdg-desktop-autostart.target']:
                self.assertEqual((output/name).readlink(),Path('/dev/null'))
            self.assertFalse((output/'dbus.service').is_symlink())

    def test_terminal_requires_authenticated_getty_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            policy.generate(root/'normal',root/'early',root/'late',commandline='linuxbr.mode=safe-terminal',search_paths=[])
            wants=root/'early/linuxbr-safe.target.wants'
            self.assertEqual((wants/'getty@tty1.service').readlink(),Path('/usr/lib/systemd/system/getty@.service'))
            self.assertFalse((wants/'sddm.service').exists())
            self.assertEqual((wants/'plymouth-quit.service').readlink(),Path('/usr/lib/systemd/system/plymouth-quit.service'))

    def test_menu_preserves_root_and_initrd(self):
        rendered=grub.render(STANZA)
        self.assertEqual(rendered.count('root=UUID=1234-abcd'),len(grub.MODES))
        self.assertEqual(rendered.count('initrd /initrd.img'),len(grub.MODES))
        self.assertIn('--hotkey=f8',rendered)
        self.assertIn('linuxbr.mode=safe-network systemd.unit=linuxbr-safe.target',rendered)
        self.assertIn('module_blacklist=amdgpu,radeon,nouveau,nvidia,nvidia_drm,nvidia_modeset,i915,xe linuxbr.video=basic',rendered)

    def test_unsupported_menu_and_mode_are_rejected(self):
        for text in ['',STANZA.replace('root=UUID=1234-abcd',''),STANZA.replace(' initrd /initrd.img','')]:
            with self.assertRaises(ValueError):grub.render(text)
        with self.assertRaises(ValueError):backend.entry('safe; reboot')

    def test_boot_config_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);config=root/'config';menu=root/'menu';menu.write_text('original menu')
            original='GRUB_TIMEOUT=5\n';config.write_text(original)
            state=dict(available=True,live=False,next='',config_sha256=hashlib.sha256(original.encode()).hexdigest())
            with patch.object(backend,'CONFIG',config),patch.object(backend,'MENU',menu),patch.object(backend,'STATE',root/'state'),patch.object(backend.os,'geteuid',return_value=0),patch.object(backend,'state',return_value=state),patch.object(backend,'run',side_effect=RuntimeError('update failed')):
                with self.assertRaises(RuntimeError):backend.configure(dict(action='persistent',mode='safe',timeout=8,expected_sha256=state['config_sha256']))
                self.assertEqual(config.read_text(),original)
                self.assertEqual(menu.read_text(),'original menu')

    def test_one_boot_preserves_other_system_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(backend,'STATE',Path(temporary)),patch.object(backend.os,'geteuid',return_value=0),patch.object(backend,'state',return_value=dict(available=True,live=False,next='other-system')),patch.object(backend,'run') as run:
                with self.assertRaises(ValueError):backend.configure(dict(action='once',mode='safe'))
                run.assert_not_called()


if __name__=='__main__':unittest.main()
