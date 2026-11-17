import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))

from batch_rename_backend import apply_plan, plan
from file_workflows_backend import State, compare_folders, find_files, names_to_review, verified_copy


class FileWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / 'origem'
        self.dst = self.root / 'destino'
        self.src.mkdir()
        self.dst.mkdir()
        self.state = State(self.root / 'state')

    def test_searches_multiple_folders_applies_filters_and_avoids_duplicates(self):
        report = self.src / 'Relatório.PDF'
        report.write_bytes(b'valid')
        (self.dst / 'relatório.txt').write_bytes(b'text')
        (self.dst / 'página.pdf').write_bytes(b'x')
        (self.src / 'link.pdf').symlink_to(self.dst / 'página.pdf')
        last_modified = report.stat().st_mtime
        result, limited = find_files([self.root, self.src], '*', 'pdf', 3, 8,
                                     last_modified - 5, last_modified + 5)
        self.assertEqual(result, [report])
        self.assertFalse(limited)

    def test_compare_includes_moved_and_missing_names_and_data_differences(self):
        (self.src / 'atual.txt').write_bytes(b'aa')
        (self.dst / 'atual.txt').write_bytes(b'bb')
        (self.src / 'novo.pdf').touch()
        (self.dst / 'antigo.pdf').touch()
        self.assertEqual(dict(compare_folders(self.src, self.dst, True)),
                         {'antigo.pdf': 'Somente na segunda pasta',
                          'atual.txt': 'Conteúdo diferente',
                          'novo.pdf': 'Somente na primeira pasta'})

    def test_verified_copy_resumes_and_never_replaces_an_existing_different_file(self):
        source = self.src / 'dados.bin'
        target = self.dst / source.name
        payload = b'Linux BR' * 170000
        source.write_bytes(payload)
        original = hashlib.sha256(payload).hexdigest()
        token = hashlib.sha256(os.fsencode(str(source) + '\0' + target.name)).hexdigest()[:32]
        partial = self.dst / f'.linuxbr-copy-{token}.part'
        partial.write_bytes(payload[:700000])
        self.state.mark_transfer(source, target, self.dst.stat())
        self.assertEqual(verified_copy(source, target, self.state), original)
        self.assertEqual(verified_copy(source, target, self.state), original)
        self.assertFalse(partial.exists())
        self.assertEqual(target.read_bytes(), payload)
        target.write_bytes(b'outro documento')
        with self.assertRaises(FileExistsError):
            verified_copy(source, target, self.state)
        self.assertEqual(target.read_bytes(), b'outro documento')

    def test_verified_copy_requires_original_mount_and_rejects_symlink(self):
        source = self.src / 'dados.bin'
        source.write_bytes(b'dados')
        target = self.dst / source.name
        self.state.mark_transfer(source, target, self.dst.stat())
        self.dst.rename(self.root / 'unidade')
        self.dst.mkdir()
        with self.assertRaisesRegex(ValueError, 'Reconecte'):
            verified_copy(source, target, self.state)
        self.assertFalse(target.exists())
        (self.dst / 'link.bin').symlink_to(source)
        with self.assertRaises(OSError):
            verified_copy(source, self.dst / 'link.bin')
        self.assertEqual(source.read_bytes(), b'dados')

    def test_windows_names_checks_reserved_characters_and_case(self):
        (self.dst / 'Relatorio.txt').touch()
        result = names_to_review([self.src / 'relatorio.TXT', self.src / 'CON.pdf',
                                  self.src / 'dados:atual', self.src / 'Normal.txt'], self.dst)
        self.assertEqual(len(result), 3)

    def test_batch_undo_preserves_files_with_conflicts_and_relocates_tags(self):
        source = self.src / 'origem.txt'
        source.write_text('original', encoding='utf-8')
        self.state.set_tag('Projeto', [source], True)
        rows = plan([source], '{nome}-{n}')
        apply_plan(rows, on_commit=lambda changes: self.state.remember('Renomeação', changes))
        renamed = rows[0][1]
        self.assertEqual(self.state.read()['tags']['Projeto'], [str(renamed)])
        snapshot = self.state.read()['undo'][0]
        source.write_text('outro', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'ocupado'):
            self.state.undo(snapshot)
        self.assertEqual(source.read_text(), 'outro')
        self.assertEqual(renamed.read_text(), 'original')
        source.unlink()
        self.state.undo(snapshot)
        self.assertEqual(source.read_text(), 'original')
        self.assertEqual(self.state.read()['tags']['Projeto'], [str(source)])
        self.assertEqual(self.state.read()['undo'], [])

    def test_batch_rename_rolls_back_when_history_cannot_be_written(self):
        source = self.src / 'origem.txt'
        source.touch()
        rows = plan([source], '{nome}-{n}')
        with patch.object(self.state, 'write', side_effect=OSError('sem espaço')):
            with self.assertRaisesRegex(ValueError, 'sem espaço'):
                apply_plan(rows, on_commit=lambda changes: self.state.remember('Renomeação', changes))
        self.assertTrue(source.exists())
        self.assertFalse(rows[0][1].exists())


if __name__ == '__main__':
    unittest.main()
