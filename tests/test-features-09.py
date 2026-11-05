"""Reject package substitutions and preserve installed architecture identities."""
from pathlib import Path
from types import SimpleNamespace
import sys
import re
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import features_backend as backend


class FeaturePlans(unittest.TestCase):
    def test_running_wine_servers_block_removal_for_both_architectures(self):
        for process in ['wineserver','wineserver32','wineserver64']:
            def command(argv,**kwargs):
                return SimpleNamespace(returncode=0 if re.fullmatch(argv[-1],process) else 1,stdout='')
            with self.subTest(process=process),patch.object(backend,'run',side_effect=command):
                with self.assertRaisesRegex(ValueError,'Feche os programas Windows'):backend.ensure_idle('windows')

    def test_removal_cannot_replace_native_hypervisor_with_other_architecture(self):
        output='Remv qemu-system-x86 [9.2]\nInst qemu-system-x86:i386 (9.2 Debian:13 [i386])\n'
        with patch.object(backend,'inventory',return_value=[dict(id='virtualization',installed=['qemu-system-x86'])]),patch.object(backend,'run',return_value=SimpleNamespace(stdout=output)):
            with self.assertRaisesRegex(ValueError,'instalar ou substituir'):backend.package_plan('virtualization','remove')

    def test_installation_cannot_remove_existing_programs(self):
        with patch.object(backend,'run',return_value=SimpleNamespace(stdout='Remv existing-program [1.0]\nInst wine (10.0 Debian:13 [amd64])\n')):
            with self.assertRaisesRegex(ValueError,'remover programas'):backend.package_plan('windows','install')

    def test_inventory_keeps_both_architectures_and_sizes(self):
        output='wine64\tinstalled\t10\nwine:i386\tinstalled\t20\nqemu-system-x86:i386\tinstalled\t30\n'
        with patch.object(backend,'run',return_value=SimpleNamespace(stdout=output)),patch.object(backend,'unit_state',return_value=dict(LoadState='not-found')):
            rows={r['id']:r for r in backend.inventory()}
        self.assertIn('wine:i386',rows['windows']['installed'])
        self.assertEqual(rows['windows']['size'],30*1024)
        self.assertEqual(rows['virtualization']['installed'],['qemu-system-x86:i386'])


if __name__=='__main__':unittest.main()
