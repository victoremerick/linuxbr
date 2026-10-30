#!/usr/bin/env python3
"""Exercise onboarding state, offline actions and support export without host changes."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
import welcome

APP = QApplication([])


class WelcomeTests(unittest.TestCase):
    def test_service_shortcuts_use_plasma6_format(self):
        # Plasma 6 service actions store only the keys, unlike dynamic actions
        # which still use shortcut/default/friendly-name triplets.
        config = ROOT / 'packages/linuxbr-desktop/files/etc/skel/.config/kglobalshortcutsrc'
        count = 0
        for line in config.read_text().splitlines():
            if not line.startswith('_launch='):
                continue
            keys = line.partition('=')[2]
            self.assertNotIn(',', keys)
            for sequence in keys.replace('\\t', '\t').split('\t'):
                shortcut = QKeySequence.fromString(sequence, QKeySequence.SequenceFormat.PortableText)
                self.assertFalse(shortcut.isEmpty())
                self.assertEqual(shortcut.count(), 1)
            count += 1
        self.assertEqual(count, 5)

    def test_first_login_and_explicit_opt_in(self):
        self.assertTrue(welcome.should_autostart({}))
        self.assertFalse(welcome.should_autostart({'seen': True}))
        self.assertTrue(welcome.should_autostart({'seen': True, 'show_on_login': True}))
        self.assertFalse(welcome.should_autostart({'seen': True, 'show_on_login': 'false'}))

    def test_preferences_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nested/welcome.json'
            self.assertEqual(welcome.load_preferences(path), {})
            welcome.save_preferences(False, path)
            self.assertFalse(welcome.should_autostart(welcome.load_preferences(path)))
            welcome.save_preferences(True, path)
            self.assertTrue(welcome.should_autostart(welcome.load_preferences(path)))
            for value in ('not json', '[]', 'null'):
                path.write_text(value)
                self.assertEqual(welcome.load_preferences(path), {})

    def test_only_known_local_actions_execute(self):
        calls = []
        page = welcome.HelpPage(calls.append)
        page.follow_link(QUrl('https://example.invalid'))
        page.follow_link(QUrl('file:///etc/passwd'))
        page.follow_link(QUrl('action:not-an-action'))
        self.assertEqual(calls, [])
        page.follow_link(QUrl('action:network'))
        self.assertEqual(calls, [['linuxbr-system', '--page', 'Rede']])
        for document in welcome.TOPICS.values():
            for action in re.findall(r'href="action:([^"]+)"', document):
                self.assertIn(action, welcome.ACTIONS)

    def test_report_export_and_cancel(self):
        page = welcome.HelpPage(lambda command: None, 'Recuperação e ajuda')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'relatório.txt'
            with patch.object(welcome.QFileDialog, 'getSaveFileName', return_value=(str(path), '')), \
                 patch.object(welcome.QMessageBox, 'information'):
                page.export_report()
            text = path.read_text()
            self.assertIn('Kernel:', text)
            self.assertIn('Espaço livre da pasta pessoal:', text)
            self.assertNotIn(str(Path.home()), text)
            with patch.object(welcome.QFileDialog, 'getSaveFileName', return_value=('', '')), \
                 patch.object(welcome, 'support_report') as report:
                page.export_report()
                report.assert_not_called()

    def test_topics_and_small_screen(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            window = welcome.Welcome()
            window.resize(800, 600)
            window.show(); APP.processEvents()
            for row, title in enumerate(welcome.TOPICS):
                window.nav.setCurrentRow(row); APP.processEvents()
                self.assertTrue(window.page.browser.toPlainText().strip())
                self.assertEqual(window.nav.currentItem().text(), title)
            window.nav.setCurrentRow(0); APP.processEvents()
            preview = os.environ.get('WELCOME_PREVIEW', '/tmp/linuxbr-welcome.png')
            self.assertTrue(window.grab().save(preview))
            window.show_on_login.setChecked(False)
            window.close()
            self.assertFalse(welcome.should_autostart(welcome.load_preferences()))

    def test_live_installer_only_offered_in_live_session(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            with patch.object(welcome, 'is_live_session', return_value=False):
                installed = welcome.Welcome()
                self.assertIsNone(installed.live_install)
                installed.close()
            with patch.object(welcome, 'is_live_session', return_value=True):
                live = welcome.Welcome()
                with patch.object(live, 'launch') as launch:
                    live.live_install.click()
                    launch.assert_called_once_with(['calamares-install-linuxbr'])
                live.close()


if __name__ == '__main__':
    unittest.main()
