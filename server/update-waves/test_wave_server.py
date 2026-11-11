"""Exercise the local deployment contract without installing package fixtures."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from wsgiref.simple_server import make_server

from waves_server import Service, gpg_signer


CLIENT = Path(__file__).resolve().parents[2] / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0, str(CLIENT))
import update_waves
import organization_policy
import organization_machine_policy


class WaveServerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.service = Service(self.directory / 'waves.sqlite', lambda value: value,
                               'https://waves.example.test')
        self.service.initialize('lab')
        self.admin = self.service.register('ti')
        self.pilot = self.service.register('lab-pilot', 'pilot')
        self.general = self.service.register('lab-general', 'general')
        self.archive = self.directory / 'sample.deb'
        self.archive.write_bytes(b'package fixture')
        self.service.stage('revision-1', [self.archive])
        self.inventory = {'release': '1.1.0', 'free_bytes': 5 * 1024**3, 'reboot_pending': False}

    def call(self, token, method, path, payload=None, **headers):
        raw = json.dumps(payload).encode() if payload is not None else b''
        environ = {'PATH_INFO': path, 'REQUEST_METHOD': method,
                   'HTTP_AUTHORIZATION': 'Bearer ' + token, 'CONTENT_LENGTH': str(len(raw)),
                   'CONTENT_TYPE': 'application/json', 'wsgi.input': BytesIO(raw), **headers}
        status = []
        answer = b''.join(self.service(environ, lambda code, _: status.append(int(code[:3]))))
        return status[0], json.loads(answer)

    def action(self, action, target, **headers):
        return self.call(self.admin, 'POST', '/v1/admin/action',
                         {'action': action, 'target': target}, **headers)

    def manifest(self, token):
        return self.call(token, 'POST', '/v1/manifest',
                         {'nonce': 'f' * 64, 'inventory': self.inventory})

    def result(self, token, state):
        return self.call(token, 'POST', '/v1/result', {'revision': 'revision-1', 'state': state})

    def test_pilot_result_promotion_pause_and_retirement(self):
        self.assertEqual(self.action('pilot', 'revision-1')[0], 200)
        self.assertEqual(self.manifest(self.general)[1]['waves']['general'], 'paused')
        self.assertEqual(self.result(self.general, 'completed')[0], 409)
        self.assertEqual(self.action('promote', 'revision-1')[0], 400)
        code, pilot = self.manifest(self.pilot)
        self.assertEqual(code, 200)
        self.assertEqual(pilot['nonce'], 'f' * 64)
        self.assertEqual(self.result(self.pilot, 'completed')[0], 200)
        self.assertEqual(self.action('promote', 'revision-1')[0], 200)
        general = self.manifest(self.general)[1]
        self.assertEqual(general['archives'], pilot['archives'])
        self.assertEqual(general['waves']['general'], 'approved')
        self.assertEqual(self.action('pause', 'revision-1')[0], 200)
        self.assertEqual(self.manifest(self.general)[1]['waves']['general'], 'paused')
        self.assertEqual(self.action('resume', 'revision-1')[0], 200)
        self.assertEqual(self.manifest(self.general)[1]['waves']['general'], 'approved')
        self.assertEqual(self.action('retire', 'revision-1')[0], 200)
        self.assertEqual(self.manifest(self.general)[0], 409)

    def test_failed_pilot_is_never_promoted_or_retried(self):
        self.assertEqual(self.action('pilot', 'revision-1')[0], 200)
        self.assertEqual(self.manifest(self.pilot)[0], 200)
        self.assertEqual(self.result(self.pilot, 'failed')[0], 200)
        self.assertEqual(self.result(self.pilot, 'completed')[0], 409)
        self.assertEqual(self.manifest(self.pilot)[0], 409)
        self.assertEqual(self.action('promote', 'revision-1')[0], 400)

    def test_window_restricts_authorization_without_blocking_results_or_manual_pause(self):
        operator = self.service.register('release-operator', role='release')
        starts = datetime(2026, 11, 11, 1, tzinfo=timezone.utc)
        ends = starts + timedelta(hours=1)
        local = {'starts_at': '2026-11-10T22:00-03:00', 'ends_at': '2026-11-10T23:00-03:00'}
        expected = {'starts_at': starts.isoformat(), 'ends_at': ends.isoformat()}
        action = {'action': 'set-window', 'target': 'revision-1', 'window': local, 'expected_window': None}
        self.assertEqual(self.call(operator, 'POST', '/v1/admin/action', action)[0], 200)
        self.assertEqual(self.action('pilot', 'revision-1')[0], 200)
        with patch('waves_server.now', return_value=starts - timedelta(seconds=1)):
            self.assertEqual(self.manifest(self.pilot)[1]['waves']['pilot'], 'paused')
            self.assertEqual(self.result(self.pilot, 'completed')[0], 409)
            dashboard = self.call(operator, 'GET', '/v1/admin/status')[1]
            self.assertEqual(dashboard['active']['window_state'], 'scheduled')
            self.assertEqual(dashboard['revisions'][0]['window'], expected)
        with patch('waves_server.now', return_value=starts):
            self.assertEqual(self.manifest(self.pilot)[1]['waves']['pilot'], 'approved')
            self.assertEqual(self.manifest(self.general)[1]['waves']['general'], 'paused')
            self.assertEqual(self.action('pause', 'revision-1')[0], 200)
            self.assertEqual(self.manifest(self.pilot)[1]['waves']['pilot'], 'paused')
            self.assertEqual(self.action('resume', 'revision-1')[0], 200)
        with patch('waves_server.now', return_value=ends - timedelta(seconds=5)):
            _, approved = self.manifest(self.pilot)
            self.assertEqual(approved['waves']['pilot'], 'approved')
            self.assertEqual(approved['maintenance_window'], expected)
            self.assertEqual(approved['expires_at'], ends.isoformat())
            self.assertEqual(update_waves.verify_manifest(approved, 'lab', 'pilot', approved['archives'],
                                                          ends - timedelta(seconds=1)), 'revision-1')
            with self.assertRaisesRegex(ValueError, 'vencida'):
                update_waves.verify_manifest(approved, 'lab', 'pilot', approved['archives'], ends)
        with patch('waves_server.now', return_value=ends):
            self.assertEqual(self.manifest(self.pilot)[1]['waves']['pilot'], 'paused')
            self.assertEqual(self.result(self.pilot, 'completed')[0], 200)
            self.assertEqual(self.action('promote', 'revision-1')[0], 200)
            self.assertEqual(self.manifest(self.general)[1]['waves']['general'], 'paused')
            self.assertEqual(self.action('retire', 'revision-1')[0], 200)
            self.assertEqual(self.manifest(self.pilot)[0], 409)

    def test_window_edit_roles_validation_conflicts_and_legacy_database(self):
        with closing(self.service.connect()) as db, db:
            db.execute('DROP TABLE maintenance_windows')
        self.assertIsNone(self.call(self.admin, 'GET', '/v1/admin/status')[1]['revisions'][0]['window'])
        support = self.service.register('support-operator', role='support')
        operator = self.service.register('release-operator', role='release')
        action = {'action': 'set-window', 'target': 'revision-1', 'expected_window': None}
        local = {'starts_at': '2026-11-10T22:00-03:00', 'ends_at': '2026-11-11T02:00Z'}
        self.assertEqual(self.call(support, 'POST', '/v1/admin/action', dict(action, window=local))[0], 403)
        for bad in (dict(local, starts_at='2026-11-10T22:00'),
                    dict(local, ends_at=local['starts_at']),
                    dict(local, starts_at='2026-02-30T22:00-03:00')):
            self.assertEqual(self.call(operator, 'POST', '/v1/admin/action', dict(action, window=bad))[0], 400)
        self.assertEqual(self.call(self.admin, 'POST', '/v1/admin/action', dict(action, window=local))[0], 200)
        self.assertEqual(self.call(operator, 'POST', '/v1/admin/action', dict(action, window=local))[0], 409)
        dashboard = self.call(self.admin, 'GET', '/v1/admin/status')[1]
        expected = dashboard['revisions'][0]['window']
        changed = dict(local, ends_at='2026-11-11T03:00Z')
        self.assertEqual(self.call(operator, 'POST', '/v1/admin/action',
                                   dict(action, expected_window=expected, window=changed))[0], 200)
        clear = {'action': 'clear-window', 'target': 'revision-1', 'expected_window': expected}
        self.assertEqual(self.call(operator, 'POST', '/v1/admin/action', clear)[0], 409)
        self.assertEqual(self.call(support, 'POST', '/v1/admin/action', clear)[0], 403)
        dashboard = self.call(self.admin, 'GET', '/v1/admin/status')[1]
        self.assertEqual(self.call(operator, 'POST', '/v1/admin/action',
                                   dict(clear, expected_window=dashboard['revisions'][0]['window']))[0], 200)
        dashboard = self.call(self.admin, 'GET', '/v1/admin/status')[1]
        self.assertIsNone(dashboard['revisions'][0]['window'])
        self.assertEqual([row['action'] for row in dashboard['audit'][:3]],
                         ['clear-window', 'reschedule-window', 'set-window'])
        self.assertTrue(all('revision-1' in row['target'] for row in dashboard['audit'][:3]))
        self.assertEqual(self.action('pilot', 'revision-1')[0], 200)
        self.assertEqual(self.manifest(self.pilot)[1]['waves']['pilot'], 'approved')

    def test_roles_origin_and_inventory(self):
        self.assertEqual(self.call(self.pilot, 'GET', '/v1/admin/status')[0], 401)
        self.assertEqual(self.manifest(self.admin)[0], 401)
        self.assertEqual(self.action('pilot', 'revision-1', HTTP_ORIGIN='https://other.test')[0], 403)
        self.assertEqual(self.call(self.pilot, 'POST', '/v1/inventory', self.inventory)[0], 200)
        code, dashboard = self.call(self.admin, 'GET', '/v1/admin/status')
        self.assertEqual(code, 200)
        device = next(item for item in dashboard['devices'] if item['name'] == 'lab-pilot')
        self.assertEqual(device['free_bytes'], self.inventory['free_bytes'])
        self.assertIsNotNone(device['last_contact'])
        self.assertNotIn('token_hash', device)
        self.assertEqual(self.action('disable-device', 'lab-pilot')[0], 200)
        self.assertEqual(self.manifest(self.pilot)[0], 401)
        auditor = self.service.register('auditor', role='audit')
        self.assertEqual(self.call(auditor, 'GET', '/v1/admin/status')[0], 200)
        self.assertEqual(self.call(auditor, 'POST', '/v1/admin/action',
                                   {'action': 'pilot', 'target': 'revision-1'})[0], 403)
        self.assertEqual(self.call(auditor, 'POST', '/v1/admin/report',
                                   {'request_id': 'a' * 32})[0], 403)

    def test_diagnostics_bound_to_device_and_approved_fields(self):
        self.assertEqual(self.action('diagnostic', 'lab-pilot')[0], 200)
        self.assertEqual(self.action('diagnostic', 'lab-pilot')[0], 409)
        _, pending = self.call(self.pilot, 'GET', '/v1/diagnostic')
        request_id = pending['request_id']
        self.assertIsNone(self.call(self.general, 'GET', '/v1/diagnostic')[1]['request_id'])
        report = {'schema': 1, 'diagnóstico': {'Rede': {'conectividade': 'full'}}}
        packet = {'request_id': request_id, 'report': report}
        self.assertEqual(self.call(self.general, 'POST', '/v1/diagnostic', packet)[0], 409)
        invalid = {'schema': 1, 'diagnóstico': {'Rede': {'senha': 'privada'}}}
        self.assertEqual(self.call(self.pilot, 'POST', '/v1/diagnostic',
                                   dict(packet, report=invalid))[0], 400)
        self.assertEqual(self.call(self.pilot, 'POST', '/v1/diagnostic', packet)[0], 200)
        self.assertEqual(self.call(self.pilot, 'POST', '/v1/diagnostic', packet)[0], 409)
        self.assertEqual(self.call(self.admin, 'POST', '/v1/admin/report',
                                   {'request_id': request_id}), (200, report))
        self.assertEqual(self.action('delete-diagnostic', request_id)[0], 200)
        self.assertEqual(self.call(self.admin, 'POST', '/v1/admin/report',
                                   {'request_id': request_id})[0], 404)

    def test_policy_assignment_is_scoped_and_preserves_unknown_required_rule(self):
        rules = [{'id': 'work-folder', 'required': False, 'value': 'Trabalho'},
                 {'id': 'future-rule', 'required': True, 'value': {'setting': 1}}]
        self.service.stage_policy('work-1', rules)
        self.assertEqual(self.call(self.pilot, 'POST', '/v1/policy', {'nonce': 'f' * 64})[0], 409)
        self.assertEqual(self.call(self.admin, 'POST', '/v1/admin/action',
                                   {'action': 'assign-policy', 'target': 'lab-pilot', 'profile': 'work-1'})[0], 200)
        code, policy = self.call(self.pilot, 'POST', '/v1/policy', {'nonce': 'f' * 64})
        self.assertEqual(code, 200)
        self.assertEqual(policy['kind'], 'organization-policy')
        self.assertEqual(policy['rules'], rules)
        self.assertEqual(policy['device'], 'lab-pilot')
        self.assertEqual(self.call(self.general, 'POST', '/v1/policy', {'nonce': 'f' * 64})[0], 409)
        self.assertEqual(self.action('clear-policy', 'lab-pilot')[0], 200)
        self.assertEqual(self.call(self.pilot, 'POST', '/v1/policy', {'nonce': 'f' * 64})[0], 409)

    def test_policy_validates_known_values_before_staging(self):
        for rules in (
            [{'id': 'work-folder', 'required': False, 'value': '../pessoal'}],
            [{'id': 'store-search', 'required': False, 'value': ['editor\ncomando']}],
            [{'id': 'store-search', 'required': 'yes', 'value': ['editor']}],
            [{'id': 'store-snap', 'required': True, 'value': 'false'}],
        ):
            with self.assertRaises(ValueError):
                self.service.stage_policy('bad', rules)

    @unittest.skipUnless(all(shutil.which(tool) for tool in ('gpg', 'gpgv', 'openssl')),
                         'GnuPG e OpenSSL são necessários')
    def test_client_authorizes_over_https_and_refuses_offline_pause(self):
        home = self.directory / 'gnupg'
        home.mkdir(mode=0o700)
        gpg = ['gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '']
        self.addCleanup(subprocess.run, ['gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'],
                        capture_output=True)
        subprocess.run(gpg + ['--quick-generate-key', 'Wave Lab <wave@example.test>', 'ed25519', 'sign', '1d'],
                       check=True, capture_output=True)
        lines = subprocess.check_output(gpg + ['--with-colons', '--fingerprint'], text=True).splitlines()
        fingerprint = next(line.split(':')[9] for line in lines if line.startswith('fpr:'))
        self.service.signer = gpg_signer(str(home), fingerprint)
        certificate, tls_key, keyring, config, token_file = [self.directory / name for name in
            ('ca.pem', 'tls.key', 'trusted.gpg', 'config.json', 'device-token')]
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=IP:127.0.0.1',
                        '-keyout', str(tls_key), '-out', str(certificate)],
                       check=True, capture_output=True)
        keyring.write_bytes(subprocess.check_output(gpg + ['--export']))
        token_file.write_text(self.pilot, encoding='ascii')
        token_file.chmod(0o600)
        self.action('pilot', 'revision-1')
        server = make_server('127.0.0.1', 0, self.service)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config.write_text(json.dumps({'schema': 1, 'organization': 'lab', 'device': 'lab-pilot',
                                     'wave': 'pilot', 'endpoint': f'https://127.0.0.1:{server.server_port}',
                                     'ca_file': str(certificate), 'token_file': str(token_file)}),
                          encoding='utf-8')
        try:
            with (patch.multiple(update_waves, DIRECTORY=self.directory, CONFIG=config, KEYRING=keyring),
                  patch.object(update_waves, 'trusted_file', side_effect=lambda path, **_: path.read_bytes())):
                instant = datetime.now(timezone.utc)
                self.assertEqual(self.call(self.admin, 'POST', '/v1/admin/action',
                    {'action': 'set-window', 'target': 'revision-1', 'expected_window': None, 'window': {
                        'starts_at': (instant - timedelta(minutes=1)).isoformat(timespec='seconds'),
                        'ends_at': (instant + timedelta(minutes=1)).isoformat(timespec='seconds'),
                    }})[0], 200)
                self.assertEqual(update_waves.authorize([str(self.archive)]), 'revision-1')
                rules = [{'id': 'work-folder', 'required': False, 'value': 'Trabalho'},
                         {'id': 'store-snap', 'required': True, 'value': False}]
                self.service.stage_policy('profile-1', rules)
                self.assertEqual(self.call(self.admin, 'POST', '/v1/admin/action',
                    {'action': 'assign-policy', 'target': 'lab-pilot', 'profile': 'profile-1'})[0], 200)
                client_config = update_waves.read_config()
                profile = update_waves.decode_manifest(update_waves.request(
                    client_config, 'POST', '/v1/policy', {'nonce': 'e' * 64}))
                self.assertEqual(organization_policy.validate(
                    profile, client_config, 'e' * 64, update_waves.datetime.now(update_waves.timezone.utc))['rules'], rules)
                machine_policy = self.directory / 'store-optional-sources.json'
                machine_state = self.directory / 'organization-machine'
                with (patch.multiple(organization_machine_policy, POLICY=machine_policy, STATE=machine_state,
                                     OWNER=os.geteuid()),
                      patch.object(organization_machine_policy.os, 'geteuid', return_value=0)):
                    reviewed = organization_machine_policy.command(['preview'])
                    self.assertTrue(reviewed['can_apply'])
                    self.assertEqual(reviewed['rules_sha256'], organization_machine_policy.fingerprint(profile))
                    applied = organization_machine_policy.command(
                        ['apply', reviewed['revision'], reviewed['rules_sha256']])
                    self.assertEqual(applied['managed'], {'store-snap': False})
                    self.assertEqual(json.loads(machine_policy.read_bytes()), {'snap': False})
                    self.assertEqual(organization_machine_policy.command(['restore'])['managed'], {})
                    self.assertFalse(machine_policy.exists())
                self.action('pause', 'revision-1')
                with self.assertRaisesRegex(ValueError, 'pausada'):
                    update_waves.authorize([str(self.archive)])
                server.shutdown()
                server.server_close()
                with self.assertRaisesRegex(ValueError, 'contactar'):
                    update_waves.authorize([str(self.archive)])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
