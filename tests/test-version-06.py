#!/usr/bin/env python3
"""Exercise profile lifecycle, store inventory and installer cancellation."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QApplication,QDialog,QPushButton,QComboBox
import webapps_backend as web
import webapps
import store_backend as store
import store as store_ui
import windows_compat as windows
from daily_use import DailyUse,TASKS
APP=QApplication.instance() or QApplication([])


class Version06(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        for context in (patch.dict(os.environ,{'XDG_DATA_HOME':temp.name,'XDG_CONFIG_HOME':temp.name}),
                        patch.object(web,'CATALOG',FILES/'usr/share/linuxbr/webapps/catalog.json'),
                        patch.object(store,'CATALOG',FILES/'usr/share/linuxbr/store/catalog.json'),
                        patch('os.geteuid',return_value=1000),patch('webapp_icons.request_refresh')):
            context.start();self.addCleanup(context.stop)

    def profile(self,name='Pessoal'):
        return web.install({'url':'https://web.whatsapp.com/','session':name,'new_session':True})

    def test_preferred_profile_is_preselected_but_picker_still_opens(self):
        first=self.profile();second=self.profile('Trabalho');web.set_preferred_profile(second)
        self.assertEqual(web.preferred_profile('https://web.whatsapp.com/'),second)
        picker=webapps.ProfilePicker(web.sessions('https://web.whatsapp.com/'))
        selected=[picker.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(picker.list.count())
                  if picker.list.item(i).checkState()==Qt.CheckState.Checked]
        self.assertEqual(selected,[second]);self.assertTrue(picker.open_button.isEnabled())
        picker.show();APP.processEvents()
        center=picker.card.geometry().center();expected=picker.rect().center()
        self.assertLessEqual(abs(center.x()-expected.x()),1)
        self.assertLessEqual(abs(center.y()-expected.y()),1)
        picker.close()
        with patch.object(webapps.ProfilePicker,'exec') as choose,patch.object(web,'launch') as launch:
            webapps.open_site('https://web.whatsapp.com/');choose.assert_called_once();launch.assert_not_called()
        web.remove(second);self.assertIsNone(web.preferred_profile('https://web.whatsapp.com/'))
        self.assertTrue(web.record_path(first).exists())

    def test_hidden_profile_can_be_deleted_without_touching_other_accounts(self):
        first=self.profile();second=self.profile('Trabalho')
        profile=web.record_path(first)/'profile';profile.mkdir();(profile/'cookies').write_text('private')
        web.remove(first);self.assertTrue(profile.exists());web.delete_profile(first)
        self.assertFalse(profile.exists());self.assertEqual([item['id'] for item in web.installed(True)],[second])
        desktop=web.apps_dir()/f'linuxbr-webapp-site-{web.app_id(web.read_record(second)["url"])}.desktop'
        self.assertIn(second,desktop.read_text())

    def test_running_profile_and_symlink_are_not_deleted(self):
        identifier=self.profile();directory=web.record_path(identifier);profile=directory/'profile';profile.mkdir()
        (profile/'SingletonLock').symlink_to('/missing/chromium-lock')
        with self.assertRaises(ValueError):web.delete_profile(identifier)
        (profile/'SingletonLock').unlink();profile.rmdir()
        outside=directory.parent/'outside';outside.mkdir();(outside/'keep').write_text('preserve')
        profile.symlink_to(outside)
        with self.assertRaises(ValueError):web.delete_profile(identifier)
        self.assertEqual((outside/'keep').read_text(),'preserve')
        with self.assertRaises(ValueError):web.delete_profile('../outside')

    def test_store_installed_inventory_opens_exact_web_profile(self):
        identifier=self.profile()
        with patch.object(store,'native_launch',return_value=None),patch.object(store,'desktop_applications',return_value=[]):items=store.installed_entries(store.catalog())
        self.assertEqual(len(items),1);self.assertEqual(items[0]['profile_id'],identifier)
        self.assertEqual(store.local_action(items[0]),['linuxbr-webapps','--launch',identifier])
        with patch.object(store,'native_launch',return_value=None),patch.object(store,'desktop_applications',return_value=[]),patch('store.subprocess.Popen') as launch:
            window=store_ui.Window();window.view.setCurrentIndex(1)
            window.activate();self.assertEqual(launch.call_args.args[0],['linuxbr-webapps','--launch',identifier])
            window.query.setText('inexistente');self.assertEqual(window.results.count(),0);window.close()

    def test_windows_installer_cancel_does_not_create_environment_or_job(self):
        window=windows.WindowsCompatibility()
        before=windows.environments()
        with (patch.object(windows,'inspect_windows_file',return_value=(Path('/tmp/setup.exe'),'x64')),
             patch.object(windows,'create_environment') as create,patch.object(windows,'start_job') as start):
            QTimer.singleShot(0,lambda:APP.activeModalWidget().reject())
            window.guided_install();create.assert_not_called();start.assert_not_called()
        self.assertEqual(windows.environments(),before);window.close()

    def test_daily_tasks_are_inert_until_clicked(self):
        with patch('daily_use.launch') as launch:
            page=DailyUse();launch.assert_not_called()
            button=next(item for item in page.findChildren(QPushButton) if item.text()=='Mapear unidade de rede')
            button.click();launch.assert_called_once_with(page,['linuxbr-file-tools','--map-network'])
            self.assertEqual(len(TASKS),6)

    def test_windows_guided_install_creates_separate_environment_after_confirmation(self):
        window=windows.WindowsCompatibility();before=windows.environments()
        def confirm():
            dialog=APP.activeModalWidget()
            next(button for button in dialog.findChildren(QPushButton)
                 if button.text()=='Preparar e abrir instalador').click()
        with (patch.object(windows,'inspect_windows_file',return_value=(Path('/tmp/setup.exe'),'x64')),
              patch.object(windows.shutil,'which',return_value='/usr/bin/wine'),
              patch.object(windows,'start_job',return_value='job-06') as start):
            QTimer.singleShot(0,confirm);window.guided_install()
            self.assertEqual(len(windows.environments()),len(before)+1)
            identifier=window.environments.currentData()
            self.assertNotIn(identifier,[value[0] for value in before])
            self.assertEqual(windows.read_environment(identifier)['architecture'],'win64')
            start.assert_called_once_with(identifier,'run','/tmp/setup.exe')
        window.close()

    def test_x64_installer_can_open_guide_when_current_environment_is_32_bit(self):
        identifier=windows.create_environment('Programa antigo','win32')
        window=windows.WindowsCompatibility();window.refresh_environments(identifier)
        with (patch.object(windows,'inspect_windows_file',return_value=(Path('/tmp/setup.exe'),'x64')),
              patch.object(windows.shutil,'which',return_value='/usr/bin/wine')):
            window.file.setText('/tmp/setup.exe');window.review()
            self.assertTrue(window.open_button.isEnabled())
        window.close()

    def test_installer_translation_placeholders(self):
        spec=importlib.util.spec_from_file_location('translations',ROOT/'scripts/prepare-installer-translations.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        tree=ET.ElementTree(ET.fromstring('<TS><context>'+''.join(
            '<message><source>'+source+'</source><translation>1</translation></message>'
            for source in module.CORRECTIONS)+'</context></TS>'))
        module.correct(tree)
        for message in tree.findall('.//message'):self.assertIn('%1',message.findtext('translation'))


if __name__=='__main__':unittest.main()
