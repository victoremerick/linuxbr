#!/usr/bin/env python3
"""Temporary Samba publication lifecycle without changing the host's shares."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'packages/linuxbr-file-properties/files/usr/lib/linuxbr-file-properties'
sys.path.insert(0, str(SOURCE))

import share_grants as grants
from backend import usershare_entries


class SambaSimulation:
    def __init__(self, root, shared):
        self.spool = root / 'usershares'
        self.spool.mkdir(mode=0o1770)
        self.shared = shared
        self.trace = []
        (self.spool / 'original').write_text(
            f'#VERSION 2\npath={shared}\ncomment=Original\nusershare_acl=S-1-1-0:R,\nguest_ok=n\n')

    def run(self, tool, *args):
        self.trace.append((tool, *args))
        output = ''
        if tool == 'testparm':
            output = str(self.spool)
        if tool == 'pdbedit':
            output = 'Unix username:  teste\nUser SID:      S-1-5-21-123-456-789-1010\n'
        if (tool, *args[:2]) == ('net', 'usershare', 'add'):
            alias, path, title, acl, guest = args[2:]
            (self.spool / alias).write_text(f'#VERSION 2\npath={path}\ncomment={title}\nusershare_acl={acl}\n{guest}\n')
        if (tool, *args[:2]) == ('net', 'usershare', 'delete'):
            (self.spool / args[2]).unlink()
        if (tool, *args[:2]) == ('net', 'usershare', 'info'):
            output = '\n'.join(f'[{item.name}]\n' + item.read_text()
                               for item in sorted(self.spool.iterdir()))
        return subprocess.CompletedProcess((tool, *args), 0, output, '')


@unittest.skipUnless(os.geteuid() == 0, 'o estado Samba simulado pertence ao administrador')
class Shares(unittest.TestCase):
    def setUp(self):
        data = tempfile.TemporaryDirectory(dir='/root')
        self.addCleanup(data.cleanup)
        self.root = Path(data.name)
        self.share = self.root / 'Pasta de teste'
        self.share.mkdir()
        self.state = self.root / 'state'
        self.samba = SambaSimulation(self.root, self.share)
        user = SimpleNamespace(pw_uid=1001, pw_gid=1001, pw_name='tester')
        for guard in (patch.object(grants, 'STATE', self.state),
                      patch.object(grants, 'run', self.samba.run),
                      patch.object(grants.pwd, 'getpwnam', return_value=user),
                      patch.object(grants.time, 'time', return_value=1_000_000)):
            guard.start()
            self.addCleanup(guard.stop)

    def test_expiry_closes_only_temporary_address_and_keeps_original_acl(self):
        original = (self.samba.spool / 'original').read_bytes()
        initial_mode = self.share.stat().st_mode
        a = grants.grant(str(self.share), 'tester', 'read', 5)
        b = grants.grant(str(self.share), 'tester', 'edit', 10)
        reader, writer = [self.samba.spool / record['alias'] for record in (a, b)]
        self.assertIn('S-1-5-21-123-456-789-1010:R', reader.read_text())
        self.assertIn('S-1-5-21-123-456-789-1010:F', writer.read_text())
        self.assertIn('guest_ok=n', reader.read_text())
        self.assertEqual((self.samba.spool / 'original').read_bytes(), original)
        self.assertEqual(self.share.stat().st_mode, initial_mode)
        with patch.object(grants.time, 'time', return_value=1_000_300):
            self.assertEqual(grants.expire(), [])
        self.assertFalse(reader.exists())
        self.assertTrue(writer.exists())
        self.assertIn(('smbcontrol', '--timeout=5', 'smbd', 'close-share', reader.name), self.samba.trace)
        self.assertEqual(list(grants.records())[0][0].stem, writer.name)
        self.assertEqual((self.samba.spool / 'original').read_bytes(), original)

    def test_modified_share_is_preserved(self):
        result = grants.grant(str(self.share), 'tester', 'read', 5)
        altered = self.samba.spool / result['alias']
        text = altered.read_text().replace('Concessão Linux BR', 'Alterada')
        altered.write_text(text)
        with patch.object(grants.time, 'time', return_value=1_000_400):
            self.assertIn('alterada externamente', grants.expire()[0])
        self.assertEqual(altered.read_text(), text)

    def test_refuses_unpublished_path_and_withdraws_when_samba_info_becomes_unavailable(self):
        missing = self.root / 'unpublished'
        missing.mkdir()
        with self.assertRaisesRegex(ValueError, 'Publique'):
            grants.grant(str(missing), 'tester', 'read', 5)
        row = grants.grant(str(self.share), 'tester', 'read', 5)
        with (patch.object(grants, 'registered', side_effect=ValueError('inacessível')),
              patch.object(grants.time, 'time', return_value=1_000_400)):
            self.assertEqual(grants.expire(), [])
        self.assertFalse((self.samba.spool / row['alias']).exists())
        self.assertTrue(datetime.fromisoformat(row['expires']).tzinfo)

    def test_original_usershare_output_is_exact(self):
        raw = '[publico]\npath=/srv/docs\ncomment=Relatórios\nusershare_acl=Everyone:R,\nguest_ok=n\n'
        data = usershare_entries(raw)
        self.assertEqual(data['publico']['path'], '/srv/docs')
        self.assertEqual(data['publico']['usershare_acl'], 'Everyone:R,')


if __name__ == '__main__':
    unittest.main(verbosity=2)
