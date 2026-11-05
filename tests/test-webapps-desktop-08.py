#!/usr/bin/env python3
"""Isolated regression checks for saved profiles and desktop preferences."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
import webapps
import webapps_backend as web
import webapps_host as host
import desktopflows08 as flows
import desktopflows08_backend as desktop

APP=QApplication.instance() or QApplication([])


class Desktop08(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.directory=Path(temporary.name)
        self.config=self.directory/'config';self.system=self.directory/'system';self.data=self.directory/'data'
        for mocked in (patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.config),'XDG_CONFIG_DIRS':str(self.system),
            'XDG_DATA_HOME':str(self.data),'XDG_DATA_DIRS':str(self.directory/'share'),'XDG_STATE_HOME':str(self.directory/'state'),
            'XDG_CURRENT_DESKTOP':'KDE','KDE_SESSION_VERSION':'6'}),patch('os.geteuid',return_value=1000),
            patch.object(web,'CATALOG',FILES/'usr/share/linuxbr/webapps/catalog.json'),patch('webapp_icons.request_refresh')):
            mocked.start();self.addCleanup(mocked.stop)

    def profile(self, session='Pessoal'):
        return web.install({'url':'https://example.org/app','name':'Exemplo','session':session,'new_session':True})

    def launcher(self, directory, name='example.desktop', extra=''):
        path=directory/'autostart'/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('[Desktop Entry]\nType=Application\nName=Exemplo\nName[pt_BR]=Aplicativo de teste\nExec=/usr/bin/example --option\n'+extra,encoding='utf-8')
        return path

    def test_chromium_preferences_keep_each_profile_and_data(self):
        first=self.profile();second=self.profile('Trabalho')
        directory=web.record_path(first)/'profile';directory.mkdir();(directory/'Cookies').write_bytes(b'cookies preserved')
        with patch.object(web.subprocess,'Popen') as process:
            web.open_profile_settings(first,'site');web.open_profile_settings(second,'downloads')
        first_args=process.call_args_list[0].args[0];second_args=process.call_args_list[1].args[0]
        self.assertIn('--user-data-dir='+str(directory),first_args)
        self.assertIn('chrome-extension://'+web.EXTENSION_ID+'/settings.html?section=site&origin=https%3A%2F%2Fexample.org',first_args)
        self.assertIn('chrome-extension://'+web.EXTENSION_ID+'/settings.html?section=downloads&origin=https%3A%2F%2Fexample.org',second_args)
        self.assertNotEqual(first_args[1],second_args[1]);self.assertEqual((directory/'Cookies').read_bytes(),b'cookies preserved')
        with self.assertRaises(ValueError):web.open_profile_settings(first,'unknown')

    def test_native_settings_bridge_keeps_profile_and_closed_section_list(self):
        identifier=self.profile();directory=web.record_path(identifier)/'profile';directory.mkdir()
        preferences=directory/'Preferences';preferences.write_bytes(b'original preferences')
        with patch.object(web.subprocess,'Popen') as process:
            for section in ('downloads','site','notifications','camera','microphone'):
                web.open_profile_settings(identifier,section)
            for section in ('','__proto__','constructor','downloads&origin=https://other.org','chrome://flags'):
                with self.assertRaises(ValueError):web.open_profile_settings(identifier,section)
        self.assertEqual(process.call_count,5)
        for call in process.call_args_list:
            args=call.args[0]
            self.assertIn('--user-data-dir='+str(directory),args)
            self.assertTrue(args[-1].startswith('chrome-extension://'+web.EXTENSION_ID+'/settings.html?'))
            self.assertIn('&origin=https%3A%2F%2Fexample.org',args[-1])
            self.assertFalse(any(arg.startswith(('--remote-debugging','--allow-chrome-scheme','chrome://')) for arg in args))
        self.assertEqual(preferences.read_bytes(),b'original preferences')

    def test_session_start_only_selected_profiles_rename_and_removal(self):
        first=self.profile();second=self.profile('Trabalho')
        web.save_profile_options(first,session_start=True)
        self.assertTrue(web.profile_options(first)['session_start']);self.assertFalse(web.profile_options(second)['session_start'])
        self.assertIn('--launch '+first,web.session_start_path(first).read_text())
        web.rename_session(first,'Casa');self.assertIn('Casa',web.session_start_path(first).read_text())
        directory=web.record_path(first)/'profile';directory.mkdir();(directory/'Cookies').write_bytes(b'login')
        web.remove(first);self.assertFalse(web.session_start_path(first).exists());self.assertEqual((directory/'Cookies').read_bytes(),b'login')
        web.restore(first);self.assertFalse(web.profile_options(first)['session_start'])

    def test_external_links_preserve_query_and_reject_same_site_and_schemes(self):
        identifier=self.profile()
        with patch.object(web,'default_browser',return_value='chromium.desktop'):
            web.save_profile_options(identifier,'default-browser')
            with patch.object(web.subprocess,'Popen') as process:
                web.open_external(identifier,'https://other.example/path?a=1#part')
            self.assertEqual(process.call_args.args[0],['xdg-open','https://other.example/path?a=1#part'])
            for url in ('https://example.org/elsewhere','javascript:alert(1)','file:///etc/passwd','https://a:b@other.example/',
                        'https://other.example/\nExec=bad','https://other.example:bad/'):
                with self.subTest(url=url),self.assertRaises(ValueError):web.open_external(identifier,url)
        web.save_profile_options(identifier,'profile')
        with self.assertRaises(ValueError):web.open_external(identifier,'https://other.example/')

    def test_default_browser_refuses_webapp_routes_without_changing_preferences(self):
        identifier=self.profile();web.apps_dir().mkdir(exist_ok=True)
        for name,command in [('linuxbr-webapp-example.desktop','chromium %U'),('browser.desktop','linuxbr-webapps --open-site %U'),
                             ('browser.desktop','chromium --app=https://example.org %U')]:
            (web.apps_dir()/name).write_text('[Desktop Entry]\nType=Application\nExec='+command+'\n')
            result=subprocess.CompletedProcess([],0,name+'\n','')
            with patch.object(web.subprocess,'run',return_value=result),self.assertRaises(ValueError):web.save_profile_options(identifier,'default-browser',True)
            self.assertFalse(web.session_start_path(identifier).exists())
            self.assertEqual(web.profile_options(identifier)['external_links'],'profile')
        (web.apps_dir()/'browser.desktop').write_text('[Desktop Entry]\nType=Application\nExec=chromium %U\n')
        with patch.object(web.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'browser.desktop\n','')):
            self.assertEqual(web.default_browser(),'browser.desktop')
        (web.apps_dir()/'linuxbr-webapp-loop.desktop').write_text('[Desktop Entry]\nType=Application\nExec=chromium --app=https://example.org/\n')
        with patch.object(web.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0,'browser.desktop\n',''),
            subprocess.CompletedProcess([],0,'linuxbr-webapp-loop.desktop\n','')]),self.assertRaises(ValueError):web.default_browser('https')

    def test_native_messages_bound_to_browser_ancestry_not_claimed_id(self):
        identifier=self.profile();item=web.read_record(identifier)
        with patch.object(web,'profile_context',return_value=item),patch.object(web,'open_external') as external:
            self.assertTrue(host.handle({'action':'external-link','id':'f'*32,'url':'https://other.example/'})['opened'])
            external.assert_called_once_with(identifier,'https://other.example/')
        with patch.object(web,'profile_context',return_value=None),patch.object(web,'open_external') as external:
            self.assertFalse(host.handle({'action':'external-link','url':'https://other.example/'})['available']);external.assert_not_called()

    def test_autostart_system_override_restore_exact_original_and_no_services(self):
        system=self.launcher(self.system,extra='# keep this\nOnlyShowIn=KDE;\n[Desktop Action Help]\nName=Ajuda\nExec=/usr/bin/help\n')
        original=system.read_bytes();entries=desktop.autostart_entries();self.assertEqual(entries[0]['origin'],'Padrão da sessão');self.assertTrue(entries[0]['enabled'])
        with patch.object(desktop.subprocess,'run') as process:
            desktop.set_autostart(system.name,False);self.assertFalse(desktop.autostart_entries()[0]['enabled'])
            self.assertEqual(system.read_bytes(),original)
            self.assertIn('[Desktop Action Help]',(self.config/'autostart'/system.name).read_text())
            desktop.set_autostart(system.name,True);self.assertTrue(desktop.autostart_entries()[0]['enabled'])
            desktop.restore_autostart(system.name);process.assert_not_called()
        self.assertFalse((self.config/'autostart'/system.name).exists());self.assertEqual(system.read_bytes(),original)
        own=self.launcher(self.config,extra='Hidden=true\nHidden=true\n# original duplicate\n')
        original=own.read_bytes();desktop.set_autostart(own.name,True);self.assertTrue(desktop.autostart_entries()[0]['enabled'])
        desktop.restore_autostart(own.name);self.assertEqual(own.read_bytes(),original)

    def test_autostart_reports_restrictions_and_preserves_other_edits(self):
        path=self.launcher(self.system,extra='OnlyShowIn=GNOME;\n')
        self.assertIn('Não se aplica',desktop.autostart_entries()[0]['status'])
        desktop.set_autostart(path.name,False);target=self.config/'autostart'/path.name
        target.write_text(target.read_text()+'\n# another program changed this\n')
        with self.assertRaises(ValueError):desktop.restore_autostart(path.name)
        with self.assertRaises(ValueError):desktop.set_autostart(path.name,True)
        self.assertIn('another program',target.read_text())
        for name in ('../../bad.desktop','example.service','folder/example.desktop'):
            with self.assertRaises(ValueError):desktop.set_autostart(name,False)
        service=self.launcher(self.system,'managed.desktop','X-systemd-skip=true\n')
        self.assertFalse(next(entry for entry in desktop.autostart_entries() if entry['id']==service.name)['editable'])
        with self.assertRaises(ValueError):desktop.set_autostart(service.name,False)
        self.assertFalse((self.config/'autostart'/service.name).exists())

    def test_search_uses_native_query_as_one_argument_and_portuguese_aliases(self):
        self.assertIn(('Tipos de arquivo e Abrir com','filetypes'),desktop.search_actions('associação'))
        self.assertIn(('Aplicativos na inicialização','startup'),desktop.search_actions('inicializacao'))
        with patch.object(desktop.shutil,'which',return_value='/usr/bin/krunner'),patch.object(desktop.subprocess,'Popen') as process:
            desktop.launch_native('search','foto de família; echo no')
        self.assertEqual(process.call_args.args[0],['/usr/bin/krunner','--','foto de família; echo no'])
        with patch.object(desktop.shutil,'which',return_value=None),self.assertRaises(ValueError):desktop.launch_native('filetypes')

    def test_association_native_change_undo_and_external_change_guard(self):
        apps=self.data/'applications';apps.mkdir(parents=True)
        for identifier in ('first.desktop','second.desktop'):
            (apps/identifier).write_text('[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor %U\nMimeType=text/plain;\n')
        nested=apps/'wine/Programs';nested.mkdir(parents=True)
        (nested/'Editor.desktop').write_text('[Desktop Entry]\nType=Application\nName=Editor Windows\nExec=wine /test/editor.exe %U\nMimeType=text/plain;\n')
        self.assertIn('wine-Programs-Editor.desktop',{entry['id'] for entry in desktop.applications()})
        current=['first.desktop'];calls=[]
        def xdg(args):
            calls.append(args)
            if args[:2]==['query','default']:return current[0]
            if args[0]=='default':current[0]=args[1];return ''
        with patch.object(desktop,'_xdg',side_effect=xdg):
            change=desktop.set_default('text/plain','second.desktop');self.assertEqual(current[0],'second.desktop')
            desktop.undo_default(change);self.assertEqual(current[0],'first.desktop')
            change=desktop.set_default('text/plain','second.desktop');current[0]='other.desktop'
            with self.assertRaises(ValueError):desktop.undo_default(change)
        self.assertEqual(current[0],'other.desktop');self.assertIn(['default','first.desktop','text/plain'],calls)

    def test_preferences_cancel_and_picker_keep_multi_selection(self):
        first=self.profile();second=self.profile('Trabalho');web.set_preferred_profile(first)
        dialog=webapps.ProfilePreferences(first);self.addCleanup(dialog.close)
        dialog.startup.setChecked(True);dialog.reject();self.assertFalse(web.session_start_path(first).exists())
        picker=webapps.ProfilePicker(web.sessions('https://example.org/app'));self.addCleanup(picker.close)
        second_row=next(i for i,item in enumerate(picker.choices) if item['id']==second)
        picker.list.item(second_row).setCheckState(Qt.CheckState.Checked)
        picker.refresh_status();self.assertTrue(all(picker.list.item(i).checkState()==Qt.CheckState.Checked for i in range(picker.list.count())))
        with patch.object(web,'launch') as launch:picker.open_selected()
        self.assertEqual({call.args[0] for call in launch.call_args_list},{first,second})

    def test_embedded_page_startup_actions_work_on_fixture_only(self):
        self.launcher(self.system);page=flows.DesktopFlowsPage('startup');self.addCleanup(page.close)
        self.assertEqual(page.tabs.currentIndex(),page.pages['startup']);self.assertTrue(page.disable.isEnabled())
        page.disable.click();self.assertIn('Preferência salva',page.status.text());self.assertTrue(page.restore.isEnabled())
        page.restore.click();self.assertFalse((self.config/'autostart/example.desktop').exists())
        page.query.setText('abrir com');self.assertGreater(page.actions.topLevelItemCount(),0)

    @unittest.skipUnless(shutil.which('xdg-mime'),'xdg-mime indisponível')
    def test_real_xdg_association_roundtrip_in_private_directories(self):
        apps=self.data/'applications';apps.mkdir(parents=True)
        for identifier in ('linuxbr-test-first.desktop','linuxbr-test-second.desktop'):
            (apps/identifier).write_text('[Desktop Entry]\nType=Application\nName=Editor de teste\nExec=/usr/bin/true %U\nMimeType=text/plain;\n')
        self.config.mkdir(parents=True,exist_ok=True)
        fixture=self.directory/'arquivo com acentos á.txt';fixture.write_text('Documento de teste.\n')
        # A private HOME also contains helpers that do not honor all XDG paths.
        private_home=self.directory/'home';private_home.mkdir()
        with patch.dict(os.environ,{'HOME':str(private_home),'XDG_DATA_DIRS':'/usr/local/share:/usr/share'}):
            desktop.set_default('text/plain','linuxbr-test-first.desktop')
            change=desktop.set_default('text/plain','linuxbr-test-second.desktop')
            self.assertEqual(desktop.file_association(fixture)['default'],'linuxbr-test-second.desktop')
            desktop.undo_default(change)
            self.assertEqual(desktop.file_association(fixture)['default'],'linuxbr-test-first.desktop')

    def test_keyboard_space_enter_escape_and_find(self):
        first=self.profile();second=self.profile('Trabalho')
        picker=webapps.ProfilePicker(web.sessions('https://example.org/app'));self.addCleanup(picker.close)
        picker.show();APP.processEvents();picker.list.setCurrentRow(0)
        QTest.keyClick(picker.list,Qt.Key.Key_Space)
        self.assertEqual(picker.list.item(0).checkState(),Qt.CheckState.Checked)
        with patch.object(web,'launch') as launch:
            QTest.keyClick(picker.list,Qt.Key.Key_Return)
        launch.assert_called_once_with(picker.choices[0]['id'])
        preferences=webapps.ProfilePreferences(first);self.addCleanup(preferences.close)
        preferences.show();preferences.startup.setChecked(True);APP.processEvents()
        QTest.keyClick(preferences,Qt.Key.Key_Escape);self.assertFalse(web.session_start_path(first).exists())
        window=webapps.Window();self.addCleanup(window.close);window.show();window.list.setFocus();APP.processEvents()
        QTest.keyClick(window,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
        self.assertIs(window.focusWidget(),window.search)


if __name__=='__main__':unittest.main()
