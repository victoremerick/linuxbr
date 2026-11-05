#!/usr/bin/env python3
"""Basic video login stays temporary and does not restrict ordinary services."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-boot-tools/files/usr/lib/linuxbr-boot'))
import basic_video
import boot_policy


class BasicVideo(unittest.TestCase):
    def test_exact_explicit_selection(self):
        self.assertTrue(basic_video.selected('quiet nomodeset linuxbr.video=basic'))
        for text in ('nomodeset','linuxbr.video=basic-extra','linuxbr.mode=safe','quiet'):
            self.assertFalse(basic_video.selected(text))

    def test_framebuffer_login_requires_authentication_and_software_x11(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fb=root/'fb0';fb.touch();runtime=root/'runtime'
            self.assertEqual(basic_video.prepare(runtime,fb,drm=root/'absent'), 'fbdev')
            self.assertIn('Driver "fbdev"',(runtime/'xorg.conf').read_text())
            session=(runtime/'sessions/linuxbr-basic.desktop').read_text()
            self.assertIn('LIBGL_ALWAYS_SOFTWARE=1',session)
            self.assertIn('KWIN_COMPOSE=N /usr/bin/startplasma-x11',session)
            login=(runtime/'sddm.conf').read_text()
            self.assertIn('[Autologin]\nUser=\nSession=\nRelogin=false',login)
            self.assertIn('RememberLastSession=false',login)
            self.assertEqual(list((runtime/'empty-wayland').iterdir()),[])

    def test_server_keeps_its_own_console(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(basic_video.prepare(root,root/'absent',server=True),'modesetting')
            self.assertIn('AccelMethod" "none',(root/'xorg.conf').read_text())
            text=(root/'sessions/linuxbr-basic.desktop').read_text()
            self.assertIn('/usr/bin/linuxbr-minimal-session',text)
            self.assertNotIn('startplasma',text)

    def test_generic_drm_uses_no_acceleration_even_with_a_framebuffer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fb=root/'fb0';fb.touch();drm=root/'dri';drm.mkdir()
            self.assertEqual(basic_video.prepare(root/'runtime',fb,drm=drm),'modesetting')
            self.assertIn('AccelMethod" "none',(root/'runtime/xorg.conf').read_text())

    def test_generator_does_not_mask_services_or_user_autostart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=[root/name for name in ('normal','early','late')]
            self.assertEqual(boot_policy.generate(*args,commandline='linuxbr.video=basic'),[])
            drop=args[1]/'sddm.service.d/90-linuxbr-basic-video.conf'
            self.assertIn('BindReadOnlyPaths=/run/linuxbr-basic/sddm.conf:/etc/sddm.conf',drop.read_text())
            self.assertFalse(any(p.is_symlink() for p in root.rglob('*')))
            self.assertEqual(boot_policy.generate(*args,user=True,commandline='linuxbr.video=basic'),[])

    def test_restricted_mode_takes_priority(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=[root/name for name in ('normal','early','late')]
            boot_policy.generate(*args,commandline='linuxbr.mode=safe linuxbr.video=basic',search_paths=[])
            self.assertTrue((args[1]/'sddm.service.d/90-linuxbr-safe.conf').is_file())
            self.assertFalse((args[1]/'sddm.service.d/90-linuxbr-basic-video.conf').exists())


if __name__=='__main__':unittest.main(verbosity=2)
