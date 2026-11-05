import sys
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import services_backend as backend


class ServiceTests(unittest.TestCase):
    def spec(self, **extra):
        return dict(name='example', argv=['/usr/bin/true'], **extra)

    def test_literal_arguments(self):
        spec = self.spec(environment={'TEST': '$HOME %n "quoted"'})
        spec['argv'] += ['$HOME', '%n', 'a b', '"hello"', ';touch /tmp/x']
        name, result = backend.render('user', spec)
        self.assertEqual(name, 'linuxbr-custom-example.service')
        self.assertIn('"$$HOME" "%%n" "a b"', result)
        self.assertIn('Environment="TEST=$HOME %%n', result)
        self.assertIn('StartLimitBurst=3', result)
        self.assertNotIn('User=', result)

    def test_reject_injection_and_invalid_values(self):
        for spec in [self.spec(description='x\nExecStart=/bin/false'),
                     self.spec(restart='always'), self.spec(restart_seconds=True),
                     self.spec(environment={'BAD\nKEY': 'x'}),
                     self.spec(directory='relative')]:
            with self.assertRaises(ValueError):
                backend.render('user', spec)
        spec = self.spec()
        spec['name'] = '../other'
        with self.assertRaises(ValueError):
            backend.render('user', spec)

    def test_system_requires_account(self):
        with self.assertRaises(ValueError):
            backend.render('system', self.spec())
        _, result = backend.render('system', self.spec(user='root'))
        self.assertIn('User=root', result)
        self.assertIn('WantedBy=multi-user.target', result)

    def test_resource_limits_dependencies_and_isolation(self):
        _,result=backend.render('system',self.spec(user='nobody',requires=['network-online.target'],after=['network-online.target'],memory_mib=64,cpu_percent=25,tasks_max=12,isolation=True))
        for directive in ['MemoryMax=64M','CPUQuota=25%','TasksMax=12','Requires=network-online.target','ProtectSystem=strict','NoNewPrivileges=yes']:
            self.assertIn(directive,result)
        for bad in [dict(cpu_percent=True),dict(memory_mib=-1),dict(requires=['linuxbr-custom-example.service']),dict(after=['a.service\nExecStart=x']),dict(isolation=True)]:
            with self.assertRaises(ValueError):backend.render('user',self.spec(**bad))

    def test_time_limits_groups_permissions_and_network(self):
        group=backend.grp.getgrgid(backend.pwd.getpwnam('nobody').pw_gid).gr_name
        _,result=backend.render('system',self.spec(user='nobody',group=group,restart_burst=2,restart_window=60,start_seconds=20,stop_seconds=10,start_delay=2,umask='0027',private_network=True))
        for directive in ['Group='+group,'StartLimitBurst=2','StartLimitIntervalSec=60','TimeoutStartSec=20','TimeoutStopSec=10','ExecStartPre=/usr/bin/sleep 2','UMask=0027','PrivateNetwork=yes']:
            self.assertIn(directive,result)
        for bad in [dict(restart_burst=0),dict(restart_window=True),dict(start_seconds=10,start_delay=10),dict(umask='0077\nUser=root'),dict(private_network=True)]:
            with self.assertRaises(ValueError):backend.render('user',self.spec(**bad))

    def test_linger_requires_administration_and_explicit_boolean(self):
        with patch.object(backend.os,'geteuid',return_value=1000):
            with self.assertRaises(PermissionError):backend.set_linger(dict(username='brasil',enabled=True,expected=False))
        with patch.object(backend.os,'geteuid',return_value=0):
            for request in [dict(username='--root',enabled=True,expected=False),dict(username='brasil',enabled='true',expected=False)]:
                with self.assertRaises(ValueError):backend.set_linger(request)

    def test_missing_program_remains_editable(self):
        with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ,XDG_CONFIG_HOME=temporary):
            program=Path(temporary)/'program';program.write_text('#!/bin/sh\n');program.chmod(0o700)
            spec=self.spec();spec['argv']=[str(program)]
            unit,content=backend.render('user',spec);target=backend.location('user',unit);target.parent.mkdir(parents=True);target.write_text(content)
            program.unlink()
            self.assertEqual(backend.read_definition('user',unit)['spec'],spec)
            with self.assertRaises(ValueError):backend.render('user',spec)

    def test_essential_alias_is_protected(self):
        with patch.object(backend,'authorize_scope'),patch.object(backend,'details',return_value={'Id':'dbus.service'}),patch.object(backend,'ctl') as ctl:
            with self.assertRaises(ValueError):backend.control('system','alias.service','stop')
            ctl.assert_not_called()

    def test_override_rejects_execution_and_invalid_limits(self):
        for spec in [dict(ExecStart='/bin/true'),dict(cpu_percent=-1),dict(restart='always'),dict(no_new_privileges='yes')]:
            with self.assertRaises(ValueError):backend.override_render(spec)
        self.assertIn('MemoryMax=32M',backend.override_render(dict(memory_mib=32)))

    def test_failed_reload_restores_exact_configuration(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_CONFIG_HOME=temporary):
            original = self.spec(description='Original')
            unit, content = backend.render('user', original)
            path = backend.location('user', unit)
            path.parent.mkdir(parents=True)
            path.write_text(content, encoding='utf-8')
            record = backend.read_definition('user', unit)
            calls = []
            def command(scope, *args):
                calls.append(args)
                if len(calls) == 1:
                    raise RuntimeError('Falha simulada no recarregamento')
                return ''
            with patch.object(backend, 'ctl', side_effect=command), patch.object(backend.os, 'geteuid', return_value=1000), patch.object(backend.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
                with self.assertRaises(RuntimeError):
                    backend.revise('user', unit, record['sha256'], self.spec(description='Alterada'))
            self.assertEqual(path.read_bytes(), content.encode('utf-8'))
            self.assertEqual(len(calls), 2)

    def test_external_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, XDG_CONFIG_HOME=temporary):
            unit, content = backend.render('user', self.spec())
            path = backend.location('user', unit)
            path.parent.mkdir(parents=True)
            path.write_text(content + '\n# external\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                backend.read_definition('user', unit)


if __name__ == '__main__':
    unittest.main()
