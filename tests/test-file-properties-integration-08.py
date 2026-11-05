#!/usr/bin/python3
"""Exercise personal archive lookup and restoration in private bup fixtures."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'packages/linuxbr-file-properties/files/usr/lib/linuxbr-file-properties/backend.py'
SPEC = importlib.util.spec_from_file_location('properties_integration_08', SOURCE)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


@unittest.skipUnless(os.name == 'posix' and shutil.which('bup'), 'bup is required')
class PersonalVersions(unittest.TestCase):
    def test_two_versions_empty_folder_and_restore_to_other_destination(self):
        with tempfile.TemporaryDirectory(prefix='properties-08-') as temporary:
            root = Path(temporary)
            source = root / 'Documentos'
            source.mkdir()
            empty = source / 'pasta vazia'
            empty.mkdir()
            item = source / 'ação com espaços.txt'
            original = 'Primeira versão: ação e integridade.\n'.encode()
            current = 'Segunda versão: dados atuais preservados.\n'.encode()
            item.write_bytes(original)
            repository = root / 'backup'
            config = root / 'config'
            config.mkdir()
            (config / 'kuprc').write_text('[Plan][1]\nDescription=Documentos de teste\nPaths included=' + str(source) +
                '\nDestination type=0\nFilesystem destination path=' + str(repository) + '\nBackup type=0\n')
            environment = {**os.environ, 'HOME': str(root), 'XDG_CONFIG_HOME': str(config)}
            def bup(*arguments):
                return subprocess.run(['bup', '-d', str(repository), *arguments], env=environment,
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, check=True, timeout=30)
            bup('init')
            timestamp = int(time.time()) - 20
            bup('index', '-u', str(source))
            bup('save', '-n', 'kup', '--date=' + str(timestamp), str(source))
            item.write_bytes(current)
            bup('index', '-u', str(source))
            bup('save', '-n', 'kup', '--date=' + str(timestamp + 2), str(source))
            with patch.dict(os.environ, environment), patch.object(backend, 'emit'):
                versions = backend.versions(item)
                folders = backend.versions(empty)
            self.assertEqual(len(versions['rows']), 2, versions)
            self.assertEqual(len(folders['rows']), 2, folders)
            oldest = sorted(versions['rows'], key=lambda row: row['date'])[0]
            destination = root / 'restaurado'
            destination.mkdir()
            bup('restore', '--outdir=' + str(destination), 'kup/' + oldest['date'] + '/' + str(item).lstrip('/'))
            restored = list(destination.rglob(item.name))
            self.assertEqual(len(restored), 1)
            self.assertEqual(hashlib.sha256(restored[0].read_bytes()).digest(), hashlib.sha256(original).digest())
            self.assertEqual(item.read_bytes(), current)


if __name__ == '__main__':
    unittest.main()
