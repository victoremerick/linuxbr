#!/usr/bin/env python3
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / 'packages/linuxbr-system/files'
sys.path.insert(0, str(FILES / 'usr/lib/linuxbr-system'))
import store_backend as backend
import webapps_backend as web
from PyQt6.QtWidgets import QApplication
import store
APP = QApplication.instance() or QApplication([])


class StoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        for mocked in (patch.object(backend, 'CATALOG', FILES / 'usr/share/linuxbr/store/catalog.json'),
                       patch.object(web, 'CATALOG', FILES / 'usr/share/linuxbr/webapps/catalog.json'),
                       patch.dict(os.environ, {'XDG_DATA_HOME': tmp.name})):
            mocked.start(); self.addCleanup(mocked.stop)
        self.entries = backend.catalog()

    def test_catalog_and_search(self):
        self.assertEqual(len({item['id'] for item in self.entries}), len(self.entries))
        self.assertEqual(len(backend.search(self.entries, kind='web')), 7)
        self.assertEqual(backend.search(self.entries, 'planilhas')[0]['name'], 'LibreOffice')
        self.assertEqual(backend.search(self.entries, 'ilustracoes')[0]['name'], 'Inkscape')
        self.assertEqual(len(backend.search(self.entries, kind='windows')), 2)
        for item in self.entries: self.assertTrue(web.clean_url(item['source']).startswith('https://'))

    def test_actions_preserve_confirmation(self):
        for item in self.entries:
            argv = backend.action(item)
            self.assertIn(argv[0], ('linuxbr-store', 'linuxbr-webapps', 'xdg-open'))
            if item['kind'] == 'web': self.assertEqual(argv[1], '--offer')
            if item['kind'] == 'windows': self.assertEqual(argv[0], 'xdg-open')
        with self.assertRaises(ValueError): backend.action({'kind': 'windows', 'source': 'file:///tmp/installer'})

    def test_installed_webapp_opens_without_reinstall(self):
        with patch('os.geteuid', return_value=1000):
            identifier = web.install({'name': 'WhatsApp', 'url': 'https://web.whatsapp.com/'})
        with patch('webapp_icons.request_refresh'), patch('store.subprocess.Popen') as launch:
            window = store.Window(); window.query.setText('WhatsApp')
            self.assertEqual(window.primary.text(), 'Abrir aplicativo web')
            window.activate()
            self.assertEqual(launch.call_args.args[0], ['linuxbr-webapps', '--open-site', 'https://web.whatsapp.com/'])
            web.remove(identifier); window.select()
            self.assertEqual(window.primary.text(), 'Instalar aplicativo web…')
            window.close()

    def test_gui_filters_and_empty_state(self):
        with patch('webapp_icons.request_refresh'), patch('store.subprocess.Popen') as launch:
            window = store.Window()
            self.assertEqual(window.results.count(), len(self.entries)); launch.assert_not_called()
            window.query.setText('nada-encontrado'); self.assertEqual(window.results.count(), 0)
            self.assertTrue(window.primary.isHidden())
            window.discover(); self.assertEqual(launch.call_args.args[0], ['linuxbr-store', '--search', 'nada-encontrado'])
            window.query.clear(); window.kind.setCurrentIndex(window.kind.findData('windows'))
            self.assertEqual(window.results.count(), 2)
            window.activate(); self.assertEqual(launch.call_args.args[0][0], 'xdg-open')
            window.kind.setCurrentIndex(window.kind.findData('web')); window.activate()
            self.assertEqual(launch.call_args.args[0][:2], ['linuxbr-webapps', '--offer'])
            self.assertEqual(web.installed(), [])
            window.close()

if __name__ == '__main__': unittest.main()
