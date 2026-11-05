#!/usr/bin/env python3
"""Exercise saved profiles, defaults and process status through real Qt widgets."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication,QInputDialog
import webapps
import webapps_backend as backend

APP=QApplication.instance() or QApplication([])


class Profiles07(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)
        for mocked in (patch.dict(os.environ,{'XDG_DATA_HOME':str(self.directory/'data')}),
                       patch.object(backend,'CATALOG',FILES/'usr/share/linuxbr/webapps/catalog.json'),
                       patch('os.geteuid',return_value=1000),patch('webapp_icons.request_refresh')):
            mocked.start();self.addCleanup(mocked.stop)

    def profile(self,name='Pessoal',url='https://web.whatsapp.com/'):
        return backend.install({'url':url,'session':name,'new_session':True})

    def test_rename_preserves_profile_data_favicon_and_default(self):
        first=self.profile();second=self.profile('Trabalho')
        backend.set_preferred_profile(second)
        profile=backend.record_path(second)/'profile';profile.mkdir()
        (profile/'account-marker').write_bytes(b'private saved session')
        icon=backend.root()/'icons'/f'{backend.app_id(backend.read_record(second)["url"])}.png'
        icon.parent.mkdir(exist_ok=True);icon.write_bytes(b'saved favicon')
        backend.rename_session(second,'Empresa')
        self.assertEqual(backend.read_record(second)['session'],'Empresa')
        self.assertEqual(backend.preferred_profile('https://web.whatsapp.com/'),second)
        self.assertEqual((profile/'account-marker').read_bytes(),b'private saved session')
        self.assertEqual(icon.read_bytes(),b'saved favicon')
        self.assertIn('Empresa',(backend.apps_dir()/f'linuxbr-webapp-{second}.desktop').read_text())
        with self.assertRaises(ValueError):backend.rename_session(first,'empresa')
        self.assertEqual(backend.read_record(first)['session'],'Pessoal')

    def test_defaults_are_per_site_and_can_be_cleared(self):
        first=self.profile();second=self.profile('Trabalho')
        other=self.profile('Pessoal','https://example.org/')
        backend.set_preferred_profile(first);backend.set_preferred_profile(other)
        backend.clear_preferred_profile(second)
        self.assertEqual(backend.preferred_profile('https://web.whatsapp.com/'),first)
        backend.set_preferred_profile(second);backend.clear_preferred_profile(second)
        self.assertIsNone(backend.preferred_profile('https://web.whatsapp.com/'))
        self.assertEqual(backend.preferred_profile('https://example.org/'),other)
        (backend.root()/'preferences.json').write_text('[]')
        backend.set_preferred_profile(first)
        self.assertEqual(backend.preferred_profile('https://web.whatsapp.com/'),first)
        with patch('os.geteuid',return_value=0):
            with self.assertRaises(ValueError):backend.set_preferred_profile(first)
            with self.assertRaises(ValueError):backend.clear_preferred_profile(first)

    def test_process_status_ignores_stale_lock_other_apps_and_other_profiles(self):
        first=self.profile();second=self.profile('Trabalho')
        for identifier in (first,second):(backend.record_path(identifier)/'profile').mkdir()
        (backend.record_path(second)/'profile'/'SingletonLock').write_text('stale lock')
        proc=self.directory/'proc';proc.mkdir()
        first_path=str(backend.record_path(first)/'profile')
        second_path=str(backend.record_path(second)/'profile')
        commands={
            '41':['/usr/lib/chromium/chromium','--user-data-dir='+first_path,'--app=https://web.whatsapp.com/'],
            '42':['/usr/lib/chromium/chromium','--user-data-dir',first_path],
            '43':['/usr/bin/editor','--user-data-dir='+second_path],
            '44':['/usr/lib/chromium/chromium','--type=renderer','--user-data-dir='+second_path],
            '45':['/usr/lib/chromium/chromium','--user-data-dir=/unrelated/profile'],
        }
        for pid,args in commands.items():
            path=proc/pid;path.mkdir();(path/'cmdline').write_bytes(('\0'.join(args)+'\0').encode())
        (proc/'46').mkdir()  # A process that disappeared before its arguments were read.
        backend.set_preferred_profile(second)
        with patch('os.geteuid',return_value=(proc/'41').stat().st_uid):
            states=backend.profile_states(backend.installed(),proc)
        self.assertEqual(states[first],{'running':True,'preferred':False})
        self.assertEqual(states[second],{'running':False,'preferred':True})
        with patch('os.geteuid',return_value=(proc/'41').stat().st_uid+1):
            self.assertEqual(backend.running_profiles(backend.installed(),proc),set())
        self.assertEqual(backend.running_profiles(backend.installed(),self.directory/'missing-proc'),set())

    def test_active_profile_cannot_be_deleted_even_without_lock(self):
        first=self.profile();backend.set_preferred_profile(first)
        with patch.object(backend,'running_profiles',return_value={first}):
            with self.assertRaises(ValueError):backend.delete_profile(first)
        self.assertTrue(backend.record_path(first).exists())
        with patch.object(backend,'running_profiles',return_value=set()):backend.delete_profile(first)
        self.assertFalse(backend.record_path(first).exists())
        self.assertNotIn(first,json.dumps(backend._profile_preferences()))

    def test_manager_search_and_status_refresh_keep_selected_profile(self):
        first=self.profile();second=self.profile('Trabalho');backend.set_preferred_profile(second)
        states={first:{'running':True,'preferred':False},second:{'running':False,'preferred':True}}
        with patch.object(backend,'profile_states',return_value=states):
            window=webapps.Window();self.addCleanup(window.close)
            window.search.setText('trabalho')
            selected=window.items[window.list.currentRow()]['id']
            self.assertEqual(selected,second)
            self.assertEqual(sum(not window.list.item(i).isHidden() for i in range(window.list.count())),1)
            self.assertIn('Padrão',window.list.currentItem().text())
            window.refresh_icons();self.assertEqual(window.items[window.list.currentRow()]['id'],second)
            window.refresh();self.assertEqual(window.items[window.list.currentRow()]['id'],second)
            window.search.setText('whatsapp.com');self.assertTrue(all(not window.list.item(i).isHidden() for i in range(window.list.count())))
            self.assertIn('1 em execução',window.summary.text())
            window.search.setText('not-a-profile');self.assertEqual(window.list.currentRow(),-1)

    def test_picker_manages_default_and_name_without_launching_or_losing_checks(self):
        first=self.profile();second=self.profile('Trabalho');backend.set_preferred_profile(first)
        with patch.object(backend,'launch') as launch:
            picker=webapps.ProfilePicker(backend.sessions('https://web.whatsapp.com/'));self.addCleanup(picker.close)
            second_row=next(i for i,item in enumerate(picker.choices) if item['id']==second)
            picker.list.setCurrentRow(second_row)
            picker.list.item(second_row).setCheckState(Qt.CheckState.Checked)
            with patch.object(QInputDialog,'getText',return_value=('Empresa',True)):picker.rename_button.click()
            self.assertEqual(backend.read_record(second)['session'],'Empresa')
            self.assertEqual(picker.list.item(second_row).checkState(),Qt.CheckState.Checked)
            picker.default_button.click()
            self.assertEqual(backend.preferred_profile('https://web.whatsapp.com/'),second)
            self.assertIn('Padrão',picker.list.item(second_row).text())
            picker.default_button.click();self.assertIsNone(backend.preferred_profile('https://web.whatsapp.com/'))
            launch.assert_not_called()
            picker.open_button.click()
            self.assertEqual({call.args[0] for call in launch.call_args_list},{first,second})


if __name__=='__main__':unittest.main()
