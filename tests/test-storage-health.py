#!/usr/bin/env python3
"""Exercise storage health collection without accessing any physical device."""

from contextlib import contextmanager
from pathlib import Path
import stat
import sys
import tempfile
import time
from unittest import TestCase, main
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parents[1]
MODULES = BASE / 'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'
sys.path.insert(0, str(MODULES))
import health


@contextmanager
def mock_dbus():
    import dbus
    with patch.object(dbus, 'Interface') as interface:
        yield interface


class StorageHealthTests(TestCase):
    def test_ata_alerts_with_unknown_counter(self):
        properties = dict(SmartEnabled=True, SmartUpdated=10, SmartNumBadSectors=40,
                          SmartNumAttributesFailing=2, SmartNumAttributesFailedInThePast=-1,
                          SmartFailing=True, SmartTemperature=300)
        current = health.sample(health.ATA, properties, now=15)
        self.assertAlmostEqual(current['temperature'], 26.9)
        self.assertNotIn('attributes_failed_before', current)
        notices = health.alerts({'read_at': 2, 'bad_sectors': 25}, current)
        self.assertIn('SMART informa possível falha da unidade.', notices)
        self.assertTrue(any('15' in text for text in notices))

    def test_nvme_and_ata_collection_are_read_only(self):
        now = int(time.time())
        ata, nvme = '/ata', '/nvme'
        objects = {
            ata: {health.PREFIX + 'Drive': {'Serial': 'private-A', 'Model': 'ATA'},
                  health.ATA: dict(SmartEnabled=True, SmartUpdated=now, SmartSupported=True)},
            nvme: {health.PREFIX + 'Drive': {'Serial': 'private-N', 'Model': 'NVMe'},
                   health.NVME: dict(SmartUpdated=now, SmartTemperature=310,
                                     SmartCriticalWarning=['temperature'])},
        }
        bus, manager = MagicMock(), MagicMock()
        bus.get_object.side_effect = lambda service, path, **options: path
        manager.GetManagedObjects.return_value = objects
        with tempfile.TemporaryDirectory() as folder, mock_dbus() as interface:
            ata_disk, nvme_disk = MagicMock(), MagicMock()
            interface.side_effect = lambda device, protocol: ata_disk if device == ata else nvme_disk
            nvme_disk.SmartGetAttributes.return_value = {'media_errors': 4, 'percent_used': 25}
            record = health.History(Path(folder) / 'health.json')
            with patch.object(health, 'History', return_value=record):
                results = health.collect(bus, manager, objects)
            self.assertEqual({call[0] for call in ata_disk.mock_calls}, {'SmartUpdate'})
            self.assertEqual({call[0] for call in nvme_disk.mock_calls}, {'SmartUpdate', 'SmartGetAttributes'})
            self.assertTrue(ata_disk.SmartUpdate.call_args.args[0]['nowakeup'])
            self.assertTrue(nvme_disk.SmartUpdate.call_args.args[0]['auth.no_user_interaction'])
            self.assertEqual(results[1]['samples'][0]['media_errors'], 4)
            self.assertEqual(results[1]['samples'][0]['percent_used'], 25)
            self.assertTrue(any('temperatura' in line for line in results[1]['alerts']))
            self.assertNotIn('private-', record.path.read_text())

    def test_history_keeps_order_and_never_merges_duplicate_identities(self):
        now = int(time.time())
        identity = health.drive_identity({'WWN': 'fixture'})
        drive = {'id': identity, 'name': 'Disco de teste', 'protocol': 'NVMe'}
        with tempfile.TemporaryDirectory() as folder:
            record = health.History(Path(folder) / 'health.json')
            for date in (now - 20, now - 20, now, now - 10):
                record.record([dict(drive, current={'read_at': date, 'media_errors': 3})], now=now)
            new_value = dict(drive, current={'read_at': now + 1, 'media_errors': 9})
            history, identities = record.record([new_value, new_value], now=now)
            self.assertEqual(identities[identity], 2)
            self.assertEqual([row['read_at'] for row in history[identity]['samples']], [now - 20, now])
            self.assertEqual(stat.S_IMODE(record.path.stat().st_mode), 0o600)
            record.record([], now=now + (health.HISTORY_DAYS + 1) * 86_400)
            self.assertEqual(record.read(), {})

    def test_live_dialog_handles_readings_and_unsupported_drives(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PyQt6.QtWidgets import QApplication
        from health_dialog import HealthDialog
        app = QApplication.instance() or QApplication([])
        empty = HealthDialog([])
        self.assertIn('Nenhuma unidade', empty.status.text())
        device = {'name': 'Disco', 'node': '/dev/nvme0n1', 'protocol': 'NVMe',
                  'enabled': True, 'connected': True, 'history_available': True,
                  'current': None, 'alerts': ['A unidade informou erros de mídia.'],
                  'samples': [{'read_at': 10, 'media_errors': 2}, {'read_at': 20, 'media_errors': 4}]}
        dialog = HealthDialog([device])
        self.assertEqual(dialog.table.rowCount(), 2)
        self.assertIn('erros de mídia', dialog.status.text())
        self.assertEqual(dialog.table.item(0, 2).text(), '4')


if __name__ == '__main__':
    main()
