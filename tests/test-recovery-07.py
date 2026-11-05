#!/usr/bin/env python3
"""Exercise APT restore-point policy using temporary files and simulated commands."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
import snapshot_service as service


class Recovery07(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.config=self.root/'timeshift.json'
        self.policy=self.root/'policy.json'
        self.state=self.root/'state'
        self.live=self.root/'live'
        self.runtime=self.root/'run/linuxbr-recovery'
        self.runtime.parent.mkdir(mode=0o755)
        self.config.write_text(json.dumps({'backup_device_uuid':'aabbccdd-1122-3344-5566-778899aabbcc',
                                          'btrfs_mode':'false','exclude':[]}))
        self.policy.write_text(json.dumps({'before_critical_updates':True}))
        self.config.chmod(0o644);self.policy.chmod(0o644)
        self.owners={self.config:0,self.policy:0,self.state:0,
                     self.runtime.parent:0,self.runtime:0,self.runtime/'snapshot.lock':0}
        original_stat=Path.stat
        original_exists=Path.exists
        original_fstat=os.fstat
        def fixture_stat(path,*args,**kwargs):
            result=original_stat(path,*args,**kwargs)
            if path in self.owners:
                values=list(result);values[4]=self.owners[path]
                return os.stat_result(values)
            return result
        def fixture_exists(path):
            return False if path==Path('/.live-build') else original_exists(path)
        def fixture_fstat(descriptor):
            result=original_fstat(descriptor)
            path=Path(os.readlink('/proc/self/fd/'+str(descriptor)))
            if path in self.owners:
                values=list(result);values[4]=self.owners[path]
                return os.stat_result(values)
            return result
        for context in (patch.object(service,'CONFIG',self.config),patch.object(service,'POLICY',self.policy),
                        patch.object(service,'STATE',self.state),patch.object(service,'LIVE',self.live),
                        patch.object(service,'RUNTIME',self.runtime),patch.object(service.os,'fstat',new=fixture_fstat),
                        patch.object(Path,'stat',new=fixture_stat),patch.object(Path,'exists',new=fixture_exists),
                        patch.dict(os.environ,{'PATH':os.environ.get('PATH','')}),
                        patch('os.geteuid',return_value=0)):
            context.start();self.addCleanup(context.stop)
        self.run=patch.object(service.subprocess,'run',side_effect=AssertionError('Unexpected process execution'))
        self.command=self.run.start();self.addCleanup(self.run.stop)
        self.output=patch.object(service.subprocess,'check_output',side_effect=AssertionError('Unexpected metadata command'))
        self.metadata=self.output.start();self.addCleanup(self.output.stop)

    def main(self,lines='/cache/linuxbr-system.deb\n'):
        with (patch.object(service.sys,'argv',['snapshot_service.py','apt']),
              patch.object(service.sys,'stdin',io.StringIO(lines)),
              patch.object(service.fcntl,'flock'),patch.object(service.sys,'stderr',io.StringIO())):
            return service.main()

    def test_live_environment_does_not_read_archives_or_create_points(self):
        self.live.mkdir()
        self.assertEqual(self.main(),0)
        self.metadata.assert_not_called();self.command.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_only_existing_critical_packages_with_newer_versions_are_selected(self):
        archives={
            '/cache/system.deb':('linuxbr-system','0.7.0~beta1'),
            '/cache/same.deb':('systemd','257.5'),
            '/cache/older.deb':('apt','2.8'),
            '/cache/new.deb':('linux-image-6.12.99-test','6.12.99'),
            '/cache/ordinary.deb':('kate','24.12'),
        }
        self.metadata.side_effect=lambda args,**kwargs: 'Package: %s\nVersion: %s\n'%archives[args[2]]
        old={'linuxbr-system':('installed','0.6.0~beta2'), 'systemd':('installed','257.5'),
             'apt':('installed','3.0'), 'linux-image-6.12.99-test':('not-installed','')}
        def simulate(args,**kwargs):
            if args[0]=='/usr/bin/dpkg-query':
                state,version=old[args[-1]]
                return subprocess.CompletedProcess(args,0 if state=='installed' else 1,stdout=state+' '+version)
            if args[0]=='/usr/bin/dpkg' and '--compare-versions' in args:
                newer=(args[-3],args[-1])==('0.7.0~beta1','0.6.0~beta2')
                return subprocess.CompletedProcess(args,0 if newer else 1)
            raise AssertionError('Snapshot must not run during archive inspection')
        self.command.side_effect=simulate
        lines=list(archives)+['/cache/system.deb','relative.deb','VERSION 2','','**REMOVE**']
        self.assertEqual(service.critical_upgrades(lines),['linuxbr-system'])

    def test_noncritical_transaction_does_not_create_a_point(self):
        with patch.object(service,'critical_upgrades',return_value=[]):self.assertEqual(self.main(),0)
        self.command.assert_not_called();self.assertFalse(self.state.exists())
        self.assertFalse(self.runtime.exists())

    def test_new_grub_install_ignores_missing_runtime_and_unrelated_bad_config(self):
        self.config.write_text('{')
        self.policy.write_text('{')
        self.metadata.side_effect=None
        self.metadata.return_value='Package: grub-efi-amd64\nVersion: 2.12-9\n'
        with patch.object(service.os,'open',side_effect=AssertionError('No runtime or state needed')):
            self.assertEqual(self.main('/var/cache/apt/archives/grub-efi-amd64_2.12-9_amd64.deb\n'),0)
        self.metadata.assert_called_once()
        self.command.assert_not_called();self.assertFalse(self.runtime.exists());self.assertFalse(self.state.exists())

    def test_new_critical_package_is_not_an_upgrade_and_needs_no_lock(self):
        self.config.write_text('{')
        self.metadata.side_effect=None
        self.metadata.return_value='Package: linux-image-6.12-new\nVersion: 6.12.99\n'
        self.command.side_effect=lambda args,**kwargs:subprocess.CompletedProcess(args,1,stdout='not-installed ')
        with patch.object(service.os,'open',side_effect=AssertionError('No runtime or state needed')):
            self.assertEqual(self.main('/cache/new-kernel.deb\n'),0)
        self.assertEqual(self.command.call_count,1)
        self.assertFalse(self.runtime.exists());self.assertFalse(self.state.exists())

    def test_empty_or_unsupported_filename_protocol_needs_no_lock(self):
        for lines in ('','VERSION 2\n\n','VERSION 2\npackage old-version new-version\n'):
            with self.subTest(lines=lines),patch.object(service.os,'open',side_effect=AssertionError('No runtime needed')):
                self.assertEqual(self.main(lines),0)
        self.metadata.assert_not_called();self.command.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_no_destination_records_unconfigured_without_choosing_a_disk(self):
        self.config.unlink()
        with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),0)
        self.command.assert_not_called()
        self.assertEqual(json.loads((self.state/'last.json').read_text())['status'],'not-configured')
        self.assertFalse(self.runtime.exists())

    def test_explicit_policy_disable_is_recorded_without_running_timeshift(self):
        self.policy.write_text(json.dumps({'before_critical_updates':False}))
        with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),0)
        self.command.assert_not_called()
        self.assertEqual(json.loads((self.state/'last.json').read_text())['status'],'disabled')
        self.assertFalse(self.runtime.exists())

    def test_untrusted_policy_and_nonboolean_switch_abort_apt(self):
        for owner,value in ((1000,False),(0,'false'),(0,0),(0,None)):
            with self.subTest(owner=owner,value=value):
                self.owners[self.policy]=owner
                self.policy.write_text(json.dumps({'before_critical_updates':value}))
                with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),1)
                self.command.assert_not_called()

    def test_apt_action_requires_administrative_identity(self):
        with patch('os.geteuid',return_value=1000),self.assertRaises(SystemExit) as stopped:self.main()
        self.assertEqual(stopped.exception.code,1)
        self.command.assert_not_called();self.metadata.assert_not_called()

    def test_configured_snapshot_completes_before_apt_continues(self):
        self.command.side_effect=lambda args,**kwargs:subprocess.CompletedProcess(args,0)
        with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),0)
        args=self.command.call_args.args[0]
        self.assertEqual(args[0],'/usr/bin/timeshift');self.assertIn('--create',args);self.assertIn('--scripted',args)
        self.assertNotIn('--restore',args);self.assertFalse(self.command.call_args.kwargs.get('shell',False))
        state=json.loads((self.state/'last.json').read_text())
        self.assertEqual(state['status'],'created');self.assertEqual(state['packages'],['linuxbr-system'])
        self.assertIn('time',state)
        self.assertEqual(self.runtime.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.runtime/'snapshot.lock').stat().st_mode & 0o777,0o600)

    def test_configured_upgrade_refuses_untrusted_runtime_or_lock(self):
        for case in ('parent-owner','parent-writable','directory-owner','directory-writable',
                     'directory-symlink','lock-owner','lock-writable','lock-symlink','lock-hardlink'):
            with self.subTest(case=case):
                self.runtime.parent.chmod(0o755)
                self.owners[self.runtime.parent]=self.owners[self.runtime]=self.owners[self.runtime/'snapshot.lock']=0
                if self.runtime.is_symlink():self.runtime.unlink()
                if self.runtime.exists():
                    for child in self.runtime.iterdir():child.unlink()
                    self.runtime.rmdir()
                outside=self.root/'outside';outside.mkdir(exist_ok=True)
                target=outside/'preserved';target.write_text('preserved')
                if case=='parent-owner':self.owners[self.runtime.parent]=1000
                elif case=='parent-writable':self.runtime.parent.chmod(0o777)
                elif case=='directory-symlink':self.runtime.symlink_to(outside)
                else:
                    self.runtime.mkdir(mode=0o700)
                    if case=='directory-owner':self.owners[self.runtime]=1000
                    elif case=='directory-writable':self.runtime.chmod(0o777)
                    elif case=='lock-symlink':(self.runtime/'snapshot.lock').symlink_to(target)
                    elif case=='lock-hardlink':os.link(target,self.runtime/'snapshot.lock')
                    else:
                        lock=self.runtime/'snapshot.lock';lock.touch(mode=0o600)
                        if case=='lock-owner':self.owners[lock]=1000
                        elif case=='lock-writable':lock.chmod(0o666)
                with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):
                    self.assertEqual(self.main(),1)
                self.command.assert_not_called()
                self.assertEqual(target.read_text(),'preserved')

    def test_snapshot_nonzero_missing_binary_and_timeout_abort_apt(self):
        for outcome in (subprocess.CompletedProcess(['/usr/bin/timeshift'],12),
                        FileNotFoundError('timeshift'),subprocess.TimeoutExpired('timeshift',7200)):
            with self.subTest(outcome=type(outcome).__name__):
                self.command.side_effect=outcome if isinstance(outcome,Exception) else None
                self.command.return_value=outcome
                with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),1)

    def test_existing_untrusted_or_malformed_configuration_aborts_apt(self):
        cases=('wrong-owner','writable','invalid-json','symlink')
        valid=self.config.read_text()
        for case in cases:
            with self.subTest(case=case):
                self.owners[self.config]=0
                if self.config.is_symlink():self.config.unlink()
                self.config.write_text(valid);self.config.chmod(0o644)
                if case=='wrong-owner':self.owners[self.config]=1000
                elif case=='writable':self.config.chmod(0o666)
                elif case=='invalid-json':self.config.write_text('{')
                else:
                    target=self.root/'untrusted.json';target.write_text(valid)
                    self.config.unlink();self.config.symlink_to(target)
                with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),1)
                self.command.assert_not_called()

    def test_unsupported_modes_personal_inclusions_and_invalid_types_abort(self):
        cases=({'btrfs_mode':'true'},{'exclude':['+ /home/user/**']},
               {'exclude':['  + /home/user/**']},{'exclude':'+ /home/user/**'},
               {'backup_device_uuid':True})
        base=json.loads(self.config.read_text())
        for changes in cases:
            with self.subTest(changes=changes):
                self.config.write_text(json.dumps({**base,**changes}))
                with patch.object(service,'critical_upgrades',return_value=['linuxbr-system']):self.assertEqual(self.main(),1)
                self.command.assert_not_called()

    def test_status_is_read_only_and_normalizes_unexpected_last_state(self):
        self.state.mkdir();(self.state/'last.json').write_text('[]')
        status=service.status()
        self.assertTrue(status['configured']);self.assertTrue(status['automatic'])
        self.assertEqual(status['last'],{})
        self.command.assert_not_called();self.metadata.assert_not_called()

    def test_later_failure_preserves_last_success_and_legacy_state_is_read(self):
        service.save_state({'status':'created','packages':['linuxbr-system']})
        previous=service.status()['last_success']
        self.assertEqual(previous['status'],'created')
        service.save_state({'status':'failed','packages':['linuxbr-system']})
        self.assertEqual(service.status()['last']['status'],'failed')
        self.assertEqual(service.status()['last_success'],previous)
        (self.state/'last-success.json').unlink()
        service.save_state({'status':'created','packages':['linuxbr-system']})
        (self.state/'last-success.json').unlink()
        self.assertEqual(service.status()['last_success'],service.status()['last'])
        self.assertTrue(service.IMPORTANT.match('libkf6kiowidgets6'))

    def test_apt_hook_declares_filename_protocol_and_propagates_errors(self):
        content=(FILES/'etc/apt/apt.conf.d/80linuxbr-recovery').read_text()
        self.assertIn('DPkg::Pre-Install-Pkgs',content)
        self.assertIn('snapshot_service.py apt',content)
        self.assertNotIn('|| true',content);self.assertNotIn('exit 0',content)


if __name__=='__main__':unittest.main()
