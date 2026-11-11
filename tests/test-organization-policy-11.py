"""Verify the account preparation boundary using disposable folders."""
from datetime import datetime, timedelta, timezone
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from organization_policy import apply_preferences, validate


class OrganizationPolicy(unittest.TestCase):
    def profile(self):
        now = datetime.now(timezone.utc)
        return dict(schema=1, kind='organization-policy', organization='example', device='desktop',
                    revision='profile-1', nonce='a' * 64, issued_at=now.isoformat(),
                    expires_at=(now + timedelta(minutes=1)).isoformat(), rules=[
                        dict(id='work-folder', required=False, value='Trabalho'),
                        dict(id='store-search', required=False, value=['LibreOffice'])])

    def test_profile_is_bound_to_request_and_device(self):
        profile = self.profile()
        validate(profile, profile, 'a' * 64, datetime.now(timezone.utc))
        with self.assertRaises(ValueError):
            validate(profile, dict(profile, device='other'), 'a' * 64, datetime.now(timezone.utc))
        with self.assertRaises(ValueError):
            validate(profile, profile, 'b' * 64, datetime.now(timezone.utc))

    def test_repeated_preparation_preserves_existing_documents_and_pending_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / '.config/linuxbr/organization.json'
            profile = self.profile()
            first = apply_preferences(profile, home, state)
            (home / 'Trabalho/documento.txt').write_text('pessoal')
            second = apply_preferences(profile, home, state)
            self.assertEqual(first, second)
            self.assertEqual((home / 'Trabalho/documento.txt').read_text(), 'pessoal')
            self.assertEqual(json.loads(state.read_text())['results'][1]['state'], 'Ação necessária')

    def test_required_control_expiry_and_traversal_cannot_report_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / 'state.json'
            required = self.profile()
            required['rules'][0]['required'] = True
            with self.assertRaisesRegex(ValueError, 'obrigatórios'):
                apply_preferences(required, home, state)
            self.assertFalse(state.exists())
            invalid = self.profile()
            invalid['rules'][0]['value'] = '../outside'
            with self.assertRaises(ValueError):
                apply_preferences(invalid, home, state)
            expired = self.profile()
            expired['expires_at'] = expired['issued_at']
            with self.assertRaisesRegex(ValueError, 'Validade'):
                apply_preferences(expired, home, state)
            self.assertFalse(state.exists())


if __name__ == '__main__':
    unittest.main()
