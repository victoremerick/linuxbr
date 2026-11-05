#!/usr/bin/python3
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import windows_runner as runner


def executable(path,machine=0x8664):
    header=bytearray(64);header[:2]=b'MZ';struct.pack_into('<I',header,60,64)
    path.write_bytes(header+b'PE\0\0'+struct.pack('<H',machine));return path


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.directory=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'XDG_DATA_HOME':self.tmp.name});self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()

    def test_exe_architectures_and_argv(self):
        path=executable(self.directory/'Meu programa $(touch nope).exe')
        self.assertEqual(runner.inspect_windows_file(path)[1],'x64')
        self.assertEqual(runner.command_for('run',path),['wine',str(path)])
        self.assertEqual(runner.inspect_windows_file(executable(self.directory/'old.exe',0x14c))[1],'x86')

    def test_msi_is_not_launched_as_an_exe(self):
        path=self.directory/'installer.msi';path.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+bytes(64))
        self.assertEqual(runner.command_for('run',path),['wine','msiexec','/i',str(path)])

    def test_invalid_and_unsupported_files(self):
        path=self.directory/'fake.exe';path.write_text('echo not a Windows program')
        with self.assertRaises(ValueError):runner.inspect_windows_file(path)
        with self.assertRaises(ValueError):runner.inspect_windows_file(executable(self.directory/'arm.exe',0xaa64))
        with self.assertRaises(ValueError):runner.command_for('delete')
        with self.assertRaises(ValueError):runner.environment_path('../../outside')

    def test_environments_are_separate_and_keep_names(self):
        a=runner.create_environment('Editor');b=runner.create_environment('Jogo','win32')
        self.assertNotEqual(a,b)
        self.assertEqual(runner.read_environment(b)['architecture'],'win32')
        self.assertCountEqual([name for _,name in runner.environments()],['Editor','Jogo'])

    def test_root_cannot_execute(self):
        with patch.object(os,'geteuid',return_value=0),patch.object(runner.subprocess,'call') as call:
            with self.assertRaises(ValueError):runner.run('invalid','run','file.exe')
            call.assert_not_called()

    def test_prefix_and_environment_are_controlled(self):
        identifier=runner.create_environment('Teste');prefix=runner.environment_path(identifier)/'prefix'
        prefix.mkdir();(prefix/'system.reg').touch();file=executable(self.directory/'program.exe')
        with patch.object(os,'geteuid',return_value=1000),patch.dict(os.environ,{'WINEPREFIX':'/wrong','WINEDLLOVERRIDES':'bad'}),patch.object(runner.subprocess,'call',return_value=0) as call:
            self.assertEqual(runner.run(identifier,'run',file),0)
            self.assertEqual(call.call_args.kwargs['env']['WINEPREFIX'],str(prefix))
            self.assertNotIn('WINEDLLOVERRIDES',call.call_args.kwargs['env'])
            self.assertFalse(call.call_args.kwargs.get('shell',False))

    def test_x64_refused_in_legacy_environment(self):
        identifier=runner.create_environment('Legado','win32');file=executable(self.directory/'program.exe')
        with patch.object(os,'geteuid',return_value=1000),patch.object(runner.subprocess,'call') as call:
            with self.assertRaises(ValueError):runner.run(identifier,'run',file)
            call.assert_not_called()

    def test_interface_and_installer_delegate(self):
        from PyQt6.QtWidgets import QApplication,QTabWidget
        import windows_compat
        from installer import Installer
        application=QApplication.instance() or QApplication([])
        with patch.object(windows_compat.shutil,'which',return_value='/usr/bin/wine'):
            window=windows_compat.WindowsCompatibility();file=executable(self.directory/'fixture.exe')
            window.file.setText(str(file));self.assertTrue(window.open_button.isEnabled())
            window.file.setText(str(self.directory/'missing.exe'));self.assertFalse(window.open_button.isEnabled())
            window.show();application.processEvents()
            self.assertTrue(window.grab().save(os.environ.get('WINDOWS_PREVIEW','/tmp/linuxbr-windows.png')))
            window.findChild(QTabWidget).setCurrentIndex(1);application.processEvents()
            self.assertLessEqual(window.height(),720)
            preview=Path(os.environ.get('WINDOWS_PREVIEW','/tmp/linuxbr-windows.png'))
            self.assertTrue(window.grab().save(str(preview.with_name('windows-games.png'))))
            window.close()
        installer=Installer(str(file))
        with patch('installer.QProcess.startDetached',return_value=(True,123)) as launch:
            installer.start();launch.assert_called_once_with('linuxbr-windows',[str(file)])


if __name__=='__main__':unittest.main()
