import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import windows_bottles as window


class WindowTests(unittest.TestCase):
    def test_host_window_profile_keeps_arguments_separate(self):
        name = 'Microsoft Word $(touch arquivo)'
        args = window.command(window.APP_IDS[0], 'Meu ambiente', name)
        self.assertIn('--socket=x11', args)
        self.assertIn('--nosocket=wayland', args)
        self.assertIn('--env=XDG_SESSION_TYPE=x11', args)
        self.assertEqual(args[-5:], ['run', '-b', 'Meu ambiente', '-p', name])

    def test_prepare_only_selected_bottle(self):
        args = window.command(window.APP_IDS[1], 'Office', prepare=True)
        self.assertEqual(args[-5:], ['edit', '-b', 'Office', '--params', 'virtual_desktop:false'])
        self.assertNotIn('override', args)
        self.assertNotIn('stop', args)

    def test_invalid_input(self):
        for app, bottle, program in [('other.app', 'Office', 'Word'),
                                     (window.APP_IDS[0], 'bad\nname', 'Word'),
                                     (window.APP_IDS[0], 'Office', None)]:
            with self.assertRaises(ValueError):
                window.command(app, bottle, program)

    def test_root_and_missing_display_do_not_launch(self):
        for uid, display in [(0, ':1'), (1000, '')]:
            with patch.object(os, 'geteuid', return_value=uid), \
                 patch.dict(os.environ, {'DISPLAY': display}), \
                 patch.object(window.subprocess, 'run') as run:
                self.assertEqual(window.main(['--bottle', 'Office', '--program', 'Word']), 1)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
