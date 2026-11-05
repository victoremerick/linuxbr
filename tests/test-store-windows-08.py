#!/usr/bin/env python3
"""Package decisions and Wine maintenance against disposable user data."""
import fcntl
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import MagicMock,patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
import store_backend as store
import store_transactions as transactions
import windows_runner as runner
import windows_recipes as recipes
import windows_games as games
from PyQt6.QtWidgets import QApplication,QMessageBox
from store_operations import Operations
APP=QApplication.instance() or QApplication([])


def request(manager='deb',action='install',scope='system',target='hello',origin='APT'):
    return dict(manager=manager,action=action,scope=scope,target=target,origin=origin,name='Aplicativo de teste')


def executable(path):
    header=bytearray(64);header[:2]=b'MZ';struct.pack_into('<I',header,60,64)
    path.write_bytes(header+b'PE\0\0'+struct.pack('<H',0x8664));return path


class StoreWindows08(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.directory=Path(temporary.name)
        for context in (patch.dict(os.environ,{'XDG_DATA_HOME':temporary.name}),patch('os.geteuid',return_value=1000),
            patch.object(recipes,'CATALOG',FILES/'usr/share/linuxbr/windows/recipes-v1.json')):
            context.start();self.addCleanup(context.stop)
        self.environment=runner.create_environment('Ambiente de teste')
        prefix=runner.environment_path(self.environment)/'prefix';prefix.mkdir()
        (prefix/'system.reg').write_text('registro anterior');(prefix/'documento.txt').write_text('conteúdo preservado')

    def test_exact_identifiers_reject_options_wildcards_and_commands(self):
        for target in ('--purge','hello;touch /tmp/x','*','../../hello','hello\nother'):
            with self.assertRaises(ValueError):transactions.checked_request(request(target=target))
        for target in ('--delete-data','org.example.App;bad','org.example.App/*/stable'):
            with self.assertRaises(ValueError):transactions.checked_request(request('flatpak',target=target,origin='flathub'))
        with self.assertRaises(ValueError):transactions.checked_request(request('flatpak',target='org.example.App',origin='https://host/'))

    def test_flatpak_scope_and_exact_ref_preserve_application_data(self):
        for scope in ('user','system'):
            value=request('flatpak','remove',scope,'org.example.App/x86_64/stable','flathub')
            command=transactions.flatpak_command(value)
            self.assertIn('--'+scope,command);self.assertEqual(command[-1],value['target'])
            self.assertNotIn('--delete-data',command);self.assertNotIn('--unused',command)
        command=transactions.flatpak_command(request('flatpak',target='org.example.App',origin='flathub'))
        self.assertEqual(command[-2:],['flathub','org.example.App'])

    def test_flatpak_keeps_a_terminal_for_native_confirmation(self):
        child=self.directory/'native-confirmation.py';marker=self.directory/'accepted.txt'
        child.write_text('import os,sys\nfrom pathlib import Path\n'
            'if not os.isatty(0): raise SystemExit(4)\n'
            'print("Native confirmation [Y/n]: ",end="",flush=True)\n'
            'if sys.stdin.readline().strip()!="y": raise SystemExit(5)\n'
            'Path(sys.argv[1]).write_text("accepted")\n')
        read_fd,write_fd=os.pipe();os.write(write_fd,b'y\n');os.close(write_fd)
        with (os.fdopen(read_fd,'r') as answer,patch('sys.stdin',answer),
            patch.object(transactions,'flatpak_command',return_value=[sys.executable,str(child),str(marker)]),
            patch.object(transactions,'emit')):
            transactions.run_flatpak(request('flatpak',target='org.example.App',origin='fixture'))
        self.assertEqual(marker.read_text(),'accepted')

    def test_installed_flatpak_scopes_are_separate_choices(self):
        def query(argv):
            if 'list' in argv:return 'org.example.App\tx86_64\tstable\tflathub'
            if 'remotes' in argv:return 'flathub\tFlathub\thttps://dl.flathub.org/repo/'
            return ''
        with patch.object(store,'query_local',side_effect=query):
            targets=store.package_targets(dict(kind='linux',flatpak_id='org.example.App'))
        self.assertEqual(len(targets),2);self.assertEqual({value['scope'] for value in targets},{'user','system'})
        self.assertTrue(all(value['installed'] for value in targets))
        self.assertTrue(all(value['target']=='org.example.App/x86_64/stable' for value in targets))

    def pk(self):
        value=object.__new__(transactions.PackageKit)
        return value

    def test_deb_refusal_never_runs_a_mutating_transaction(self):
        pk=self.pk();package=dict(id='hello;2.10;amd64;debian',info=1,summary='Hello')
        with (patch.object(pk,'transaction',side_effect=[[package],[package]]) as call,patch('sys.stdin',io.StringIO('reject\n')),
            patch.object(transactions,'emit')):
            with self.assertRaises(ValueError):pk.perform(request())
        self.assertEqual(call.call_count,2)
        self.assertEqual(call.call_args_list[1].args[2][0],(1<<1)|(1<<2))

    def test_deb_removal_never_autoremoves_or_removes_dependents(self):
        pk=self.pk();package=dict(id='hello;2.10;amd64;installed',info=2,summary='Hello')
        with (patch.object(pk,'transaction',side_effect=[[package],[package],[]]) as call,patch('sys.stdin',io.StringIO('approve\n')),
            patch.object(transactions,'emit')):
            pk.perform(request(action='remove'))
        for invocation in call.call_args_list[1:]:
            self.assertEqual(invocation.args[0],'RemovePackages');self.assertEqual(invocation.args[2][-2:],(False,False))
        self.assertEqual(call.call_args.args[2][0],1<<1)

    def test_ambiguous_package_is_not_silently_chosen(self):
        pk=self.pk();values=[dict(id='hello;1;amd64;a'),dict(id='hello;1;amd64;b')]
        with patch.object(pk,'transaction',return_value=values) as call:
            with self.assertRaises(ValueError):pk.perform(request())
        self.assertEqual(call.call_count,1)

    def test_multiarch_resolve_selects_system_architecture(self):
        pk=self.pk();values=[dict(id='hello;1;amd64;a'),dict(id='hello;1;i386;a')]
        with (patch.object(pk,'transaction',side_effect=[values,[],[]]) as call,
            patch.object(transactions,'machine_architecture',return_value='amd64'),
            patch('sys.stdin',io.StringIO('approve\n')),patch.object(transactions,'emit')):
            pk.perform(request())
        self.assertEqual(call.call_args.args[2][1],['hello;1;amd64;a'])

    def test_failures_are_recorded_with_origin_scope_and_result(self):
        import uuid
        with (patch.object(transactions.PackageKit,'perform',side_effect=ValueError('Repositório indisponível')),
            patch.object(transactions,'emit')):
            code=transactions.execute(request(),str(uuid.uuid4()))
        self.assertEqual(code,1);record=transactions.history()[0]
        self.assertEqual(record['status'],'failed');self.assertTrue(record['finished'])
        self.assertEqual(record['request']['scope'],'system');self.assertIn('indisponível',record['error'])

    def test_backup_preserves_links_without_copying_personal_directories(self):
        personal=self.directory/'pessoal';personal.mkdir();(personal/'arquivo.txt').write_text('fora do ambiente')
        prefix=runner.environment_path(self.environment)/'prefix';(prefix/'Documentos').symlink_to(personal,target_is_directory=True)
        with patch.object(recipes,'ensure_idle'):
            backup=recipes.backup_environment(self.environment)
        self.assertTrue((backup/'prefix/Documentos').is_symlink())
        self.assertEqual((backup/'prefix/documento.txt').read_text(),'conteúdo preservado')
        self.assertEqual((prefix/'system.reg').read_text(),'registro anterior')
        self.assertEqual(json.loads((backup/'backup.json').read_text())['environment'],self.environment)

    def test_copy_failure_prevents_any_repair_command(self):
        with (patch.object(recipes,'ensure_idle'),patch.object(recipes.shutil,'copytree',side_effect=OSError('Destino desconectado')),
            patch.object(recipes.subprocess,'call') as call):
            with self.assertRaises(OSError):recipes.maintain(self.environment,'repair')
        call.assert_not_called()

    def test_busy_environment_is_never_killed_to_make_a_backup(self):
        import subprocess
        with (patch.object(recipes.subprocess,'run',side_effect=subprocess.TimeoutExpired('wineserver',2)) as run,
            patch.object(recipes.shutil,'copytree') as copy):
            with self.assertRaises(ValueError):recipes.backup_environment(self.environment)
        copy.assert_not_called();self.assertEqual(run.call_args.args[0],['wineserver','--wait'])

    def test_maintenance_lock_blocks_program_open_without_running_wine(self):
        path=runner.environment_path(self.environment)/'maintenance.lock'
        file=executable(self.directory/'programa.exe')
        with path.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            with patch.object(runner.subprocess,'call') as call:
                with self.assertRaises(ValueError):runner.run(self.environment,'run',file)
                call.assert_not_called()

    def test_repair_preserves_other_environments_and_scopes_wine(self):
        other=runner.create_environment('Outro ambiente');before=(runner.environment_path(other)/'environment.json').read_bytes()
        with (patch.object(recipes,'ensure_idle'),patch.object(recipes.subprocess,'call',return_value=0) as call,
            patch.object(recipes.subprocess,'run')):
            recipes.maintain(self.environment,'repair')
        self.assertEqual(call.call_args.args[0],['wineboot','--update'])
        self.assertEqual(call.call_args.kwargs['env']['WINEPREFIX'],str(runner.environment_path(self.environment)/'prefix'))
        self.assertEqual((runner.environment_path(other)/'environment.json').read_bytes(),before)
        self.assertTrue((runner.environment_path(self.environment)/'prefix/documento.txt').exists())

    def test_recipe_root_architecture_and_dependency_are_checked_before_changes(self):
        other=runner.create_environment('Legado','win32')
        with patch.object(recipes,'backup_environment') as backup:
            with self.assertRaises(ValueError):recipes.maintain(other,'apply','7zip-26.05-x64')
            with self.assertRaises(ValueError):recipes.maintain(self.environment,'dependency','7zip-26.05-x64',executable(self.directory/'unrelated.exe'))
            backup.assert_not_called()
        with patch('os.geteuid',return_value=0),patch.object(recipes.subprocess,'call') as call:
            with self.assertRaises(ValueError):recipes.maintain(self.environment,'repair')
            call.assert_not_called()

    def test_recipe_matrix_distinguishes_prior_evidence_and_missing_tests(self):
        value=recipes.catalog();self.assertEqual(value['schema'],1)
        self.assertEqual({item['status'] for item in value['recipes']},{'tested','partial','untested'})
        self.assertIn('Revalidação',recipes.recipe('7zip-26.05-x64')['evidence'])
        self.assertTrue(all(item['status']=='untested' for item in value['games']))

    def test_steam_inventory_is_readonly_and_does_not_claim_validation(self):
        folder=self.directory/'.local/share/Steam/steamapps';folder.mkdir(parents=True)
        manifest=folder/'appmanifest_123.acf';manifest.write_text('"AppState" { "appid" "123" "name" "Jogo de teste" }')
        before=manifest.read_bytes();values=games.installed_games(self.directory)
        self.assertEqual(values[0]['id'],'123');self.assertEqual(values[0]['status'],'Não testado nesta versão')
        self.assertEqual(manifest.read_bytes(),before)
        self.assertEqual(games.details_uri('123'),'steam://nav/games/details/123')
        with self.assertRaises(ValueError):games.details_uri('123/../../run')

    def test_queue_refusal_does_not_add_or_start_operations(self):
        window=Operations();self.addCleanup(window.close)
        target=dict(manager='deb',target='hello',scope='system',origin='APT',installed=False,label='DEB sistema')
        with patch.object(store,'package_targets',return_value=[target]):window.set_item(dict(kind='linux',name='Hello'))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Cancel),patch.object(window,'start_next') as start:
            window.enqueue('install')
        self.assertEqual(window.queue,[]);start.assert_not_called()

    def test_queue_runs_one_operation_at_a_time_in_requested_order(self):
        import uuid
        window=Operations();self.addCleanup(window.close)
        first=(str(uuid.uuid4()),request(target='hello'))
        second=(str(uuid.uuid4()),request(target='ed'))
        window.queue=[first,second]
        with patch('store_operations.QProcess') as process:
            process.return_value.readAllStandardOutput.return_value=b''
            window.start_next();window.start_next()
            self.assertEqual(process.return_value.start.call_count,1)
            self.assertEqual(window.current,first);self.assertEqual(window.queue,[second])
            window.completed(0);APP.processEvents()
            self.assertEqual(process.return_value.start.call_count,2)
            self.assertEqual(window.current,second);self.assertEqual(window.queue,[])
            window.process=None;window.current=None

    def test_success_updates_only_the_selected_installation_scope(self):
        import uuid
        window=Operations();self.addCleanup(window.close)
        for scope in ('user','system'):
            target=dict(manager='flatpak',scope=scope,target='org.example.App',origin='fixture',installed=False)
            window.targets.addItem(scope,target)
        window.current=(str(uuid.uuid4()),request('flatpak','install','user','org.example.App','fixture'))
        window.process=MagicMock();window.process.readAllStandardOutput.return_value=b''
        with patch('store_operations.QTimer.singleShot'):window.completed(0)
        self.assertTrue(window.targets.itemData(0)['installed'])
        self.assertFalse(window.targets.itemData(1)['installed'])
        self.assertTrue(next(button for button,action in window.action_buttons if action=='remove').isEnabled())

    def test_external_job_monitor_does_not_execute_again(self):
        import uuid
        import windows_compat
        job=str(uuid.uuid4());root=runner.data_root()/'jobs';root.mkdir()
        (root/(job+'.json')).write_text(json.dumps(dict(code=0,error='')))
        (root/(job+'.log')).write_text('Resultado da operação anterior.\n')
        window=windows_compat.WindowsCompatibility();self.addCleanup(window.close)
        with patch.object(windows_compat,'start_job') as start:
            window.watch_job(job,self.environment,action='configure');window.poll()
        start.assert_not_called();self.assertIsNone(window.job)
        self.assertEqual(window.last_job_result['code'],0)
        self.assertIn('operação anterior',window.log.toPlainText())
        with self.assertRaises(ValueError):window.watch_job('../../outro',self.environment)
        (root/(job+'.log')).unlink();(root/(job+'.log')).symlink_to(self.directory/'externo')
        with self.assertRaises(ValueError):window.watch_job(job,self.environment)

    def test_open_backups_handles_absence_and_opens_the_private_folder(self):
        import windows_compat
        window=windows_compat.WindowsCompatibility();self.addCleanup(window.close)
        with patch.object(window,'problem') as problem:
            window.open_environment_backups();problem.assert_called_once()
        path=runner.data_root()/'backups';path.mkdir()
        with patch.object(window,'open_path') as open_path:
            window.open_environment_backups();open_path.assert_called_once_with(path)


if __name__=='__main__':unittest.main()
