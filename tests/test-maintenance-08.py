#!/usr/bin/python3
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import protection_status as protection
import storage_cleanup as cleanup
import troubleshooting


class Maintenance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.home = self.base/'home'; self.home.mkdir()
        self.cache = self.home/'.cache'; self.cache.mkdir(); self.data = self.home/'.local/share'; self.data.mkdir(parents=True)
        self.config = self.home/'.config'; self.config.mkdir()
        env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_CACHE_HOME': str(self.cache),
                                     'XDG_DATA_HOME': str(self.data), 'XDG_CONFIG_HOME': str(self.config)})
        env.start(); self.addCleanup(env.stop)

    def test_kup_native_settings_and_last_success(self):
        path = self.config/'kuprc'; destination = self.home/'Cópias'; destination.mkdir()
        fields = {'Description': 'Meus documentos', 'Backup type': '0', 'Destination type': '0',
                  'Filesystem destination path': destination.as_uri(), 'Last complete backup': '2026,11,3,18,20,0'}
        for key, value in fields.items():
            subprocess.run(['kwriteconfig6', '--file', str(path), '--group', 'Plan/1', '--key', key, value], check=True)
        result = protection.backup_plans(path, volumes=[])
        self.assertEqual(len(result), 1); self.assertEqual(result[0]['name'], 'Meus documentos')
        self.assertEqual(result[0]['type'], 'versions'); self.assertEqual(result[0]['destination'], str(destination))
        self.assertTrue(result[0]['available']); self.assertTrue(result[0]['last_complete'].startswith('2026-11-03T18:20'))
        self.assertIsNone(protection.kconfig_date('data inválida'))

    def test_disconnected_external_destination_is_not_claimed_available(self):
        path = self.config/'kuprc'; path.write_text('[Plan/1]\nDescription=Externo\n')
        values = {'Destination type': '1', 'External drive UUID': 'abc-123', 'External drive destination path': 'Cópias'}
        reader = lambda group, key, default: values.get(key, default)
        result = protection.backup_plans(path, volumes=[], read_key=reader)[0]
        self.assertFalse(result['available']); self.assertIsNone(result['destination'])
        point = self.home/'montado'; point.mkdir(); (point/'Cópias').mkdir()
        result = protection.backup_plans(path, volumes=[{'uuid': 'abc-123', 'target': str(point)}], read_key=reader)[0]
        self.assertTrue(result['available'])

    def test_kconfig_real_fractional_seconds_and_time_zones(self):
        from datetime import datetime, timezone
        self.assertEqual(datetime.fromisoformat(protection.kconfig_date('2026,11,3,18,20,0.123,UTC').replace('Z', '+00:00')),
                         datetime(2026, 11, 3, 18, 20, 0, 123000, tzinfo=timezone.utc))
        value = protection.kconfig_date('2026,11,3,18,20,0.005,America/Sao_Paulo')
        self.assertTrue(value.endswith('-03:00')); self.assertIn('.005', value)
        self.assertIsNone(protection.kconfig_date('2026,11,3,18,20,0,Invalid/Zone'))
        self.assertIsNone(protection.kconfig_date('2026,11,3,18,20,Infinity,UTC'))
        self.assertIsNone(protection.kconfig_date('2026,11,3,18,20,NaN,UTC'))
        rounded = protection.kconfig_date('2026,11,3,18,20,0.0005,UTC')
        self.assertEqual(datetime.fromisoformat(rounded.replace('Z', '+00:00')).microsecond, 1000)

    def test_disabled_backup_is_reported_even_when_a_success_exists(self):
        path = self.config/'kuprc'
        path.write_text('[General]\nBackups enabled=false\n[Plan/1]\nDescription=Antigo\n')
        reader = lambda group, key, default: '2026,11,3,18,20,0.123,UTC' if key == 'Last complete backup' else default
        result = protection.backup_plans(path, volumes=[], read_key=reader)[0]
        self.assertFalse(result['enabled']); self.assertIsNotNone(result['last_complete'])

    def test_expired_and_current_indexes_are_distinguished(self):
        directory = self.base/'lists'; directory.mkdir()
        now = datetime.now(timezone.utc)
        for name, days in [('linuxbr_expired_InRelease', -1), ('linuxbr_current_InRelease', 7)]:
            (directory/name).write_text('Valid-Until: ' + format_datetime(now+timedelta(days=days)) + '\n')
        result = {item['index']: item for item in protection.index_validity(directory)}
        self.assertTrue(result['linuxbr_expired_InRelease']['expired']); self.assertFalse(result['linuxbr_current_InRelease']['expired'])

    def test_https_sources_ignore_disabled_and_credentials_rejected(self):
        directory = self.base/'sources'; directory.mkdir()
        (directory/'linuxbr.sources').write_text('Types: deb\nURIs: https://localhost:8443\n\nTypes: deb\nEnabled: no\nURIs: https://disabled.test\n')
        self.assertEqual(protection.repository_addresses(directory), ['https://localhost:8443'])
        with self.assertRaises(ValueError): protection.check_repository_tls('https://user:password@localhost')

    def test_cleanup_only_old_cache_and_keeps_personal_data(self):
        old = self.cache/'old.bin'; old.write_bytes(b'cache'); os.utime(old, (time.time()-90000,)*2)
        recent = self.cache/'recent.bin'; recent.write_text('em uso')
        document = self.home/'Documentos'; document.mkdir(); (document/'arquivo').write_text('pessoal')
        (self.cache/'link').symlink_to(document, target_is_directory=True)
        plan = cleanup.scan('cache'); result = cleanup.clean(plan)
        self.assertFalse(old.exists()); self.assertTrue(recent.exists()); self.assertTrue((document/'arquivo').exists())
        self.assertTrue((self.cache/'link').is_symlink()); self.assertGreaterEqual(result['removed'], 1)

    def test_changed_cache_item_is_preserved_after_preview(self):
        item = self.cache/'item'; item.write_text('antes'); os.utime(item, (time.time()-90000,)*2)
        plan = cleanup.scan('cache'); item.write_text('depois')
        result = cleanup.clean(plan); self.assertEqual(item.read_text(), 'depois'); self.assertEqual(result['changed_or_retained'], 1)

    def test_protects_data_directory_even_if_nested_in_cache(self):
        data = self.cache/'dados'; data.mkdir(); item = data/'conta'; item.write_text('sessão'); os.utime(item, (time.time()-90000,)*2)
        with patch.dict(os.environ, {'XDG_DATA_HOME': str(data)}):
            result = cleanup.clean(cleanup.scan('cache'))
        self.assertTrue(item.exists()); self.assertEqual(result['removed'], 0)

    def test_refuses_cache_root_that_is_home_or_a_link(self):
        with patch.dict(os.environ, {'XDG_CACHE_HOME': str(self.home)}):
            with self.assertRaises(ValueError): cleanup.scan('cache')
        linked = self.home/'linkcache'; linked.symlink_to(self.cache)
        with patch.dict(os.environ, {'XDG_CACHE_HOME': str(linked)}):
            with self.assertRaises(ValueError): cleanup.scan('cache')

    def trash(self):
        trash = self.data/'Trash'; (trash/'files').mkdir(parents=True); (trash/'info').mkdir()
        item = trash/'files'/'uma pasta'; item.mkdir(); (item/'arquivo').write_text('descartado')
        info = trash/'info'/'uma pasta.trashinfo'; info.write_text('[Trash Info]\nPath=/origem\n')
        return trash, item, info

    def test_trash_removes_contents_before_metadata_without_following_links(self):
        trash, item, info = self.trash(); outside = self.home/'fora'; outside.write_text('preservado')
        (item/'link').symlink_to(outside)
        result = cleanup.clean(cleanup.scan('trash'))
        self.assertFalse(item.exists()); self.assertFalse(info.exists()); self.assertEqual(outside.read_text(), 'preservado')
        self.assertEqual(result['errors'], [])

    def test_trash_keeps_restore_metadata_when_a_file_changed(self):
        trash, item, info = self.trash(); plan = cleanup.scan('trash'); (item/'arquivo').write_text('modificado depois')
        result = cleanup.clean(plan)
        self.assertTrue(item.exists()); self.assertTrue(info.exists()); self.assertGreater(result['changed_or_retained'], 0)

    def test_diagnostics_do_not_turn_a_failed_command_into_success(self):
        with patch.object(troubleshooting.shutil, 'which', return_value='/usr/bin/tool'), patch.object(troubleshooting, 'command', return_value=(1, '', 'sem conexão')):
            report = troubleshooting.diagnose('Som e microfone')
        self.assertTrue(all(item['status'] == 'attention' for item in report['results']))


if __name__ == '__main__': unittest.main()
