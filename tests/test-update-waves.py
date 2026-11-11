"""Exercise signed wave authorization and its integration with recovery."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import snapshot_service
import update_waves


class UpdateWaves(unittest.TestCase):
    @unittest.skipUnless(shutil.which('gpg') and Path('/usr/bin/gpgv').is_file(), 'GnuPG necessário')
    def test_signed_batch_pilot_and_general(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / 'gnupg'
            home.mkdir(mode=0o700)
            gpg = ['gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback',
                   '--passphrase', '']
            keyring, signed, payload = [root / name for name in ('keys.gpg', 'wave.gpg', 'wave.json')]
            subprocess.run(gpg + ['--quick-generate-key', 'Wave Test <wave@example.test>',
                                  'ed25519', 'sign', '1d'], check=True, capture_output=True)
            keyring.write_bytes(subprocess.check_output(gpg + ['--export']))
            config, archive = root / 'config.json', root / 'sample.deb'
            archive.write_bytes(b'fixture package')
            now = datetime.now(timezone.utc)
            manifest = {
                'schema': 1, 'organization': 'example.test', 'revision': 'test-1',
                'issued_at': now.isoformat(), 'expires_at': (now + timedelta(hours=1)).isoformat(),
                'waves': {'pilot': 'approved', 'general': 'paused'},
                'archives': [hashlib.sha256(archive.read_bytes()).hexdigest()],
            }
            payload.write_text(json.dumps(manifest), encoding='utf-8')
            subprocess.run(gpg + ['--output', str(signed), '--sign', str(payload)],
                           check=True, capture_output=True)
            config.write_text(json.dumps({'schema': 1, 'organization': 'example.test',
                                          'wave': 'pilot'}), encoding='utf-8')
            with (patch.multiple(update_waves, CONFIG=config, MANIFEST=signed, KEYRING=keyring),
                  patch.object(update_waves, 'trusted_file', side_effect=Path.read_bytes),
                  patch.object(update_waves, 'archive_digest',
                               side_effect=lambda path: hashlib.sha256(path.read_bytes()).hexdigest())):
                self.assertEqual(update_waves.authorize([str(archive)]), 'test-1')
                archive.write_bytes(b'changed package')
                with self.assertRaisesRegex(ValueError, 'diferem'):
                    update_waves.authorize([str(archive)])
                config.write_text(config.read_text().replace('pilot', 'general'), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'pausada'):
                    update_waves.authorize([str(archive)])
                signed.write_bytes(b'altered manifest')
                with self.assertRaisesRegex(ValueError, 'assinatura'):
                    update_waves.authorize([str(archive)])

    @unittest.skipUnless(os.geteuid() == 0, 'O teste de propriedade do DEB precisa de root')
    def test_verified_archive_requires_protected_file_and_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive = directory / 'payload.deb'
            archive.write_bytes(b'approved')
            self.assertEqual(update_waves.archive_digest(archive), hashlib.sha256(b'approved').hexdigest())
            archive.chmod(0o666)
            with self.assertRaises(ValueError):
                update_waves.archive_digest(archive)
            archive.chmod(0o644)
            directory.chmod(0o777)
            with self.assertRaises(ValueError):
                update_waves.archive_digest(archive)
            directory.chmod(0o700)
            link = directory / 'linked.deb'
            link.symlink_to(archive)
            with self.assertRaises(OSError):
                update_waves.archive_digest(link)

    @unittest.skipUnless(Path('/usr/bin/dpkg-deb').is_file(), 'dpkg-deb necessário')
    def test_managed_transaction_without_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            control = directory / 'package/DEBIAN/control'
            control.parent.mkdir(parents=True)
            control.write_text('Package: linuxbr-wave-fixture\nVersion: 1.0\nArchitecture: all\n'
                               'Maintainer: Linux BR\nDescription: Pacote de teste\n', encoding='utf-8')
            archive = directory / 'sample.deb'
            subprocess.run(['/usr/bin/dpkg-deb', '--build', '--root-owner-group',
                            str(control.parent.parent), str(archive)], check=True, capture_output=True)
            with (patch.object(snapshot_service, 'authorize', return_value='revision-1'),
                  patch.object(snapshot_service, 'read_json', return_value={}),
                  patch.object(Path, 'exists', return_value=False),
                  patch.object(snapshot_service, 'create_snapshot') as snapshot):
                with self.assertRaisesRegex(ValueError, 'destino de recuperação'):
                    snapshot_service.before_upgrade([str(archive)])
                snapshot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
