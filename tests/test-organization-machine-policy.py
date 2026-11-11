"""Check locally enforced organization controls and interrupted transactions."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1] / 'packages/linuxbr-system/files/usr'
sys.path.insert(0, str(ROOT / 'lib/linuxbr-system'))

import organization_machine_policy as machine
import store_optional


def profile(revision, *rules, organization='lab'):
    return {'organization': organization, 'device': 'test-device', 'revision': revision,
            'rules': [{'id': name, 'required': required, 'value': value}
                      for name, required, value in rules]}


class MachinePolicy(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.policy = root / 'etc' / 'store-optional-sources.json'
        self.state = root / 'var' / 'organization-machine'
        self.policy.parent.mkdir()
        self.state.parent.mkdir()
        patches = ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(patch.multiple(machine, POLICY=self.policy, STATE=self.state, OWNER=os.geteuid()))
        patches.enter_context(patch.object(machine.os, 'geteuid', return_value=0))
        self.fetch = patches.enter_context(patch.object(machine, 'fetch'))
        self.fetch.return_value = profile('policy-1', ('store-snap', True, False))

    def run_apply(self):
        result = machine.command(['preview'])
        return machine.command(['apply', result['revision'], result['rules_sha256']])

    def test_apply_then_restore_absent_policy(self):
        preview = machine.command(['preview'])
        self.assertEqual(preview['changes'], [{'id': 'store-snap', 'from': None, 'to': False}])
        self.assertFalse(self.policy.exists())
        applied = self.run_apply()
        self.assertEqual(applied['managed'], {'store-snap': False})
        self.assertEqual(applied['rules_sha256'], preview['rules_sha256'])
        self.assertEqual(json.loads(self.policy.read_bytes()), {'snap': False})
        self.assertEqual(self.policy.stat().st_mode & 0o777, 0o644)
        self.assertEqual((self.state / 'state.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.run_apply(), applied)
        with patch.object(machine, 'fetch', side_effect=ValueError('Sem conexão')):
            self.assertEqual(machine.command(['status']), applied)
            restored = machine.command(['restore'])
        self.assertFalse(self.policy.exists())
        self.assertIsNone(restored['revision'])
        self.assertEqual([event['action'] for event in restored['history']], ['apply', 'restore'])

    def test_replacement_restores_retired_rules_and_preserves_local_flag(self):
        self.policy.write_text('{"snap":true,"brew":false}', encoding='utf-8')
        self.run_apply()
        self.fetch.return_value = profile('policy-2', ('store-brew', True, True))
        result = self.run_apply()
        self.assertEqual(result['managed'], {'store-brew': True})
        self.assertEqual(json.loads(self.policy.read_bytes()), {'snap': True, 'brew': True})
        machine.command(['restore'])
        self.assertEqual(json.loads(self.policy.read_bytes()), {'snap': True, 'brew': False})

    def test_manual_conflict_stops_apply_and_restore_without_mutation(self):
        applied = self.run_apply()
        self.policy.write_text('{"snap":true,"brew":false}', encoding='utf-8')
        self.fetch.return_value = profile('policy-2', ('store-brew', True, True))
        preview = machine.command(['preview'])
        self.assertFalse(preview['can_apply'])
        self.assertEqual(preview['conflicts'], ['store-snap'])
        with self.assertRaisesRegex(ValueError, 'conflito'):
            self.run_apply()
        with self.assertRaisesRegex(ValueError, 'alterados localmente'):
            machine.command(['restore'])
        self.assertEqual(json.loads(self.policy.read_bytes()), {'snap': True, 'brew': False})
        self.assertEqual(machine.command(['status'])['history'], applied['history'])

    def test_reapproval_required_after_profile_changes_and_unknown_rule_blocks_all(self):
        preview = machine.command(['preview'])
        self.fetch.return_value = profile('policy-1', ('store-snap', True, True))
        with self.assertRaisesRegex(ValueError, 'mudou'):
            machine.command(['apply', preview['revision'], preview['rules_sha256']])
        self.assertFalse(self.policy.exists())
        self.fetch.return_value = profile('policy-2', ('store-snap', True, False),
                                          ('store-brew', False, False),
                                          ('unsupported-control', True, '/etc/other-file'))
        self.assertEqual(machine.command(['preview'])['unsupported'], ['unsupported-control'])
        with self.assertRaisesRegex(ValueError, 'sem suporte'):
            self.run_apply()
        self.assertFalse(self.policy.exists())
        self.fetch.return_value = profile('policy-3', ('store-snap', True, 'false'))
        with self.assertRaisesRegex(ValueError, 'valor inválido'):
            machine.command(['preview'])
        self.fetch.return_value = profile('policy-4', ('store-brew', False, False))
        self.assertEqual(self.run_apply()['managed'], {})
        self.assertFalse(self.policy.exists())

    def test_new_enrollment_cannot_take_over_another_organizations_policy(self):
        self.run_apply()
        self.fetch.return_value = profile('policy-2', ('store-snap', True, True), organization='other')
        self.assertTrue(machine.command(['preview'])['profile_conflict'])
        with self.assertRaisesRegex(ValueError, 'conflito'):
            self.run_apply()
        machine.command(['restore'])
        self.assertEqual(self.run_apply()['organization'], 'other')

    def test_interrupted_state_write_recovers_or_reports_manual_conflict(self):
        original = machine.replace_json

        def interrupted(path, *args):
            if path == self.state / 'state.json':
                raise OSError('Interrupção de teste')
            original(path, *args)

        with patch.object(machine, 'replace_json', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.run_apply()
        pending = self.state / 'pending.json'
        self.assertTrue(pending.exists())
        self.policy.write_text('{"snap":true}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'transação de políticas interrompida'):
            machine.command(['status'])
        self.assertEqual(json.loads(self.policy.read_bytes()), {'snap': True})
        self.assertTrue(pending.exists())
        self.policy.write_text('{"snap":false}', encoding='utf-8')
        self.assertEqual(machine.command(['status'])['managed'], {'store-snap': False})
        self.assertFalse(pending.exists())

    def test_interruption_before_policy_write_does_not_apply_on_restart(self):
        original = machine.replace_json

        def interrupted(path, *args):
            if path == self.policy:
                raise OSError('Interrupção de teste')
            original(path, *args)

        with patch.object(machine, 'replace_json', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.run_apply()
        self.assertEqual(machine.command(['status'])['managed'], {})
        self.assertFalse(self.policy.exists())
        self.assertFalse((self.state / 'pending.json').exists())

    def test_reject_insecure_file_and_arbitrary_action(self):
        other = self.policy.with_name('other.json')
        other.write_text('{"snap":true}', encoding='utf-8')
        self.policy.symlink_to(other)
        with self.assertRaises(OSError):
            self.run_apply()
        self.assertEqual(other.read_text(encoding='utf-8'), '{"snap":true}')
        self.policy.unlink()
        self.policy.write_text('{"snap":true}', encoding='utf-8')
        self.policy.chmod(0o666)
        with self.assertRaisesRegex(ValueError, 'protegido pelo administrador'):
            self.run_apply()
        with self.assertRaisesRegex(ValueError, 'Use preview'):
            machine.command(['apply', self.policy.as_posix(), 'a' * 64])
        with patch.object(machine.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(ValueError, 'autorização de administrador'):
                machine.command(['status'])

    def test_store_enforces_block_without_removing_local_preferences(self):
        if machine.OWNER != 0:
            self.skipTest('A Loja exige arquivo de política do root.')
        self.fetch.return_value = profile('policy-1', ('store-snap', True, False),
                                          ('store-brew', True, True))
        preferences = self.policy.with_name('user-flags.json')
        preferences.write_text('{"snap":true,"brew":false}', encoding='utf-8')
        self.run_apply()
        with patch.multiple(store_optional, POLICY=self.policy, preferences=lambda: preferences):
            self.assertFalse(store_optional.enabled('snap'))
            self.assertTrue(store_optional.allowed('brew'))
            self.assertFalse(store_optional.enabled('brew'))
            machine.command(['restore'])
            self.assertTrue(store_optional.enabled('snap'))
        self.assertEqual(json.loads(preferences.read_bytes()), {'snap': True, 'brew': False})

    def test_policykit_grants_only_the_machine_helper_with_admin_authorization(self):
        policy = ElementTree.parse(ROOT / 'share/polkit-1/actions/org.linuxbr.organization-machine.policy')
        action, = policy.findall('action')
        self.assertEqual(action.attrib['id'], 'org.linuxbr.organization.machine')
        self.assertEqual(action.findtext('defaults/allow_active'), 'auth_admin')
        self.assertEqual(action.findtext('defaults/allow_any'), 'no')
        self.assertEqual(action.findtext('defaults/allow_inactive'), 'no')
        self.assertEqual(action.findtext("annotate[@key='org.freedesktop.policykit.exec.path']"),
                         '/usr/lib/linuxbr-system/organization_machine_policy.py')


if __name__ == '__main__':
    unittest.main()
