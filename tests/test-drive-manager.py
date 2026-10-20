#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
from core import Store, inventory, smb_url, PREFIX


def volume(uuid='abc', mounts=(), device='/dev/sdb1'):
    return {PREFIX + 'Block': {'Device': device.encode() + b'\0', 'IdUUID': uuid, 'Size': 1234, 'IdLabel': 'Dados', 'Drive': '/drive', 'IdType': 'ext4'},
            PREFIX + 'Filesystem': {'MountPoints': [x.encode() + b'\0' for x in mounts]}}


class Drives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'drives.json')

    def test_replug_and_reservations(self):
        first = inventory({'/a': volume()})
        self.assertEqual(self.store.discover(first)['letters']['uuid:abc'], 'D')
        self.store.discover([])
        second = inventory({'/b': volume(device='/dev/sdc1')})
        self.assertEqual(self.store.discover(second)['letters']['uuid:abc'], 'D')
        self.store.assign('uuid:abc', 'M')
        self.assertEqual(self.store.discover(second)['letters']['uuid:abc'], 'M')
        self.assertEqual(self.store.discover(inventory({'/c': volume('xyz')}))['letters']['uuid:xyz'], 'D')

    def test_reserved_letters_conflicts_and_exhaustion(self):
        for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ': self.store.assign('id:' + letter, letter)
        with self.assertRaises(ValueError): self.store.assign('other', 'D')
        with self.assertRaises(ValueError): self.store.assign('system', 'C')
        self.assertNotIn('uuid:abc', self.store.discover(inventory({'/a': volume()}))['letters'])
        with self.assertRaises(ValueError): self.store.add_share('smb://server/share', 'Rede')
        self.assertEqual(self.store.update()['shares'], {})

    def test_root_and_protected(self):
        rows = inventory({'/a': volume(mounts=['/']), '/b': volume('boot', ['/boot/efi'])})
        self.assertEqual(rows[0]['key'], 'system')
        self.assertTrue(rows[1]['protected'])
        self.assertEqual(self.store.discover(rows)['letters'], {})

    def test_duplicate_uuids_and_no_uuid(self):
        rows = inventory({'/a': volume(), '/b': volume(), '/c': volume('')})
        self.assertTrue(all(not r['key'] for r in rows[1:]))
        self.assertEqual(self.store.discover(rows)['letters'], {})

    def test_network_normalization_and_removal(self):
        url = smb_url(r'\\SERVER\Equipe Brasil')
        self.assertEqual(url, 'smb://server/Equipe%20Brasil')
        self.store.add_share(url, 'Equipe')
        self.assertEqual(self.store.update()['letters']['smb:' + url], 'Z')
        self.store.forget('smb:' + url)
        self.assertEqual(self.store.update()['shares'], {})

    def test_network_rejects_secrets_and_wrong_schemes(self):
        for url in ['file:///etc', 'https://example.org/a', 'smb://u:secret@srv/a', 'smb://srv', 'smb://srv/a?password=x', 'smb://srv:bad/a', 'smb://srv/a%00b']:
            with self.subTest(url=url), self.assertRaises(ValueError): smb_url(url)

    def test_corrupt_config_preserved(self):
        self.store.path.write_text('{broken')
        with self.assertRaises(ValueError): self.store.update()
        self.assertEqual(self.store.path.read_text(), '{broken')

    def test_independent_store_instances_merge_and_private_permissions(self):
        self.store.assign('one', 'D')
        other = Store(self.store.path)
        other.assign('two', 'E')
        self.assertEqual(self.store.update()['letters'], {'one': 'D', 'two': 'E'})
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

if __name__ == '__main__': unittest.main()
