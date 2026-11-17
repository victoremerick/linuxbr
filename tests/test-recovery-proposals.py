#!/usr/bin/env python3
"""Exercise the new recovery actions without writing to connected disks."""

from contextlib import nullcontext
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'packages'
sys.path[:0] = [str(SOURCE / 'linuxbr-system/files/usr/lib/linuxbr-system'),
                str(SOURCE / 'linuxbr-boot-tools/files/usr/lib/linuxbr-boot')]

import backup_validation as backup
import post_update
import profile_repair as profile
import recovery_compare
import recovery_media as media
import recovery_timeline as timeline
import reinstall_plan
import update_recovery


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')


@unittest.skipIf(os.geteuid() != 0, 'as cópias sintéticas têm a propriedade da raiz')
class Compare(unittest.TestCase):
    def test_changes_and_privacy(self):
        with tempfile.TemporaryDirectory() as directory:
            original, updated = (Path(directory) / name for name in ('before', 'after'))
            for root, version, message in ((original, '1.0', 'segredo-exemplo-A'),
                                           (updated, '2.0', 'segredo-exemplo-B')):
                write(root / 'var/lib/dpkg/status',
                      f'Package: parte\nArchitecture: amd64\nVersion: {version}\nStatus: install ok installed\n')
                write(root / 'etc/default/locale', message)
                (root / 'etc/systemd/system').mkdir(parents=True)
            (updated / 'etc/systemd/system/bloco.service').symlink_to('/dev/null')
            result = recovery_compare.compare_folders(original, updated)
            self.assertEqual(result['packages']['changes'][0]['before'], '1.0')
            self.assertEqual(result['packages']['changes'][0]['after'], '2.0')
            self.assertEqual(result['services']['changes'][0]['after'], 'Mascarado')
            self.assertEqual(result['configuration']['changes'][0]['name'], 'etc/default/locale')
            self.assertNotIn('segredo-exemplo', json.dumps(result))
            self.assertEqual(len(recovery_compare.delta({}, {str(i): i for i in range(90)})['changes']), 40)

    def test_different_installation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory)
            point = backup / 'timeshift/snapshots/2026-11-17_13-15-20'
            write(point / 'info.json', json.dumps({'type': 'rsync', 'sys-uuid': 'original'}))
            with self.assertRaisesRegex(ValueError, 'outra instalação'):
                recovery_compare.eligible(backup, point.name, 'different', b'1', b'2')


