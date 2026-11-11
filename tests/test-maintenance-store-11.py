"""Verify the new diagnostic and portable-list boundaries."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import store_format_tests as evidence
import store_portable as portable
import store_transactions as transactions
import support_diagnostics as diagnostics


class MaintenanceStore11(unittest.TestCase):
    def setUp(self):
        self.url = 'https://example.test/repo/'
        self.row = dict(ref='org.example.Editor/x86_64/stable', scope='user',
                        origin='approved', origin_sha256=portable.fingerprint(self.url), commit='a' * 64)

    def test_portable_preview_distinguishes_matching_origin_and_installed(self):
        with (patch.object(portable, 'installed', return_value=[]),
              patch.object(portable, 'remotes', return_value={'approved': self.url})):
            self.assertEqual(portable.review([self.row])[0][1], 'Pode consultar e instalar')
            other = dict(self.row, origin_sha256=portable.fingerprint('https://different.test/repo/'))
            self.assertIn('não corresponde', portable.review([other])[0][1])
        with (patch.object(portable, 'installed', return_value=[(self.row['ref'], 'approved', '')]),
              patch.object(portable, 'remotes', return_value={})):
            self.assertEqual(portable.review([self.row])[0][1], 'Já instalado')

    def test_portable_file_rejects_credentials_commands_and_duplicate_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            def write(rows):
                path.write_text(json.dumps(dict(schema=1, manager='flatpak', apps=rows)), encoding='utf-8')
            write([self.row])
            self.assertEqual(portable.load(path), [self.row])
            for bad in ([dict(self.row, url='https://user:secret@example.test/repo/')],
                        [dict(self.row, command='arbitrary')], [self.row, self.row]):
                write(bad)
                with self.assertRaises(ValueError):
                    portable.load(path)

    def test_installation_rechecks_source_and_exact_ref(self):
        request = transactions.checked_request(dict(manager='flatpak', action='install',
            target=self.row['ref'], scope=self.row['scope'], origin=self.row['origin'],
            expected_origin_sha256=self.row['origin_sha256']))
        with (patch.object(portable, 'remotes', return_value={}),
              patch.object(transactions, 'run_terminal') as launch):
            with self.assertRaisesRegex(ValueError, 'mudou'):
                transactions.run_flatpak(request)
            launch.assert_not_called()
        with (patch.object(portable, 'remotes', return_value={'approved': self.url}),
              patch.object(portable, 'flatpak', return_value='app/org.other.Editor/x86_64/stable'),
              patch.object(transactions, 'run_terminal') as launch):
            with self.assertRaisesRegex(ValueError, 'não está disponível'):
                transactions.run_flatpak(request)
            launch.assert_not_called()

    def test_diagnostics_excludes_unrecognized_values_and_deselected_sections(self):
        with patch.object(diagnostics, 'query', return_value='test-secret-token'):
            sections = {key: diagnostics.collect(key) for key in ('network', 'graphics')}
        data = diagnostics.render(sections, ['network'])
        self.assertNotIn('test-secret-token', data)
        self.assertNotIn('Sessão gráfica', data)
        self.assertIn('indisponível', data)

    def test_evidence_is_bound_to_origin_format_and_artifact(self):
        record = dict(manager='flatpak', target=self.row['ref'], origin=self.url,
                      linuxbr='1.1.0', artifact='a' * 64, date='2026-11-10',
                      architecture='x86_64', version='1', result='pass', checks='abertura',
                      evidence='relatório de laboratório')
        identity = {key: record[key] for key in ('manager', 'target', 'origin', 'linuxbr', 'artifact')}
        self.assertTrue(evidence.assessment([record], **identity).startswith('Testado'))
        self.assertIn('históricos', evidence.assessment([record], **dict(identity, artifact='b' * 64)))
        self.assertEqual(evidence.assessment([record], **dict(identity, manager='deb')), evidence.UNKNOWN)


if __name__ == '__main__':
    unittest.main()
