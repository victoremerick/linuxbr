import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import application_cache as cache


class CatalogTests(unittest.TestCase):
    def test_missing_menu_refuses_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                cache.catalog_environment({'XDG_CONFIG_DIRS': directory}, directory)

    def test_headless_environment_keeps_plasma_menu_and_flatpak_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            menu = Path(directory) / 'menus/plasma-applications.menu'
            menu.parent.mkdir(); menu.touch()
            source = {'XDG_CONFIG_DIRS': directory, 'XDG_DATA_DIRS': '/custom/share'}
            env = cache.catalog_environment(source, directory)
            self.assertEqual(env['XDG_MENU_PREFIX'], 'plasma-')
            self.assertEqual(env['XDG_DATA_DIRS'].split(':')[0], '/custom/share')
            self.assertIn(directory + '/.local/share/flatpak/exports/share', env['XDG_DATA_DIRS'])
            self.assertNotIn('XDG_MENU_PREFIX', source)

    def test_invalid_prefix_is_rejected(self):
        for prefix in ('', '../', '/tmp/'):
            with self.assertRaises(ValueError):
                cache.catalog_environment({'XDG_MENU_PREFIX': prefix})

    def test_root_cannot_rebuild_user_catalog(self):
        with patch.object(os, 'geteuid', return_value=0), patch.object(cache.subprocess, 'run') as run:
            self.assertEqual(cache.main([]), 1)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
