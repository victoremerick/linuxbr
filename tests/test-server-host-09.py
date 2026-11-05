from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-server/files/usr/lib/linuxbr-server'))
import host_backend as backend


class HostValidation(unittest.TestCase):
    def test_account_and_password_boundaries(self):
        for name in ['root:name','--root','a\nroot','a'*32,'UPPER','']:
            with self.assertRaises(ValueError):backend.username(name)
        self.assertEqual(backend.username('brasil-01'),'brasil-01')
        for password in ['short','x'*257,'x'*15+'\n','x'*15+'\0']:
            with self.assertRaises(ValueError):backend.password(password)
        self.assertEqual(backend.password('Senha longa com espaços'),'Senha longa com espaços')

    def test_mutations_require_root(self):
        with patch.object(backend.os,'geteuid',return_value=1000),patch.object(backend,'run') as command:
            with self.assertRaises(PermissionError):backend.apply(dict(action='hostname',hostname='servidor'))
            command.assert_not_called()

    def test_rejects_hostname_injection_before_running_programs(self):
        with patch.object(backend.os,'geteuid',return_value=0),patch.object(backend,'run') as command:
            for value in ['-option','host;reboot','host\nname','x'*64,'host/name','']:
                with self.assertRaises(ValueError):backend.apply(dict(action='hostname',hostname=value))
            command.assert_not_called()


if __name__=='__main__':unittest.main()
