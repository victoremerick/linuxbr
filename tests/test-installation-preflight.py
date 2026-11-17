#!/usr/bin/env python3
"""Regression checks for the read-only installer preflight."""

import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import mock_open, patch


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'packages/linuxbr-calamares-settings/desktop-installation/preflight.py'
spec = importlib.util.spec_from_file_location('preflight', HELPER)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class StorageTests(TestCase):
    def test_volume_types_and_extents(self):
        rows = {'blockdevices': [
            dict(type='loop', path='/dev/loop0'),
            dict(type='disk', path='/dev/vda', size=64 * 1024**3, model=' Disco virtual  ',
                 vendor='Teste', tran='virtio', children=[
                     dict(type='part', path='/dev/vda1', fstype='BitLocker', size=32 * 1024**3, start=2048),
                     dict(type='part', path='/dev/vda2', fstype='crypto_LUKS', size=8 * 1024**3, start=2048 + 32 * 2**21),
                     dict(type='part', path='/dev/vda3', fstype='ntfs', size=8 * 1024**3, start=2048 + 40 * 2**21),
                 ]),
        ]}
        with patch.object(preflight, 'hibernation', return_value='hibernated') as test:
            disk, = preflight.storage_model(rows)
        self.assertEqual(disk['model'], 'Disco virtual')
        self.assertEqual(disk['vendor'], 'Teste')
        self.assertEqual(disk['transport'], 'virtio')
        self.assertEqual(disk['volumes'][0]['start'], 1024**2)
        self.assertEqual([row['protection'] for row in disk['volumes']],
                         ['bitlocker', 'luks', 'hibernated'])
        test.assert_called_once_with('/dev/vda3')

    def test_hibernation_reads_only_a_bounded_header(self):
        for data, status in [(b'HIBR' + bytes(4092), 'hibernated'),
                             (bytes(4096), 'inactive'), (b'', 'unknown')]:
            with (
                self.subTest(status=status),
                patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFBLK)),
                patch.object(preflight.subprocess, 'Popen') as command,
            ):
                child = command.return_value.__enter__.return_value
                child.stdout = mock_open(read_data=data)()
                self.assertEqual(preflight.hibernation('/dev/vda1'), status)
                arguments = command.call_args.args[0]
                self.assertIn('/usr/bin/ntfscat', arguments)
                self.assertNotIn('--readwrite', arguments)
                child.stdout.read.assert_called_once_with(4096)

    def test_reject_paths_outside_block_devices(self):
        with (
            patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG)),
            patch.object(preflight.subprocess, 'Popen') as command,
        ):
            self.assertEqual(preflight.hibernation('/tmp/plain'), 'unknown')
            self.assertEqual(preflight.hibernation('/dev/null'), 'unknown')
        command.assert_not_called()


if __name__ == '__main__':
    main()
