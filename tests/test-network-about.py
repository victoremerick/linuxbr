#!/usr/bin/env python3
"""Offline regression coverage; no SMB account or host configuration is changed."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for package in ('linuxbr-system', 'linuxbr-drive-manager'):
    sys.path.insert(0, str(ROOT / 'packages' / package / 'files/usr/lib' / package))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication
import about
import network_access
import file_tools
from core import Store
APP = QApplication.instance() or QApplication([])


class NetworkAbout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def program(self, status=0, sleep=False):
        script = self.root / 'cliente com espaços'
        script.write_text('#!' + sys.executable + '\nimport json,sys,time\n'
                          + 'open(' + repr(str(self.root / 'args.json')) + ',"w").write(json.dumps(sys.argv[1:]))\n'
                          + ('time.sleep(60)\n' if sleep else '') + f'sys.exit({status})\n')
        script.chmod(0o700)
        return str(script)

    def test_first_connection_lists_share_interactively_and_rejects_url_credentials(self):
        connector = network_access.NetworkAccess()
        self.addCleanup(connector.cancel)
        results = []
        connector.finished.connect(lambda *value: results.append(value))
        with patch.object(network_access.shutil, 'which', return_value=self.program()):
            connector.start(r'\\SERVER\Equipe Brasil')
        self.assertTrue(connector.busy)
        process = connector.process
        self.assertTrue(process.waitForFinished(5000))
        self.assertEqual(json.loads((self.root / 'args.json').read_text()),
                         ['--interactive', 'ls', 'smb://server/Equipe%20Brasil'])
        self.assertEqual(results[0][:2], ('smb://server/Equipe%20Brasil', True))
        self.assertFalse(connector.busy)
        with self.assertRaises(ValueError): connector.start('smb://victor:senha@server/Equipe')

    def test_failure_preserves_mapping_and_does_not_call_it_offline(self):
        store = Store(self.root / 'drive-manager.json')
        before = store.add_share('smb://server/Equipe', 'Equipe')
        connector = network_access.NetworkAccess()
        results = []
        connector.finished.connect(lambda *value: results.append(value))
        with patch.object(network_access.shutil, 'which', return_value=self.program(1)):
            connector.start('smb://server/Equipe')
        connector.process.waitForFinished(5000)
        self.assertFalse(results[0][1])
        self.assertIn('conta e a permissão', results[0][2])
        self.assertEqual(store.update(), before)
        self.assertNotIn('senha', (self.root / 'drive-manager.json').read_text())

    def test_timeout_clears_busy_and_allows_retry(self):
        connector = network_access.NetworkAccess()
        results = []
        connector.finished.connect(lambda *value: results.append(value))
        with patch.object(network_access.shutil, 'which', return_value=self.program(sleep=True)):
            connector.start('smb://server/Equipe')
        process = connector.process
        self.assertTrue(process.waitForStarted(2000))
        connector.expire()
        process.waitForFinished(5000)
        self.assertFalse(connector.busy)
        self.assertIn('tempo de conexão', results[0][2])

    def test_cancel_does_not_emit_result(self):
        connector = network_access.NetworkAccess()
        results = []
        connector.finished.connect(lambda *value: results.append(value))
        with patch.object(network_access.shutil, 'which', return_value=self.program(sleep=True)):
            connector.start('smb://server/Equipe')
        process = connector.process
        self.assertTrue(process.waitForStarted(2000))
        connector.cancel()
        process.waitForFinished(5000)
        self.assertEqual(results, [])
        self.assertFalse(connector.busy)

    def test_missing_component_has_actionable_error(self):
        with patch.object(network_access.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'kde-cli-tools'):
                network_access.NetworkAccess().start('smb://server/Equipe')

    def test_saving_mapping_without_opening_does_not_connect(self):
        store = Store(self.root / 'drive-manager.json')
        with patch.object(file_tools, 'network_api', return_value=(lambda: store, network_access.smb_url)), \
             patch.object(file_tools, 'message'), patch.object(network_access.NetworkAccess, 'start') as start:
            dialog = file_tools.MapNetworkDialog()
            dialog.location.setText(r'\\server\Equipe')
            dialog.open_now.setChecked(False)
            dialog.map_share()
        start.assert_not_called()
        self.assertIn('smb://server/Equipe', store.update()['shares'])

    def test_release_reads_installed_metadata_and_corruption_falls_back(self):
        path = self.root / 'release.json'
        path.write_text(json.dumps({'display_version': '0.7.0 Beta 1', 'channel': 'beta'}))
        self.assertEqual(about.release_summary(path), ('0.7.0 Beta 1', 'beta'))
        path.write_text('[]')
        with patch.object(about.platform, 'freedesktop_os_release', return_value={'VERSION': '0.6.0 Beta 2'}):
            self.assertEqual(about.release_summary(path), ('0.6.0 Beta 2', ''))

    def test_notes_are_offline_and_reject_executable_links(self):
        path = self.root / 'README.md'; path.write_text('# Linux BR\n\n## 0.7\nNovidades verificadas.')
        dialog = about.ReleaseNotes(path=path)
        self.assertIn('Novidades verificadas', dialog.browser.toPlainText())
        with patch.object(about.QDesktopServices, 'openUrl') as opened:
            for value in ('file:///tmp/programa', 'action:execute', 'https://u:senha@example.org'):
                dialog.follow_link(QUrl(value))
            opened.assert_not_called()
            dialog.follow_link(QUrl('https://www.debian.org/'))
            opened.assert_called_once()
        dialog.close()

    def test_cancel_diagnostic_does_not_collect_or_write(self):
        with patch.object(about.QFileDialog, 'getSaveFileName', return_value=('', '')), \
             patch('welcome.support_report') as report:
            about.export_diagnostic(None)
            report.assert_not_called()

    def test_diagnostic_reuses_existing_report(self):
        path = self.root / 'diagnostico.txt'
        with patch.object(about.QFileDialog, 'getSaveFileName', return_value=(str(path), '')), \
             patch.object(about.QMessageBox, 'information'), \
             patch('welcome.support_report', return_value='Sistema: Linux BR\n') as report:
            about.export_diagnostic(None)
        report.assert_called_once_with()
        self.assertEqual(path.read_text(), 'Sistema: Linux BR\n')


if __name__ == '__main__': unittest.main()
