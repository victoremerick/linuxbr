#!/usr/bin/env python3
"""Check confirmation boundaries and menu management with real Qt widgets."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication,QDialog,QMessageBox
import webapps
import webapps_backend as backend
APP=QApplication.instance() or QApplication([])

class Confirmation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        for mocked in (patch.dict(os.environ,{'XDG_DATA_HOME':self.tmp.name}),
                       patch.object(backend,'CATALOG',FILES/'usr/share/linuxbr/webapps/catalog.json'),
                       patch('os.geteuid',return_value=1000)):
            mocked.start();self.addCleanup(mocked.stop)

    def test_no_install_on_open_or_cancel(self):
        dialog=webapps.InstallDialog({'name':'Wrong','url':'https://web.whatsapp.com/chat?private=1'})
        self.assertEqual(dialog.name.text(),'WhatsApp');self.assertTrue(dialog.url.isReadOnly())
        self.assertEqual(backend.installed(),[]);dialog.reject();self.assertEqual(backend.installed(),[])

    def test_confirm_then_remove_from_manager(self):
        dialog=webapps.InstallDialog({'name':'Site','url':'https://example.org/app'})
        dialog.install_button.click()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        manager=webapps.Window();self.assertEqual(manager.list.count(),1)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):manager.remove()
        self.assertEqual(manager.list.count(),0)
        self.assertTrue((backend.record_path(dialog.identifier)/'app.json').exists())

    def test_invalid_url_does_not_install(self):
        dialog=webapps.InstallDialog();dialog.name.setText('Site');dialog.url.setText('file:///etc/passwd')
        dialog.install_button.click();self.assertTrue(dialog.error.text());self.assertEqual(backend.installed(),[])

    def test_new_session_confirmation_and_selection(self):
        offer={'name':'WhatsApp','url':'https://web.whatsapp.com/'}
        first=backend.install(offer)
        dialog=webapps.InstallDialog(offer)
        self.assertTrue(dialog.new_session)
        dialog.install_button.click();self.assertTrue(dialog.error.text())
        self.assertEqual(len(backend.installed()),1)
        dialog.session.setText('Trabalho');dialog.install_button.click()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        second=dialog.identifier
        with patch.object(webapps.ProfilePicker,'exec',return_value=0) as picker,patch.object(backend,'launch') as launch:
            webapps.open_site(offer['url']);picker.assert_called_once();launch.assert_not_called()
        with patch.object(backend,'launch') as launch:
            picker=webapps.ProfilePicker(backend.sessions(offer['url']))
            self.assertFalse(picker.open_button.isEnabled())
            for i in range(picker.list.count()):picker.list.item(i).setCheckState(webapps.Qt.CheckState.Checked)
            picker.open_button.click()
            self.assertEqual({call.args[0] for call in launch.call_args_list},{first,second})
            self.assertEqual(picker.result(),QDialog.DialogCode.Accepted)
        backend.remove(first)
        with patch.object(backend,'launch') as launch:
            webapps.open_site(offer['url']);launch.assert_called_once_with(second)

if __name__=='__main__':unittest.main()
