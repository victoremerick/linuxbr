from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtGui import QColor, QImage

FILES = Path(__file__).resolve().parents[1] / 'packages/linuxbr-system/files'
sys.path.insert(0, str(FILES / 'usr/lib/linuxbr-system'))
import webapp_icons
import webapps_backend as backend
import webapps_backup as backup


class WebAppBackups(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        for mock in (patch('os.geteuid', return_value=1000),
                     patch.object(webapp_icons, 'request_refresh'),
                     patch.object(backend, 'CATALOG', FILES / 'usr/share/linuxbr/webapps/catalog.json')):
            mock.start()
            self.addCleanup(mock.stop)

    @contextmanager
    def session(self, name):
        location = self.directory / name
        with patch.dict(os.environ, {'XDG_DATA_HOME': str(location / 'share'),
                                     'XDG_CONFIG_HOME': str(location / 'config')}):
            yield

    def test_portable_profiles_preferences_and_favicon_without_browser_data(self):
        path = self.directory / 'atalhos.json'
        with self.session('origem'):
            app = dict(url='https://example.org/página-privada?token=senha#fragmento', name='Editor local')
            first = backend.install({**app, 'session': 'Pessoal'})
            second = backend.install({**app, 'session': 'Trabalho', 'new_session': True})
            backend.save_profile_options(second, session_start=True)
            backend.set_preferred_profile(second)
            for identifier in (first, second):
                profile = backend.record_path(identifier) / 'profile'
                profile.mkdir()
                (profile / 'Cookies').write_text('credencial-teste')
                (profile / 'Login Data').write_text('outra-credencial')
            icon = webapp_icons.cache_path(app['url'])
            icon.parent.mkdir(parents=True, exist_ok=True)
            png = QImage(48, 48, QImage.Format.Format_RGB32)
            png.fill(QColor('red'))
            png.setText('Comment', 'segredo-no-ícone')
            self.assertTrue(png.save(str(icon)))
            backend.export_shortcuts(path, include_profiles=True)
            document = path.read_text()
            for value in ('página-privada', 'senha', 'fragmento', 'credencial-teste', first, second):
                self.assertNotIn(value, document)

        with self.session('destino'):
            rows = backend.load_shortcuts(path)
            self.assertEqual([row['session'] for row in rows], ['Pessoal', 'Trabalho'])
            self.assertEqual({row['url'] for row in rows}, {'https://example.org/'})
            self.assertEqual(backup.restore(rows), (2, []))
            self.assertEqual(backup.restore(rows), (0, []))
            restored = {item['session']: item for item in backend.installed()}
            self.assertEqual(backend.preferred_profile('https://example.org/'), restored['Trabalho']['id'])
            for item in restored.values():
                self.assertEqual(item['name'], 'Editor local')
                self.assertFalse((backend.record_path(item['id']) / 'profile').exists())
                self.assertFalse(backend.session_start_enabled(item['id']))
            icon = QImage(str(webapp_icons.cache_path('https://example.org/')))
            self.assertEqual(icon.pixelColor(0, 0), QColor('red'))
            self.assertEqual(icon.textKeys(), [])

        with self.session('destino-com-inicialização'):
            rows = backend.load_shortcuts(path)
            self.assertEqual(backup.restore(rows, restore_startup=True), (2, []))
            saved = {item['session']: item['id'] for item in backend.installed()}
            self.assertFalse(backend.session_start_enabled(saved['Pessoal']))
            self.assertTrue(backend.session_start_enabled(saved['Trabalho']))

    def test_legacy_backups_and_existing_profiles_preserved(self):
        path = self.directory / 'v1.json'
        path.write_text(json.dumps(dict(schema='linuxbr-webapp-shortcuts-1',
                                        shortcuts=[dict(name='Antigo', url='https://example.org/')])))
        with self.session('destino'):
            rows = backend.load_shortcuts(path)
            self.assertEqual(backup.restore(rows), (1, []))
            identifier = backend.installed()[0]['id']
            backend.remove(identifier)
            self.assertEqual(backup.restore(rows), (0, []))
            self.assertEqual(backend.installed(), [])

    def test_rejects_invalid_profile_schema_and_credential_urls(self):
        path = self.directory / 'malformado.json'
        base = dict(url='https://example.org/', name='Editor', session='Principal',
                    options=dict(external_links='profile', session_start=False), preferred=False)
        with self.session('destino'):
            for invalid in ({**base, 'cookie': 'privado'}, {**base, 'url': 'https://user:passwd@example.org/'},
                            {**base, 'options': dict(external_links='profile', session_start='false')}):
                path.write_text(json.dumps(dict(schema=backup.SCHEMA, shortcuts=[invalid], icons={})))
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    backend.load_shortcuts(path)
            self.assertEqual(backend.installed(), [])


if __name__ == '__main__':
    unittest.main()
