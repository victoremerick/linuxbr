#!/usr/bin/python3
import sys
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
sys.path.insert(0, str(ROOT/'scripts'))
import credentials
import initial_status
from credential_policy import reject_seeded_credentials


class CredentialStore(unittest.TestCase):
    def setUp(self):
        self.collection = Mock()
        self.collection.get_locked.return_value = False
        self.collection.get_object_path.return_value = '/collection/test'
        self.service = Mock()
        self.secret = SimpleNamespace(
            Service=Mock(), Collection=Mock(), ServiceFlags=SimpleNamespace(OPEN_SESSION=1, LOAD_COLLECTIONS=2),
            CollectionFlags=SimpleNamespace(NONE=0), CollectionCreateFlags=SimpleNamespace(NONE=0),
            Schema=Mock(), SchemaFlags=SimpleNamespace(NONE=0),
            SchemaAttributeType=SimpleNamespace(STRING=1), password_store_sync=Mock(return_value=True),
            password_lookup_sync=Mock(), password_clear_sync=Mock(return_value=True))
        self.secret.Service.get_sync.return_value = self.service
        self.service.get_collections.return_value = []
        self.secret.Collection.for_alias_sync.return_value = self.collection
        self.gio = SimpleNamespace(Cancellable=Mock())
        self.libraries = patch.object(credentials, 'libraries', return_value=(self.gio, self.secret))
        self.libraries.start()
        self.addCleanup(self.libraries.stop)

    def test_read_only_check_does_not_read_saved_passwords(self):
        self.assertEqual(credentials.status()['state'], 'ready')
        self.secret.password_lookup_sync.assert_not_called()
        self.secret.password_store_sync.assert_not_called()
        self.service.unlock_sync.assert_not_called()

    def test_locked_store_is_reported_without_unlock_or_reset(self):
        self.collection.get_locked.return_value = True
        self.assertEqual(credentials.status(probe=True)['state'], 'locked')
        self.service.unlock_sync.assert_not_called()
        self.secret.Collection.create_sync.assert_not_called()
        self.secret.password_store_sync.assert_not_called()

    def test_explicit_unlock_uses_provider(self):
        self.collection.get_locked.side_effect = [True, False]
        self.assertEqual(credentials.status(unlock=True)['state'], 'ready')
        self.service.unlock_sync.assert_called_once()

    def test_missing_store_is_not_created_during_a_check(self):
        self.secret.Collection.for_alias_sync.return_value = None
        self.assertEqual(credentials.status()['state'], 'missing')
        self.secret.Collection.create_sync.assert_not_called()

    def test_creation_requires_explicit_preparation(self):
        self.secret.Collection.for_alias_sync.return_value = None
        self.secret.Collection.create_sync.return_value = self.collection
        self.assertEqual(credentials.status(unlock=True)['state'], 'ready')
        self.secret.Collection.create_sync.assert_called_once()

    def test_existing_login_store_becomes_default_without_creating_another(self):
        self.secret.Collection.for_alias_sync.return_value = None
        self.collection.get_object_path.return_value = '/org/freedesktop/secrets/collection/login'
        self.service.get_collections.return_value = [self.collection]
        self.assertEqual(credentials.status(unlock=True)['state'], 'ready')
        self.service.set_alias_sync.assert_called_once()
        self.secret.Collection.create_sync.assert_not_called()

    def test_probe_only_reads_its_own_unique_entry_and_removes_it(self):
        self.secret.password_lookup_sync.return_value = 'temporary-value'
        with patch.object(credentials.secrets, 'token_urlsafe', return_value='temporary-value'):
            result = credentials.status(probe=True)
        self.assertTrue(result['write_verified'])
        written = self.secret.password_store_sync.call_args.args[1]
        self.assertEqual(set(written), {'probe'})
        self.assertEqual(written, self.secret.password_lookup_sync.call_args.args[1])
        self.assertEqual(written, self.secret.password_clear_sync.call_args.args[1])

    def test_failed_probe_still_cleans_its_entry_and_redacts_provider_error(self):
        self.secret.password_lookup_sync.side_effect = RuntimeError('private-account private-token')
        result = credentials.status(probe=True)
        self.secret.password_clear_sync.assert_called_once()
        self.assertEqual(result['state'], 'unavailable')
        self.assertNotIn('private-', str(result))

    def test_cleanup_failure_does_not_report_success(self):
        self.secret.password_clear_sync.return_value = False
        self.assertEqual(credentials.status(probe=True)['state'], 'unavailable')

    def test_cancelled_prepare_does_not_fail_desktop_start(self):
        with patch.object(credentials, 'status', return_value=credentials.response('locked')), patch('builtins.print'):
            self.assertEqual(credentials.main(['--prepare-session']), 0)
            self.assertEqual(credentials.main(['--check']), 1)

    def test_first_use_warns_about_a_locked_store(self):
        with patch.object(credentials, 'status', return_value=credentials.response('locked')):
            result = initial_status.observe('accounts')
        self.assertEqual(result['state'], 'attention')
        self.assertIn('bloqueado', result['text'])

    def test_first_use_does_not_claim_a_write_test(self):
        with patch.object(credentials, 'status', return_value=credentials.response('ready')):
            result = initial_status.observe('accounts')
        self.assertEqual(result['state'], 'information')
        self.assertNotIn('gravação', result['text'])


class CredentialPackaging(unittest.TestCase):
    def test_new_accounts_cannot_inherit_any_store(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reject_seeded_credentials(root)
            store = root/'etc/skel/.local/share/keyrings'
            store.mkdir(parents=True)
            reject_seeded_credentials(root)
            (store/'login.keyring').write_bytes(b'private-data')
            with self.assertRaises(ValueError): reject_seeded_credentials(root)

    def test_indirect_store_is_refused_even_when_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'root'
            store = root/'etc/skel/.local/share/keyrings'
            store.parent.mkdir(parents=True)
            outside = Path(temp)/'outside'
            outside.mkdir()
            store.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError): reject_seeded_credentials(root)


if __name__ == '__main__':
    unittest.main()
