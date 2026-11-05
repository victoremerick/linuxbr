import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-boot-tools/files/usr/lib/linuxbr-boot'))
import user_environment as environment


class UserEnvironment(unittest.TestCase):
    def test_literal_values_and_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ,XDG_CONFIG_HOME=temporary),patch.object(environment,'mode',return_value=None):
            path=Path(temporary)/'linuxbr/environment.json';path.parent.mkdir()
            values={'NOME':'valor $HOME ${USER} "aspas" \\ caminho'};path.write_text(json.dumps(values))
            self.assertEqual(environment.values(),values)
            for invalid in [{'BAD\nKEY':'x'},{'KEY':'value\x00other'},{'KEY':True},['invalid']]:
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):environment.values()
            path.unlink();other=Path(temporary)/'other';other.write_text('{}');path.symlink_to(other)
            with self.assertRaises(ValueError):environment.values()

    def test_restricted_boot_does_not_read_personal_configuration(self):
        with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ,XDG_CONFIG_HOME=temporary),patch.object(environment,'mode',return_value='safe'):
            path=Path(temporary)/'linuxbr/environment.json';path.parent.mkdir();path.write_text('invalid JSON')
            self.assertEqual(environment.values(),{})


if __name__=='__main__':unittest.main()
