#!/usr/bin/python3
import importlib.util
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-drive-manager/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-drive-manager'))
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import windows_commands as commands
import windows_runner as runner


class Commands(unittest.TestCase):
    def test_options_and_paths(self):
        with patch.object(commands,'resolve',return_value='/mnt/Dados/Minha pasta'):
            self.assertEqual(commands.command('copy',['/y','C:/origem','D:/destino']),
                             ['cp','-f','--','/mnt/Dados/Minha pasta','/mnt/Dados/Minha pasta'])
        self.assertEqual(commands.command('dir',['/s','/b','/a']),['ls','-R','-1','-a','--','.'])
        self.assertEqual(commands.command('copy',['a','b']),['cp','-i','--','a','b'])
        self.assertEqual(commands.command('del',['a']),['rm','-i','--','a'])
        self.assertEqual(commands.command('rd',['a']),['rmdir','--','a'])
        for name,args in [('del',['/q','a']),('copy',['a']),('ipconfig',['/bad']),('tasklist',['/bad'])]:
            with self.assertRaises(ValueError):commands.command(name,args)

    def test_file_operations_do_not_evaluate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'Minha pasta & $(touch injected).txt';a.write_text('conteúdo')
            b=Path(tmp)/'destino.txt'
            self.assertEqual(subprocess.call(commands.command('copy',['/y',str(a),str(b)])),0)
            self.assertEqual(b.read_text(),'conteúdo')
            self.assertEqual(subprocess.call(commands.command('move',[str(b),str(b.with_suffix('.bak'))])),0)
            self.assertFalse((Path.cwd()/'injected').exists())

    def test_batch_paths_and_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'Meu script & teste.bat';a.write_bytes(b'@echo off\r\nexit /b 7\r\n')
            self.assertEqual(runner.inspect_windows_file(a)[1],'BAT')
            self.assertEqual(runner.command_for('run',a),['wine','cmd','/d','/v:off','/c','linuxbr-script.cmd'])
            for name in ('bad%PATH%.bat','bad"file.cmd'):
                b=Path(tmp)/name;b.write_text('echo teste')
                with self.assertRaises(ValueError):runner.inspect_windows_file(b)
            a.write_bytes(b'not\0text')
            with self.assertRaises(ValueError):runner.inspect_windows_file(a)

    def test_bash_functions_and_original_commands(self):
        shell=(FILES/'usr/share/linuxbr/terminal.bash').read_text()
        shell=shell.replace('/usr/lib/linuxbr-drive-manager/windows_commands.py',str(FILES/'usr/lib/linuxbr-drive-manager/windows_commands.py'))
        with tempfile.TemporaryDirectory() as tmp:
            rc=Path(tmp)/'rc';rc.write_text(shell)
            result=subprocess.run(['bash','--noprofile','--rcfile',str(rc),'-ic',
                'set -e; md "'+tmp+'/pasta"; copy /y /etc/hostname "'+tmp+'/pasta/arquivo"; '
                'dir /b "'+tmp+'/pasta"; type "'+tmp+'/pasta/arquivo"; command type cd; '
                '! dir /q; comandos-windows'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue((Path(tmp)/'pasta/arquivo').is_file())

    def test_cancel_and_edit_never_execute_batch(self):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication,QDialogButtonBox
        import windows_compat
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_DATA_HOME':tmp}):
            script=Path(tmp)/'Teste.bat';script.write_text('@echo off\nexit /b 0\n')
            window=windows_compat.WindowsCompatibility(str(script))
            failures=[]
            def cancel():
                try:
                    dialog=app.activeModalWidget()
                    self.assertEqual(dialog.windowTitle(),'Executar script Windows')
                    buttons=dialog.findChild(QDialogButtonBox)
                    self.assertTrue(buttons.button(QDialogButtonBox.StandardButton.Cancel).isDefault())
                    dialog.reject()
                except Exception as error:
                    failures.append(error)
                    if app.activeModalWidget():app.activeModalWidget().reject()
            with patch.object(windows_compat,'start_job') as job:
                QTimer.singleShot(20,cancel);window.guided_install();job.assert_not_called()
            if failures:raise failures[0]
            with patch.object(window,'launch') as launch:
                window.edit_script();launch.assert_called_once_with(['kate','--',str(script)])
            window.close()

    def test_batch_launches_in_an_interactive_terminal(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_DATA_HOME':tmp}),patch.object(os,'geteuid',return_value=1000):
            script=Path(tmp)/'Teste.cmd';script.write_text('@echo off\nexit /b 0\n')
            identifier=runner.create_environment('Teste')
            with patch.object(runner.subprocess,'Popen') as launch:
                runner.start_job(identifier,'run',script)
                argv=launch.call_args.args[0]
                self.assertEqual(argv[:3],['konsole','--hold','-e'])
                self.assertIn('--interactive',argv)
                self.assertIn(str(script),argv)
                self.assertFalse(launch.call_args.kwargs.get('shell',False))


if __name__=='__main__':unittest.main()
