#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
import recovery
import setup_flow
from release_info import release_info
APP=QApplication.instance() or QApplication([])


class RecoverySetup(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.tmp.name});env.start();self.addCleanup(env.stop)

    def test_progress_round_trip_and_private_permissions(self):
        setup_flow.save_progress({'backup':True,'apps':False})
        self.assertEqual(setup_flow.load_progress(),{'backup':True,'apps':False})
        self.assertEqual(setup_flow.preferences_path().stat().st_mode & 0o777,0o600)

    def test_corrupt_progress_does_not_prevent_startup(self):
        p=setup_flow.preferences_path();p.parent.mkdir(parents=True);p.write_text('{')
        self.assertEqual(setup_flow.load_progress(),{})

    def test_wizard_never_launches_tools_without_user_action(self):
        with patch.object(setup_flow,'launch') as launch:
            wizard=setup_flow.SetupWizard()
            self.assertEqual(len(wizard.checks),10)
            self.assertFalse(any(check.isChecked() for check in wizard.checks.values()))
            launch.assert_not_called();wizard.close()

    def test_recovery_tabs_do_not_launch_commands(self):
        with patch.object(recovery,'launch') as launch:
            for name,index in [('backup',0),('updates',1),('help',2),('system',3)]:
                page=recovery.RecoveryPage(name)
                self.assertEqual(page.tabs.currentIndex(),index)
                page.close()
            launch.assert_not_called()

    def test_cancel_restore_does_not_open_repository(self):
        page=recovery.RecoveryPage()
        with patch.object(recovery.QFileDialog,'getExistingDirectory',return_value=''),patch.object(recovery,'launch') as launch:
            page.restore_versions();launch.assert_not_called()
        page.close()

    def test_restore_passes_repository_as_single_argument(self):
        page=recovery.RecoveryPage();folder='/media/Backup com espaços'
        with patch.object(recovery.QFileDialog,'getExistingDirectory',return_value=folder),patch.object(recovery,'launch') as launch:
            page.restore_versions();launch.assert_called_once_with(page,['kup-filedigger',folder])
        page.close()

    def test_release_metadata(self):
        p=Path(self.tmp.name);(p/'VERSION').write_text('0.5.0~beta1\n')
        data=release_info(p)
        self.assertEqual(data['display_version'],'0.5.0 Beta 1')
        self.assertEqual(data['channel'],'beta')
        (p/'VERSION').write_text('0.5.0\n')
        self.assertEqual(release_info(p)['channel'],'stable')
        (p/'VERSION').write_text('invalid')
        with self.assertRaises(ValueError):release_info(p)


if __name__=='__main__':unittest.main()
