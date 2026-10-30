#!/usr/bin/env python3
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
import webapps_backend as backend
import webapps_host as host

class WebApps(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,{'XDG_DATA_HOME':self.tmp.name});self.env.start();self.addCleanup(self.env.stop)
        self.cat=patch.object(backend,'CATALOG',FILES/'usr/share/linuxbr/webapps/catalog.json');self.cat.start();self.addCleanup(self.cat.stop)
        self.uid=patch('os.geteuid',return_value=1000);self.uid.start();self.addCleanup(self.uid.stop)

    def test_urls_and_tokens(self):
        self.assertEqual(backend.clean_url('https://example.org/app?token=secret#private'),'https://example.org/app')
        for url in ['http://example.org/','file:///etc/passwd','https://user:password@example.org/',
                    'https://example.org:22/','https://127.0.0.1/','https://host.local/',
                    'https://example.org/\nExec=sh','https://example.org/%0aExec=sh','https://example.org\\@evil.org/']:
            with self.subTest(url=url),self.assertRaises(ValueError):backend.clean_url(url)

    def test_exact_catalog_match(self):
        self.assertEqual(backend.normalize_offer({'url':'https://web.whatsapp.com/chat?secret=x','name':'Fake'})['name'],'WhatsApp')
        self.assertIsNone(backend.service_for('https://web.whatsapp.com.evil.org/'))
        self.assertEqual(backend.normalize_offer({'url':'https://example.org/','name':'Example'})['availability'],'unknown')

    def test_install_launch_duplicate_and_remove(self):
        data={'url':'https://example.org/app?secret=1','name':'Meu app %U'}
        identifier=backend.install(data);self.assertEqual(identifier,backend.install(data))
        self.assertEqual(len(backend.installed()),1)
        entry=(backend.apps_dir()/f'linuxbr-webapp-{identifier}.desktop').read_text()
        self.assertNotIn('secret',entry);self.assertIn(f'Exec=/usr/bin/linuxbr-webapps --launch {identifier}',entry)
        with patch.object(backend.subprocess,'Popen') as process:
            backend.launch(identifier)
            argv=process.call_args.args[0]
            self.assertEqual(argv[0],'/usr/bin/chromium');self.assertIn('--app=https://example.org/app',argv)
            self.assertFalse(process.call_args.kwargs.get('shell',False))
            self.assertNotIn('--no-sandbox',argv)
        profile=backend.record_path(identifier)/'profile';(profile/'login').write_text('keep')
        backend.remove(identifier);self.assertEqual(backend.installed(),[])
        self.assertEqual((profile/'login').read_text(),'keep')

    def test_bad_records_and_paths(self):
        with self.assertRaises(ValueError):backend.read_record('../../escape')
        identifier=backend.install({'url':'https://example.org/','name':'A'})
        path=backend.record_path(identifier)/'app.json';data=json.loads(path.read_text());data['url']='https://evil.org/'
        path.write_text(json.dumps(data));self.assertEqual(backend.installed(),[])

    def test_sessions_isolate_persist_rename_and_restore(self):
        offer={'url':'https://web.whatsapp.com/','name':'WhatsApp'}
        first=backend.install(offer)
        # Simulate a record created before sessions existed.
        path=backend.record_path(first)/'app.json'
        old=json.loads(path.read_text());old.pop('session');old.pop('instance');path.write_text(json.dumps(old))
        self.assertEqual(backend.read_record(first)['session'],'Principal')
        second=backend.install({**offer,'new_session':True,'session':'Trabalho'})
        self.assertNotEqual(first,second)
        with patch.object(backend.subprocess,'Popen') as process:
            backend.launch(first);backend.launch(second)
            args=[call.args[0] for call in process.call_args_list]
            profiles=[next(arg for arg in argv if arg.startswith('--user-data-dir=')) for argv in args]
            self.assertNotEqual(*profiles)
        for identifier,account in ((first,'pessoal'),(second,'trabalho')):
            (backend.record_path(identifier)/'profile'/'session-marker').write_text(account)
        backend.rename_session(first,'Pessoal')
        self.assertEqual(backend.read_record(first)['session'],'Pessoal')
        self.assertIn('WhatsApp — Pessoal',(backend.apps_dir()/f'linuxbr-webapp-{first}.desktop').read_text())
        with self.assertRaises(ValueError):backend.rename_session(second,'pessoal')
        with self.assertRaises(ValueError):backend.install({**offer,'new_session':True,'session':'TRABALHO'})
        backend.remove(second);self.assertEqual(len(backend.sessions(offer['url'])),1)
        backend.restore(second);self.assertEqual(len(backend.sessions(offer['url'])),2)
        for identifier,account in ((first,'pessoal'),(second,'trabalho')):
            self.assertEqual((backend.record_path(identifier)/'profile'/'session-marker').read_text(),account)
        data=json.loads((backend.record_path(second)/'app.json').read_text());data['instance']='../../bad'
        (backend.record_path(second)/'app.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):backend.read_record(second)

    def test_install_root_refused(self):
        with patch('os.geteuid',return_value=0),self.assertRaises(ValueError):backend.install({'url':'https://example.org/','name':'A'})

    def test_native_actions_only_offer_confirmation(self):
        with patch.object(host.subprocess,'Popen') as process,patch.object(backend,'install') as install:
            self.assertTrue(host.handle({'action':'offer','url':'https://web.whatsapp.com/','name':'A'})['opened'])
            self.assertEqual(process.call_args.args[0][:2],['/usr/bin/linuxbr-webapps','--offer'])
            install.assert_not_called()
        for action in ['install','delete','shell','launch']:
            with self.assertRaises(ValueError):host.handle({'action':action})

    def test_existing_native_app_detected(self):
        backend.apps_dir().mkdir();(backend.apps_dir()/'com.ktechpit.whatsie.desktop').write_text('[Desktop Entry]')
        self.assertTrue(backend.status({'url':'https://web.whatsapp.com/'})['native_installed'])

    def test_profile_controls_bound_to_browser_profile(self):
        identifier=backend.install({'url':'https://web.whatsapp.com/','name':'WhatsApp'})
        item=backend.read_record(identifier)
        with patch.object(backend,'profile_context',return_value=None),patch.object(host.subprocess,'Popen') as process:
            self.assertFalse(host.handle({'action':'new-profile'})['available']);process.assert_not_called()
        with patch.object(backend,'profile_context',return_value=item),patch.object(host.subprocess,'Popen') as process:
            host.handle({'action':'new-profile','id':'../../wrong','url':'https://evil.org/'})
            self.assertEqual(process.call_args.args[0],['/usr/bin/linuxbr-webapps','--new-profile',identifier])
            self.assertEqual(host.handle({'action':'profile-context'})['session'],'Principal')

    def test_manifest_and_host_identity(self):
        import base64,hashlib
        manifest=json.loads((FILES/'usr/share/linuxbr/webapps/manifest.json').read_text())
        digest=hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
        identifier=''.join(chr(97+int(char,16)) for char in digest)
        registration=json.loads((FILES/'etc/chromium/native-messaging-hosts/org.linuxbr.webapps.json').read_text())
        self.assertEqual(registration['allowed_origins'],['chrome-extension://'+identifier+'/'])
        self.assertEqual(manifest['incognito'],'not_allowed')
        self.assertNotIn('history',manifest['permissions']);self.assertNotIn('cookies',manifest['permissions'])

    def test_browser_defaults_are_consistent(self):
        desktop=ROOT/'packages/linuxbr-desktop/files'
        for path in ('etc/skel/.config/kdeglobals','etc/xdg/kdeglobals',
                     'usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/defaults'):
            self.assertIn('BrowserApplication=chromium.desktop',(desktop/path).read_text())
        self.assertIn('x-scheme-handler/https=chromium.desktop;', (desktop/'etc/skel/.config/mimeapps.list').read_text())
        self.assertNotIn('--load-extension=',(FILES/'etc/chromium.d/linuxbr-webapps').read_text())

if __name__=='__main__':unittest.main()
