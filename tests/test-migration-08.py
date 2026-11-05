#!/usr/bin/python3
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from migration_backend import prepare, save_report, transfer
import migration_backend as migration
from unittest.mock import patch


class ImportFiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.source = self.base/'Documentos do Windows'; self.source.mkdir()
        self.destination = self.base/'Destino'; self.destination.mkdir()
        self.file = self.source/'ação e açúcar.txt'; self.file.write_bytes('conteúdo brasileiro\n'.encode())

    def plan(self): return prepare([self.source], self.destination)

    def test_copies_unicode_verifies_bytes_preserves_origin_and_empty_folders(self):
        (self.source/'Vazia').mkdir()
        before = self.file.read_bytes(); stamp = self.file.stat().st_mtime_ns
        report = transfer(self.plan())
        self.assertEqual(report['status'], 'completed'); self.assertEqual(len(report['copied']), 1)
        target = self.destination/self.source.name/self.file.name
        self.assertEqual(target.read_bytes(), before); self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(target.stat().st_mtime_ns, stamp)
        self.assertEqual(report['copied'][0]['sha256'], hashlib.sha256(before).hexdigest())
        self.assertTrue((self.destination/self.source.name/'Vazia').is_dir())
        saved = Path(save_report(report, self.destination)); self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(saved.read_text())['status'], 'completed')

    def test_conflict_policies_keep_skip_and_replace(self):
        first = transfer(self.plan()); self.assertEqual(first['status'], 'completed')
        self.file.write_text('nova versão')
        skipped = transfer(self.plan(), 'skip'); self.assertEqual(len(skipped['skipped']), 1)
        old = self.destination/self.source.name/self.file.name
        self.assertNotEqual(old.read_text(), self.file.read_text())
        kept = transfer(self.plan(), 'keep'); self.assertEqual(len(kept['copied']), 1)
        self.assertIn('(2)', kept['copied'][0]['path'])
        replaced = transfer(self.plan(), 'replace'); self.assertEqual(len(replaced['copied']), 1)
        self.assertEqual(old.read_text(), self.file.read_text())
        previous = replaced['copied'][0]['previous_copy']
        self.assertIsNotNone(previous)
        self.assertNotEqual((self.destination/previous).read_text(), self.file.read_text())

    def test_rejects_overlapping_roots_and_duplicate_sources(self):
        for target in (self.source, self.source/'Dentro'):
            target.mkdir(exist_ok=True)
            with self.assertRaises(ValueError): prepare([self.source], target)
        with self.assertRaises(ValueError): prepare([self.source, self.source], self.destination)

    def test_never_follows_source_links_or_special_files(self):
        outside = self.base/'fora.txt'; outside.write_text('preservado')
        (self.source/'atalho').symlink_to(outside)
        os.mkfifo(self.source/'fila')
        plan = self.plan(); self.assertEqual(len(plan['files']), 1); self.assertEqual(len(plan['skipped']), 2)
        self.assertEqual(transfer(plan)['status'], 'completed'); self.assertEqual(outside.read_text(), 'preservado')

    def test_changed_source_is_reported_without_publishing(self):
        plan = self.plan(); self.file.write_bytes(b'alterado')
        result = transfer(plan); self.assertEqual(result['status'], 'partial'); self.assertEqual(len(result['errors']), 1)
        self.assertFalse((self.destination/self.source.name/self.file.name).exists())

    def test_changed_source_with_restored_timestamp_is_not_missed(self):
        self.file.write_bytes(b'antes'); stamp = self.file.stat()
        plan = self.plan(); self.file.write_bytes(b'novo!'); os.utime(self.file, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        report = transfer(plan)
        self.assertEqual(report['status'], 'partial'); self.assertEqual(report['copied'], [])

    def test_replacement_captures_concurrent_change_without_overwriting_it(self):
        transfer(self.plan()); target = self.destination/self.source.name/self.file.name
        plan = self.plan(); real = migration.rename_noreplace; changed = False
        def race(source_fd, source_name, target_fd, target_name):
            nonlocal changed
            if source_name == self.file.name and target_name.startswith('.linuxbr-anterior-') and not changed:
                changed = True; stamp = target.stat(); target.write_bytes(b'n' * stamp.st_size)
                os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            return real(source_fd, source_name, target_fd, target_name)
        with patch.object(migration, 'rename_noreplace', side_effect=race): report = transfer(plan, 'replace')
        self.assertTrue(changed); self.assertEqual(report['status'], 'partial')
        self.assertEqual(target.read_bytes(), b'n' * self.file.stat().st_size)

    def test_cancel_after_capturing_destination_restores_the_previous_name(self):
        transfer(self.plan()); target = self.destination/self.source.name/self.file.name; before = target.read_bytes()
        plan = self.plan(); real = migration.rename_noreplace; cancel = threading.Event()
        def intercept(source_fd, source_name, target_fd, target_name):
            result = real(source_fd, source_name, target_fd, target_name)
            if target_name.startswith('.linuxbr-anterior-'): cancel.set()
            return result
        with patch.object(migration, 'rename_noreplace', side_effect=intercept): report = transfer(plan, 'replace', cancel=cancel)
        self.assertEqual(report['status'], 'cancelled'); self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(target.parent.glob('.linuxbr-anterior-*')), [])

    def test_destination_link_is_not_followed_or_overwritten(self):
        target = self.destination/self.source.name; target.mkdir()
        outside = self.base/'arquivo protegido'; outside.write_text('preservado')
        (target/self.file.name).symlink_to(outside)
        result = transfer(self.plan(), 'replace')
        self.assertEqual(result['status'], 'partial'); self.assertEqual(outside.read_text(), 'preservado')
        self.assertTrue((target/self.file.name).is_symlink())

    def test_replaced_source_parent_cannot_escape_the_held_root(self):
        folder = self.source/'Pasta'; folder.mkdir(); (folder/'outro.txt').write_text('dentro')
        plan = self.plan(); folder.rename(self.source/'Pasta anterior')
        outside = self.base/'Externa'; outside.mkdir(); (outside/'outro.txt').write_text('fora')
        folder.symlink_to(outside, target_is_directory=True)
        result = transfer(plan)
        self.assertEqual(result['status'], 'partial'); self.assertEqual((outside/'outro.txt').read_text(), 'fora')
        self.assertFalse((self.destination/self.source.name/'Pasta'/'outro.txt').exists())

    def test_cancel_mid_file_removes_only_its_temporary_copy(self):
        self.file.write_bytes(b'a' * (3*1024*1024)); plan = self.plan(); cancel = threading.Event()
        result = transfer(plan, cancel=cancel, notify=lambda info: cancel.set())
        self.assertEqual(result['status'], 'cancelled'); self.assertEqual(result['copied'], [])
        self.assertEqual(self.file.stat().st_size, 3*1024*1024)
        self.assertEqual(list(self.destination.rglob('.linuxbr-import-*')), [])
        self.assertFalse((self.destination/self.source.name/self.file.name).exists())

    def test_rejects_missing_space_and_unknown_conflict_policy(self):
        plan = self.plan(); plan['enough_space'] = False
        with self.assertRaises(ValueError): transfer(plan)
        with self.assertRaises(ValueError): transfer(plan, 'inventada')


if __name__ == '__main__': unittest.main()
