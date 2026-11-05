#!/usr/bin/python3
"""Behavior checks for file-property queries using private temporary fixtures."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'packages/linuxbr-file-properties/files/usr/lib/linuxbr-file-properties/backend.py'
SPEC = importlib.util.spec_from_file_location('file_properties_08', BACKEND)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class Properties(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.file = self.root / 'ação com espaços.txt'
        self.file.write_bytes(b'abc')

    def test_sha_algorithms_and_empty_file(self):
        for algorithm in ('sha256', 'sha512'):
            value = backend.hash_file(self.file, algorithm, progress=lambda _value: None)
            self.assertEqual(value['hash'], hashlib.new(algorithm, b'abc').hexdigest())
        self.file.write_bytes(b'')
        self.assertEqual(backend.hash_file(self.file, 'sha256')['hash'], hashlib.sha256(b'').hexdigest())
        with self.assertRaises(ValueError): backend.hash_file(self.file, 'md5')

    @unittest.skipUnless(hasattr(os, 'symlink') and os.name != 'nt', 'requires local POSIX links')
    def test_hash_refuses_links_and_fifo(self):
        link = self.root / 'link'
        link.symlink_to(self.file)
        with self.assertRaises(ValueError): backend.hash_file(link, 'sha256')
        fifo = self.root / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError): backend.hash_file(fifo, 'sha256')

    def test_hash_discards_file_changed_during_read(self):
        changed = False
        def modify(_value):
            nonlocal changed
            if not changed:
                self.file.write_bytes(b'alterado')
                changed = True
        with self.assertRaisesRegex(ValueError, 'mudou'):
            backend.hash_file(self.file, 'sha256', progress=modify)

    def test_hash_discards_replaced_path(self):
        def replace_file(_value):
            replacement = self.root / 'substituto'
            replacement.write_bytes(b'outro arquivo')
            os.replace(replacement, self.file)
        with self.assertRaisesRegex(ValueError, 'mudou'):
            backend.hash_file(self.file, 'sha256', progress=replace_file)

    def test_declared_executable_version_is_read_without_execution(self):
        def block(key, value=b'', value_type=1, children=b''):
            result = bytearray(6) + key.encode('utf-16le') + b'\0\0'
            result += b'\0' * (-len(result) % 4)
            result += value
            result += b'\0' * (-len(result) % 4)
            result += children
            struct.pack_into('<HHH', result, 0, len(result), len(value) // 2 if value_type else len(value), value_type)
            return bytes(result)
        company = block('CompanyName', 'Empresa de teste\0'.encode('utf-16le'))
        version = block('FileVersion', '1.2.3\0'.encode('utf-16le'))
        strings = block('StringFileInfo', children=block('040904b0', children=company + version))
        resource = block('VS_VERSION_INFO', b'\0' * 52, 0, strings)
        image = bytearray(4096)
        image[:2] = b'MZ'
        struct.pack_into('<I', image, 60, 0x80)
        image[0x80:0x84] = b'PE\0\0'
        struct.pack_into('<HH', image, 0x84, 0x14c, 1)
        struct.pack_into('<H', image, 0x94, 224)
        struct.pack_into('<H', image, 0x98, 0x10b)
        struct.pack_into('<II', image, 0x98 + 112, 0x1000, 0x1000)
        struct.pack_into('<IIII', image, 0x178 + 8, 0x1000, 0x1000, 0x1000, 0x200)
        for offset, name, child in [(0, 16, 0x80000020), (0x20, 1, 0x80000040), (0x40, 1033, 0x60)]:
            struct.pack_into('<HH', image, 0x200 + offset + 12, 0, 1)
            struct.pack_into('<II', image, 0x200 + offset + 16, name, child)
        struct.pack_into('<IIII', image, 0x260, 0x1100, len(resource), 1200, 0)
        image[0x300:0x300 + len(resource)] = resource
        executable = self.root / 'programa.exe'
        executable.write_bytes(image)
        details = backend.pe_version_strings(executable)
        self.assertEqual(details['Fabricante declarado'], 'Empresa de teste')
        self.assertEqual(details['Versão declarada do arquivo'], '1.2.3')
        executable.write_bytes(b'MZ')
        self.assertEqual(backend.pe_version_strings(executable), {})

    @unittest.skipIf(os.name == 'nt', 'requires POSIX mount and link semantics')
    def test_preview_skips_linked_tree(self):
        (self.root / 'pasta').mkdir()
        (self.root / 'pasta' / 'outro').write_bytes(b'123')
        (self.root / 'link').symlink_to(self.root / 'pasta', target_is_directory=True)
        with patch.object(backend, 'emit'):
            result = backend.recursive_preview(self.root)
        self.assertEqual((result['files'], result['folders'], result['links']), (2, 2, 1))
        self.assertTrue(result['safe_recursive'])

    @unittest.skipIf(os.name == 'nt', 'requires POSIX mount semantics')
    def test_preview_blocks_native_recursion_over_nested_mount(self):
        mounted = self.root / 'volume'
        mounted.mkdir()
        with patch.object(backend.os.path, 'ismount', side_effect=lambda value: value == str(mounted)), patch.object(backend, 'emit'):
            result = backend.recursive_preview(self.root)
        self.assertEqual(result['mounts'], 1)
        self.assertFalse(result['safe_recursive'])

    def test_mountinfo_longest_path_and_escapes(self):
        fixture = self.root / 'mountinfo'
        fixture.write_text('21 1 8:1 / / rw - ext4 /dev/sda1 rw\n22 21 8:2 / /media/meus\\040dados ro - ntfs3 /dev/sdb1 ro\n')
        result = backend.mount_for('/media/meus dados/ação', fixture)
        self.assertEqual(result['filesystem'], 'ntfs3')
        self.assertEqual(result['target'], '/media/meus dados')
        self.assertTrue(result['readonly'])

    def test_kup_nested_groups_inclusion_and_exclusion(self):
        config = self.root / 'kuprc'
        config.write_text('[Plan][1]\nDescription=Documentos\nPaths included=/home/teste\nPaths excluded=/home/teste/privado\nDestination type=0\nFilesystem destination path=file:///media/C%C3%B3pias\nBackup type=0\n[Plan][2]\nDescription=Outra conta\nPaths included=/home/outra\nDestination type=0\n')
        plans = backend.kup_plans('/home/teste/ação.txt', config)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['repository'], '/media/Cópias')
        self.assertTrue(plans[0]['versioned'])
        self.assertEqual(backend.kup_plans('/home/teste/privado/segredo', config), [])
        self.assertEqual(backend.kconfig_list(r'/home/teste/a\,b,/home/teste/c\\d'), ['/home/teste/a,b', '/home/teste/c\\d'])

    def test_versions_require_item_in_archive(self):
        repository = self.root / 'backup'
        (repository / 'objects').mkdir(parents=True)
        (repository / 'HEAD').write_text('ref: refs/heads/kup')
        plan = dict(name='Documentos', repository=str(repository), versioned=True)
        def run(argv, **_kwargs):
            output = '2026-11-03-120000/\n2026-11-02-120000/\n' if argv[-1] == 'kup/' else 'ação.txt\n' if '2026-11-03' in argv[-1] else ''
            return subprocess.CompletedProcess(argv, 0, stdout=output, stderr='')
        with patch.object(backend, 'kup_plans', return_value=[plan]), patch.object(backend.shutil, 'which', return_value='/usr/bin/bup'), patch.object(backend, 'command', side_effect=run), patch.object(backend, 'emit'):
            result = backend.versions(Path('/home/teste/ação.txt'))
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(result['rows'][0]['date'], '2026-11-03-120000')

    def test_wine_handoff_refuses_root(self):
        with patch.object(backend.os, 'geteuid', return_value=0, create=True):
            with self.assertRaisesRegex(ValueError, 'sem sudo'):
                backend.wine_action(str(self.file), 'environment', 'run')

    def test_wine_handoff_starts_once_and_opens_existing_monitor(self):
        launched = []
        module = SimpleNamespace(read_environment=lambda _identifier: {},
            start_job=lambda *arguments: launched.append(arguments) or 'a0e1f234-4321-4321-8321-123456789abc')
        with patch.object(backend.os, 'geteuid', return_value=1000, create=True), patch.object(backend, 'runner', return_value=module), patch.object(backend.subprocess, 'Popen') as monitor:
            result = backend.wine_action(str(self.file), 'environment', 'run')
        self.assertEqual(launched, [('environment', 'run', str(self.file))])
        self.assertTrue(result['monitor'])
        self.assertIn('--watch-job', monitor.call_args.args[0])
        self.assertIn('--environment', monitor.call_args.args[0])

    def test_sharing_service_starts_only_requested_unit(self):
        def run(argv, **_kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout='active\n' if 'is-active' in argv else '', stderr='')
        with patch.object(backend, 'command', side_effect=run) as calls:
            result = backend.start_sharing_service()
        self.assertIn('ativo', result['text'])
        self.assertEqual(calls.call_args_list[0].args[0], ['systemctl', 'start', 'smbd.service'])
        self.assertFalse(any('enable' in call.args[0] for call in calls.call_args_list))

    def test_sharing_keeps_addresses_and_services_after_partial_timeout(self):
        def run(argv, **_kwargs):
            if argv[0] == 'net':
                return subprocess.CompletedProcess(argv, 0, stdout='[lab]\npath=' + str(self.root) +
                    '\nusershare_acl=brasil:F,\nguest_ok=n\n', stderr='')
            if argv[0] == 'systemctl':
                if argv[-1] == 'nmbd.service':
                    raise subprocess.TimeoutExpired(argv, 3)
                return subprocess.CompletedProcess(argv, 0, stdout='active\n', stderr='')
            if '--get-active-zones' in argv:
                return subprocess.CompletedProcess(argv, 0, stdout='public\n  interfaces: eth0\n', stderr='')
            raise subprocess.TimeoutExpired(argv, 3)
        with patch.object(backend.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), \
             patch.object(backend, 'command', side_effect=run) as calls:
            result = backend.sharing(self.root)
        self.assertTrue(result['partial'])
        self.assertTrue(result['shares_complete'])
        self.assertEqual(result['shares'][0]['name'], 'lab')
        self.assertTrue(result['shares'][0]['smb'].endswith('/lab'))
        self.assertEqual(result['shares'][0]['guest'], 'n')
        self.assertIn('smbd.service: active', result['states'])
        self.assertTrue(any('nmbd.service' in line and 'preservados' in line for line in result['states']))
        self.assertTrue(any('prazo esgotado' in line for line in result['states']))
        self.assertEqual(result['zones'], ['public'])
        self.assertTrue(all(call.kwargs.get('timeout') == 3 for call in calls.call_args_list
                            if call.args[0][0] == 'firewall-cmd'))

    def test_explicit_firewall_inspection_allows_native_auth_and_keeps_partial_denial(self):
        def run(argv, **_kwargs):
            if argv[0] == 'net':
                return subprocess.CompletedProcess(argv, 0, stdout='[lab]\npath=' + str(self.root) +
                    '\nusershare_acl=brasil:F,\nguest_ok=n\n', stderr='')
            if argv[0] == 'systemctl':
                return subprocess.CompletedProcess(argv, 0, stdout='active\n', stderr='')
            if '--get-active-zones' in argv:
                return subprocess.CompletedProcess(argv, 0, stdout='public\n  interfaces: eth0\n', stderr='')
            return subprocess.CompletedProcess(argv, 2, stdout='', stderr='Not authorized')
        with patch.object(backend.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), \
             patch.object(backend, 'command', side_effect=run) as calls:
            result = backend.sharing(self.root, authorize_firewall=True)
        self.assertTrue(result['partial'])
        self.assertEqual(len(result['shares']), 1)
        self.assertIn('smbd.service: active', result['states'])
        firewall_calls = [call for call in calls.call_args_list if call.args[0][0] == 'firewall-cmd']
        self.assertTrue(firewall_calls)
        self.assertTrue(all(call.kwargs.get('timeout') == 120 for call in firewall_calls))
        self.assertTrue(all('--get-active-zones' in call.args[0] or '--query-service=samba' in call.args[0]
                            for call in firewall_calls))
        self.assertFalse(any('--add-service=samba' in call.args[0] for call in calls.call_args_list))

    def test_firewall_requires_selected_active_zone_and_reports_denial(self):
        active = subprocess.CompletedProcess([], 0, stdout='casa\n  interfaces: eth0\n', stderr='')
        with patch.object(backend, 'command', return_value=active) as calls:
            with self.assertRaisesRegex(ValueError, 'não está ativa'):
                backend.allow_sharing_firewall('public')
            self.assertEqual(calls.call_count, 1)
        denied = subprocess.CompletedProcess([], 2, stdout='', stderr='Não autorizado')
        with patch.object(backend, 'command', side_effect=[active, denied]) as calls:
            with self.assertRaisesRegex(ValueError, 'não foi alterado'):
                backend.allow_sharing_firewall('casa', persist=True)
            self.assertEqual(calls.call_count, 2)
        with self.assertRaises(ValueError):
            backend.allow_sharing_firewall('casa; comando')

    @unittest.skipIf(os.name == 'nt', 'subprocess cancellation validated on POSIX')
    def test_large_hash_process_can_be_cancelled(self):
        large = self.root / 'large'
        with large.open('wb') as stream:
            stream.truncate(2 * 1024 * 1024 * 1024)
        process = subprocess.Popen([sys.executable, str(BACKEND), 'hash', str(large)], stdout=subprocess.PIPE, text=True)
        first = process.stdout.readline()
        self.assertIn('"progress": true', first)
        process.kill()
        process.wait(timeout=3)
        self.assertNotEqual(process.returncode, 0)
        process.stdout.close()


if __name__ == '__main__':
    unittest.main()
