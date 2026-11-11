"""Exercise rollback preflight, restore sequencing and local wave holds."""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
sys.path.insert(0, str(ROOT / 'packages/linuxbr-boot-tools/files/usr/lib/linuxbr-boot'))
import snapshot_service as snapshots
import update_recovery as recovery


class GuidedRecovery(unittest.TestCase):
    uuid = 'd99dab1f-4da4-4aa8-91a7-5c0353124897'
    revision = 'qa-1'
    point = 'timeshift/snapshots/2026-11-10_18-00-01'

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.folder = self.root / self.point / 'localhost'
        self.folder.mkdir(parents=True)
        self.fstab = f'UUID={self.uuid} / ext4 defaults 0 1\n'.encode()
        self.machine = b'a' * 32 + b'\n'
        self.database = b'Package: linuxbr-release\nVersion: 1.1.0\n'
        self.install = dict(status='created', revision=self.revision, point_comment='qa point',
                            dpkg_status_sha256=hashlib.sha256(self.database).hexdigest())
        files = {
            'etc/fstab': self.fstab,
            'etc/machine-id': self.machine,
            recovery.STATUS: self.database,
            f'{recovery.STATE}/{snapshots.HOLD_FILE}':
                json.dumps({'schema': 1, 'revisions': [self.revision]}).encode(),
        }
        for relative, data in files.items():
            path = self.folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (self.folder.parent / 'info.json').write_text(json.dumps(
            {'comments': 'qa point', 'type': 'rsync', 'sys-uuid': self.uuid}))
        (self.folder.parent / 'exclude.list').write_text('/home/*/**\n/root/**\n')
        original = Path.lstat

        def root_owned(path):
            current = original(path)
            return current.__class__((*current[:4], 0, *current[5:]))

        patcher = patch.object(Path, 'lstat', root_owned)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check_snapshot(self):
        def validated_holds(directory):
            return json.loads((directory / snapshots.HOLD_FILE).read_text())['revisions']

        with patch.object(recovery, 'held_revisions', side_effect=validated_holds):
            return recovery.verify_snapshot(self.root, self.point, self.install, self.fstab,
                                            self.machine, self.uuid)

    def test_snapshot_matches_machine_revision_and_exclusions(self):
        self.assertEqual(self.check_snapshot(), self.folder)
        (self.folder.parent / 'exclude.list').write_text('+ /home/qa/**\n/home/*/**\n/root/**\n')
        with self.assertRaisesRegex(ValueError, 'pastas pessoais'):
            self.check_snapshot()

    def test_dpkg_status_change_is_rejected(self):
        (self.folder / recovery.STATUS).write_bytes(self.database + b'changed')
        with self.assertRaisesRegex(ValueError, 'não conferem'):
            self.check_snapshot()

    def test_snapshot_symlink_is_rejected(self):
        path = self.folder / 'etc/fstab'
        path.unlink()
        path.symlink_to('/etc/fstab')
        with self.assertRaisesRegex(ValueError, 'proteção administrativa'):
            self.check_snapshot()

    def test_calamares_efi_mount_point_allows_the_root_group(self):
        path = self.root / 'boot/efi'
        path.mkdir(parents=True)
        path.chmod(0o775)
        original = Path.lstat

        def root_group(file):
            current = original(file)
            return current.__class__((*current[:5], 0, *current[6:]))

        with patch.object(Path, 'lstat', root_group):
            with self.assertRaisesRegex(ValueError, 'proteção administrativa'):
                recovery.trusted(self.root, 'boot/efi', directory=True)
            self.assertEqual(recovery.trusted(self.root, 'boot/efi', directory=True,
                                             root_group_mount=True), path)

    def test_restore_revalidates_token_and_merges_holds(self):
        target = {'path': '/dev/vda2', 'uuid': self.uuid}
        backup = {'path': '/dev/vdb1', 'uuid': '5e9fa1e5-eb91-4992-b43d-0ebf00b8be4f'}
        plan = dict(target=target, backup=backup, point=self.point.split('/')[-1],
                    held=['older'], verified_restores=['older'], revision=self.revision,
                    restored_status=self.install['dpkg_status_sha256'])
        results = self.root / 'rsync-exit-codes'
        results.write_text('23\n')
        with (patch.object(recovery, 'snapshot_lock', side_effect=nullcontext),
              patch.object(recovery, 'checksum_rsync_environment',
                           return_value=nullcontext(({'BASH_ENV': '/run/qa-rsync'}, results))),
              patch.object(recovery, 'inspect', return_value=plan),
              patch.object(recovery, 'mounted', side_effect=lambda *args, **kwargs: nullcontext(self.folder)),
              patch.object(recovery, 'save_holds') as hold,
              patch.object(recovery, 'save_restored_revisions') as receipt,
              patch.object(recovery, 'disks', return_value=[]),
              patch.object(recovery, 'device_for', return_value=target),
              patch.object(recovery.subprocess, 'run',
                           return_value=subprocess.CompletedProcess(['timeshift'], 0)) as native):
            with self.assertRaisesRegex(ValueError, 'estado mudou'):
                recovery.restore(self.uuid, 'f' * 64)
            native.assert_not_called()
            hold.assert_not_called()
            receipt.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'Timeshift não concluiu'):
                recovery.restore(self.uuid, recovery.plan_token(plan))
            receipt.assert_not_called()
            results.write_text('0\n')
            with patch.object(recovery, 'identifier', return_value='f' * 64):
                with self.assertRaisesRegex(ValueError, 'base de pacotes restaurada não confere'):
                    recovery.restore(self.uuid, recovery.plan_token(plan))
            receipt.assert_not_called()
            hold.reset_mock()
            recovery.restore(self.uuid, recovery.plan_token(plan))
            self.assertEqual(hold.call_count, 2)
            self.assertEqual(hold.call_args.args[0], ['older', self.revision])
            receipt.assert_called_once_with(['older', self.revision], self.folder / recovery.STATE)
            argv = native.call_args.args[0]
            self.assertEqual(argv[:5], ['/usr/bin/unshare', '--mount', '--propagation', 'private', '--'])
            self.assertIn('--skip-grub', argv)
            self.assertEqual(argv[argv.index('--target') + 1], self.uuid)
            self.assertEqual(argv[argv.index('--snapshot-device') + 1], 'UUID='+backup['uuid'])
            self.assertEqual(native.call_args.kwargs['env']['BASH_ENV'], '/run/qa-rsync')

    def test_noninteractive_bash_uses_checksum_hook(self):
        with (patch.object(snapshots, 'RUNTIME', self.root),
              snapshots.checksum_rsync_environment() as (extra, _)):
            loaded = subprocess.check_output(['/usr/bin/bash', '-c', 'type rsync'], text=True, env=extra)
            self.assertIn('/usr/bin/rsync --checksum', loaded)

    def test_suspended_wave_never_reaches_package_inspection(self):
        with (patch.object(snapshots.Path, 'exists', return_value=False),
              patch.object(snapshots, 'authorize', return_value=self.revision),
              patch.object(snapshots, 'held_revisions', return_value=[self.revision]),
              patch.object(snapshots, 'critical_upgrades') as upgrades):
            with self.assertRaisesRegex(ValueError, 'suspensa'):
                snapshots.before_upgrade(['/var/cache/apt/sample.deb'])
            upgrades.assert_not_called()

    def test_new_point_carries_hold_but_installed_system_restores_previous_holds(self):
        values = {'backup_device_uuid': self.uuid, 'btrfs_mode': False}
        with (patch.object(snapshots.Path, 'exists', return_value=False),
              patch.object(snapshots, 'authorize', return_value=self.revision),
              patch.object(snapshots, 'archive_targets', return_value=[{
                  'package': 'linuxbr-release', 'version': '1.1.0', 'architecture': 'all'}]),
              patch.object(snapshots, 'held_revisions', return_value=['older']),
              patch.object(snapshots, 'snapshot_lock', side_effect=nullcontext),
              patch.object(snapshots, 'read_json', return_value=values),
              patch.object(snapshots, 'save_holds') as holds,
              patch.object(snapshots, 'create_snapshot', return_value=0) as create):
            self.assertEqual(snapshots.before_upgrade(['/var/cache/apt/sample.deb']), 0)
            self.assertEqual(holds.call_args_list[0].args[0], ['older', self.revision])
            create.assert_called_once_with(['linuxbr-release'], self.revision, [{
                'package': 'linuxbr-release', 'version': '1.1.0', 'architecture': 'all'}])
            self.assertEqual(holds.call_args_list[1].args[0], ['older'])


if __name__ == '__main__':
    unittest.main()
