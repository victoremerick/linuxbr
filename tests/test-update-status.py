#!/usr/bin/env python3
"""Read release and reboot state with local fixtures and simulated APT queries."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import update_status as updates


class UpdateStatus(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.sources=self.root/'sources';self.sources.mkdir()
        self.boot=self.root/'boot';self.boot.mkdir()
        self.reboot=self.root/'reboot-required'
        paths={'/etc/apt/sources.list.d':self.sources,'/boot':self.boot,'/run/reboot-required':self.reboot}
        for context in (patch.object(updates,'Path',side_effect=lambda value:paths.get(str(value),Path(value))),
                        patch.object(updates.os,'uname',return_value=SimpleNamespace(release='6.12.10-amd64'))):
            context.start();self.addCleanup(context.stop)
        self.process=patch.object(updates.subprocess,'run',side_effect=self.simulate)
        self.run=self.process.start();self.addCleanup(self.process.stop)
        self.installed='0.7.0~beta1'
        self.candidate='0.7.0~beta2'

    def simulate(self,args,**kwargs):
        if args[:2]==['dpkg-query','-W']:
            return subprocess.CompletedProcess(args,0,stdout=self.installed)
        if args[:2]==['apt-cache','policy']:
            return subprocess.CompletedProcess(args,0,stdout='linuxbr-release:\n  Installed: '+self.installed+'\n  Candidate: '+self.candidate+'\n')
        if args[:2]==['dpkg','--compare-versions']:
            return subprocess.CompletedProcess(args,0 if args[-3]=='6.12.11-amd64' else 1,stdout='')
        raise AssertionError('Unexpected command: '+repr(args))

    def test_release_and_only_enabled_distribution_sources_are_reported(self):
        (self.sources/'linuxbr.list').write_text('# comment\ndeb [signed-by=/key.gpg] https://updates.example.org/linuxbr stable main\n')
        (self.sources/'linuxbr-disabled.sources').write_text('Types: deb\nURIs: https://disabled.example.org/\nEnabled: no\n')
        (self.sources/'linuxbr-comment.list').write_text('# deb https://disabled.example.org/ stable main\n')
        (self.sources/'linuxbr.sources').write_text('Types: deb\nURIs: https://updates.example.org/\nSuites: stable\nComponents: main\n')
        (self.sources/'debian.sources').write_text('Types: deb\nURIs: https://deb.debian.org/debian\n')
        (self.sources/'linuxbr.backup').write_text('deb https://backup.example.org stable main\n')
        status=updates.release_status()
        self.assertEqual(status['installed'],'0.7.0~beta1');self.assertEqual(status['candidate'],'0.7.0~beta2')
        self.assertEqual(status['sources'],['linuxbr.list','linuxbr.sources'])
        self.assertFalse(status['reboot_recommended'])
        self.assertTrue(all(call.args[0][0] in ('dpkg-query','apt-cache') for call in self.run.call_args_list))

    def test_deb822_stanzas_are_checked_individually(self):
        (self.sources/'linuxbr-mixed.sources').write_text(
            'Types: deb\nURIs: https://disabled.example.org/\nEnabled: no\n\n'
            'Types: deb\nURIs: https://active.example.org/\nSuites: stable\n')
        (self.sources/'linuxbr-empty.sources').write_text('# URIs: https://comment.example.org/\n')
        self.assertEqual(updates.release_status()['sources'],['linuxbr-mixed.sources'])

    def test_reboot_marker_or_newer_installed_kernel_requires_restart(self):
        (self.boot/'vmlinuz-6.12.9-amd64').write_bytes(b'')
        (self.boot/'vmlinuz-6.12.10-amd64').write_bytes(b'')
        self.assertFalse(updates.release_status()['reboot_recommended'])
        (self.boot/'vmlinuz-6.12.11-amd64').write_bytes(b'')
        self.assertTrue(updates.release_status()['reboot_recommended'])
        (self.boot/'vmlinuz-6.12.11-amd64').unlink()
        self.reboot.write_text('')
        self.assertTrue(updates.release_status()['reboot_recommended'])

    def test_missing_candidate_is_not_displayed_as_a_version(self):
        self.candidate='(none)'
        self.assertEqual(updates.release_status()['candidate'],'')

    def test_query_failures_and_timeouts_leave_status_readable(self):
        for outcome in (FileNotFoundError('apt-cache'),subprocess.TimeoutExpired('apt-cache',10),
                        subprocess.CompletedProcess(['apt-cache'],1,stdout='private error')):
            with self.subTest(outcome=type(outcome).__name__):
                self.run.side_effect=outcome if isinstance(outcome,Exception) else None
                self.run.return_value=outcome
                status=updates.release_status()
                self.assertEqual(status['installed'],'');self.assertEqual(status['candidate'],'')
                self.assertFalse(status['reboot_recommended'])

    def test_status_queries_use_c_locale_and_never_refresh_or_install(self):
        updates.release_status()
        for call in self.run.call_args_list:
            self.assertIn(call.args[0][0],('dpkg-query','apt-cache'))
            self.assertEqual(call.kwargs['env']['LC_ALL'],'C')
            self.assertFalse(call.kwargs.get('shell',False))
            self.assertGreater(call.kwargs['timeout'],0)


if __name__=='__main__':unittest.main()