class BootCheck(unittest.TestCase):
    def test_dpkg_exact_version_and_architecture(self):
        target = {'package': 'base-files', 'version': '1:2.0~v3', 'architecture': 'amd64'}
        with patch.object(post_update, 'command', return_value='base-files\tamd64\t1:2.0~v3\tinstalled'):
            self.assertTrue(post_update.installed_targets([target]))
            self.assertFalse(post_update.installed_targets([{**target, 'architecture': 'i386'}]))
            self.assertFalse(post_update.installed_targets([{**target, 'version': '3.0'}]))

    def test_failed_report_retried_without_new_assessment(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            write(state / 'last-managed.json', json.dumps({'status': 'created', 'revision': 'revision-1',
                                                           'point_comment': 'p', 'targets': []}))
            with (patch.object(post_update, 'STATE', state), patch.object(post_update, 'LIVE', state / 'live'),
                  patch.object(post_update, 'snapshot_lock', nullcontext),
                  patch.object(post_update, 'restored_revisions', return_value=[]),
                  patch.object(post_update, 'came_from_earlier_boot', return_value=True),
                  patch.object(post_update, 'installed_targets', return_value=True) as packages,
                  patch.object(post_update, 'session_ready', return_value=True),
                  patch.object(post_update, 'network_ready', return_value=False),
                  patch.object(post_update, 'storage_ready', return_value=True),
                  patch.object(post_update, 'read_config', return_value={'endpoint': 'https://example.org'}),
                  patch.object(post_update, 'custom_health', return_value={}),
                  patch.object(post_update, 'request_json', side_effect=[OSError('offline'), {}, None]) as report):
                with self.assertRaisesRegex(OSError, 'offline'):
                    post_update.run()
                self.assertFalse(json.loads((state / post_update.REPORT).read_text())['notified'])
                post_update.run()
                post_update.run()
                self.assertTrue(json.loads((state / post_update.REPORT).read_text())['notified'])
                self.assertEqual(packages.call_count, 1)
                self.assertEqual(report.call_count, 2)
                self.assertEqual(report.call_args.args[-1], {'revision': 'revision-1', 'state': 'failed'})


class Reinstall(unittest.TestCase):
    def test_inspection_identifies_separate_home_and_integrated_home(self):
        root_uuid, home_uuid = ('ba518afa-e628-4ee7-8a08-9a4595a97cae', '3a264751-90e3-46de-9a47-7725fea5f44f')
        devices = [{'path': '/dev/sda'+str(number), 'uuid': uuid, 'fstype': 'ext4',
                    'type': 'part', 'mountpoints': [None], 'ro': False}
                   for number, uuid in enumerate((root_uuid, home_uuid), start=1)]
        fstab = f'UUID={root_uuid} / ext4 defaults 0 1\nUUID={home_uuid} /home ext4 defaults 0 2\n'
        passwd = ('ana:x:1000:1000:Ana:/home/ana:/bin/bash\n'
                  'leo:x:1001:1001:Leo:/dados/leo:/bin/bash\n'
                  'root:x:0:0:root:/root:/bin/bash\n')
        report = reinstall_plan.prepare(devices, devices[0], fstab.encode(), passwd.encode())
        self.assertEqual([row['name'] for row in report['users']], ['ana', 'leo'])
        self.assertEqual(report['volumes'][0]['volume'], '/dev/sda2')
        self.assertEqual(report['volumes'][0]['kind'], 'independent')
        self.assertEqual(report['volumes'][1]['kind'], 'root')
        with tempfile.TemporaryDirectory() as live:
            with (patch.object(update_recovery, 'LIVE', Path(live)),
                  patch.object(update_recovery.os, 'geteuid', return_value=0),
                  patch.object(reinstall_plan, 'inspect', return_value=report),
                  patch.object(sys, 'argv', ['backend', 'reinstall-plan', '--uuid', root_uuid]),
                  patch('sys.stdout', new_callable=io.StringIO) as output):
                self.assertEqual(update_recovery.main(), 0)
                self.assertEqual(json.loads(output.getvalue()), report)


class Profile(unittest.TestCase):
    def test_selected_reset_and_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config, state = root / 'config', root / 'state'
            write(config / 'kwinrc', '[Window] original')
            write(config / 'plasmashellrc', '[Panel] original')
            with patch.object(profile, 'CONFIG', config), patch.object(profile, 'STATE', state):
                profile.queue(['panel'])
                self.assertTrue((config / 'plasmashellrc').exists())
                profile.apply()
                self.assertFalse((config / 'plasmashellrc').exists())
                self.assertTrue((config / 'kwinrc').exists())
                self.assertFalse((state / 'pending.json').exists())
                profile.queue(['panel'], profile.saved()[0])
                profile.apply()
                self.assertEqual((config / 'plasmashellrc').read_text(), '[Panel] original')
                self.assertEqual(len(profile.saved()), 2)

    def test_link_never_read_or_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'config'
            config.mkdir()
            write(root / 'other', 'original')
            (config / 'kwinrc').symlink_to(root / 'other')
            with patch.object(profile, 'CONFIG', config), patch.object(profile, 'STATE', root / 'state'):
                profile.queue(['windows'])
                with self.assertRaises(OSError):
                    profile.apply()
            self.assertTrue((config / 'kwinrc').is_symlink())
            self.assertEqual((root / 'other').read_text(), 'original')


class Media(unittest.TestCase):
    def test_destination_and_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            drive = temp / 'mounted'
            drive.mkdir()
            usb = {'type': 'disk', 'tran': 'usb', 'children': [
                {'partn': 1, 'label': 'Ventoy', 'mountpoints': [str(drive)], 'path': '/dev/sdb1'},
                {'partn': 2, 'label': 'VTOYEFI', 'fstype': 'vfat'}]}
            self.assertEqual(media.ventoy_volumes([usb]), [(str(drive), '/dev/sdb1')])
            self.assertFalse(media.ventoy_volumes([{**usb, 'tran': 'nvme'}]))
            image = temp / 'linuxbr-desktop-qa.iso'
            image.write_bytes(b'\0' * (16 * 2048 + 1) + b'CD001')
            checksum = hashlib.sha256(image.read_bytes()).hexdigest()
            with (patch.object(media, 'destinations', return_value=media.ventoy_volumes([usb])),
                   patch.object(media.os.path, 'ismount', return_value=True)):
                with self.assertRaisesRegex(ValueError, 'não corresponde'):
                    media.prepare(image, '0' * 64, drive)
                self.assertFalse(list(drive.iterdir()))
                result = media.prepare(image, checksum, drive)
            self.assertEqual((result / image.name).read_bytes(), image.read_bytes())
            self.assertIn('modo Live', (result / 'LEIA-ME.txt').read_text())
            self.assertIn(checksum, (result / 'SHA256SUMS').read_text())


class Timeline(unittest.TestCase):
    def test_sorted_union_and_missing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            apt = Path(folder) / 'history.log'
            write(apt, 'Start-Date: 2026-11-17  12:00:00\nUpgrade: sys:amd64 (1.2, 1.3)\n'
                       'Install: auto:amd64 (1, automatic), teste:amd64 (2)\nEnd-Date: 2026-11-17  12:01:00\n')
            events, readable = timeline.updates(apt)
            self.assertTrue(readable)
            self.assertIn('atualizados 1, instalados 2', events[0][2])
            time = datetime.fromisoformat('2026-11-17 12:10:00').astimezone()
            peripheral = [(time, 'peripherals', 'New USB device found')]
            with (patch.object(timeline, 'updates', return_value=(events, True)),
                  patch.object(timeline, 'boots', return_value=([], False)),
                  patch.object(timeline, 'log_events', side_effect=[(peripheral, True), ([], True)])):
                output = timeline.render()
            self.assertLess(output.index('New USB device'), output.index('atualizados'))
            self.assertIn('Registros indisponíveis para esta conta: Inicializações', output)


class Backup(unittest.TestCase):
    def test_repo_failure_skips_restore_and_preserves_date(self):
        with tempfile.TemporaryDirectory() as folder:
            result = Path(folder) / 'result.json'
            backup.write(result, {'repository': 'qa', 'recovered_at': '2026-11-16'})
            with patch.object(backup, 'RESULT', result):
                stages = []
                def run(args, **options):
                    stages.append(args)
                    self.assertEqual(options['input'], b'secret\n')
                    return subprocess.CompletedProcess(args, 17)
                data = backup.validate('qa', '/home/qa/test.txt', b'secret\n', run)
                self.assertEqual(len(stages), 1)
                self.assertIn('--read-data-subset=50M', stages[0])
                self.assertEqual(data['recovered_at'], '2026-11-16')
                self.assertFalse(data['file'])
                self.assertEqual(result.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.environ.get('LINUXBR_QA_RESTIC'), 'informe o binário Debian Restic na variável LINUXBR_QA_RESTIC')
    def test_real_restic_dump_and_sample(self):
        restic = os.environ['LINUXBR_QA_RESTIC']
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            repo = str(temp / 'repo')
            sample = temp / 'data' / 'arquivo de teste.txt'
            write(sample, 'Linux BR\n')
            password = b'temporary-qa\n'
            def command(repository, *args):
                return [restic, '--repo', repository, '--password-file', '/dev/stdin', *args]
            for args in [('init',), ('backup', str(sample.parent))]:
                subprocess.run(command(repo, *args), check=True, input=password, capture_output=True)
            with patch.object(backup, 'command', command), patch.object(backup, 'RESULT', temp / 'result'):
                result = backup.validate(repo, str(sample), password)
                missing = backup.validate(repo, str(sample.with_name('missing.txt')), password)
            self.assertTrue(result['index_and_sample'])
            self.assertTrue(result['file'])
            self.assertTrue(result['recovered_at'])
            self.assertTrue(missing['index_and_sample'])
            self.assertFalse(missing['file'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
