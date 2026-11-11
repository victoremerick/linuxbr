"""A reviewed result requires the exact installed package set or a recovery hold."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
for package in ('linuxbr-system', 'linuxbr-boot-tools'):
    sys.path.insert(0, str(ROOT / 'packages' / package / 'files/usr/lib/linuxbr-system'))
from wave_review import review


class WaveReview(unittest.TestCase):
    def setUp(self):
        self.transaction = {'revision': 'update-2', 'status': 'created', 'dpkg_status_sha256': 'a' * 64, 'targets': [
            {'package': 'linuxbr-system', 'version': '1.1.0~alpha1', 'architecture': 'all'},
            {'package': 'test-library', 'version': '2:2.0-1', 'architecture': 'amd64'},
        ]}

    def test_exact_versions_and_reboot_gate(self):
        installed = ('installed\tlinuxbr-system\t1.1.0~alpha1\tall\n'
                     'installed\ttest-library\t2:2.0-1\tamd64\n')
        with patch('wave_review.subprocess.check_output', return_value=installed):
            self.assertEqual(review(self.transaction, [], [], False, '', 'a' * 64)['outcomes'], [])
            self.assertEqual(review(self.transaction, [], [], True, '', 'b' * 64)['outcomes'], [])
            self.assertEqual(review(self.transaction, [], [], False, '', 'b' * 64)['outcomes'],
                             [{'revision': 'update-2', 'state': 'completed'}])
            self.assertEqual(review(self.transaction, [], [], False, 'unconfigured', 'b' * 64)['outcomes'],
                             [{'revision': 'update-2', 'state': 'failed'}])
        with patch('wave_review.subprocess.check_output', return_value=installed.replace('amd64', 'i386')):
            self.assertEqual(review(self.transaction, [], [], False, '', 'b' * 64)['outcomes'],
                             [{'revision': 'update-2', 'state': 'failed'}])

    def test_restoration_and_protection_failure(self):
        self.assertEqual(review({}, ['update-2'], ['update-2'], False, '', 'a' * 64)['outcomes'],
                         [{'revision': 'update-2', 'state': 'restored'}])
        self.assertEqual(review({}, ['update-2'], [], False, '', 'a' * 64)['outcomes'], [])
        self.assertEqual(review({}, ['update-2'], ['update-2'], False, 'unconfigured', 'a' * 64)['outcomes'], [])
        self.assertEqual(review({'revision': 'update-2', 'status': 'failed'}, [], [], False, '', 'a' * 64)['outcomes'],
                         [{'revision': 'update-2', 'state': 'failed'}])


if __name__ == '__main__':
    unittest.main()
