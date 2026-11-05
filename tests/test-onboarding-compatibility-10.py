"""Observe configured state without approving hardware or old compatibility claims."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import initial_status as initial
import compatibility_records as compatibility
import store_repository as repositories


class InitialConfiguration(unittest.TestCase):
    def test_local_network_does_not_claim_internet(self):
        with patch.object(initial,'command',side_effect=['connected','limited']):
            value=initial.observe('network')
        self.assertIn('somente local',value['text'])
        self.assertNotIn('informa acesso à internet',value['text'])

    def test_disconnected_and_manual_checks_need_user_attention(self):
        with patch.object(initial,'command',return_value=''):
            self.assertEqual(initial.observe('network')['state'],'attention')
        for section in ['migration','display','devices','daily']:
            self.assertEqual(initial.observe(section)['state'],'manual')

    def test_missing_executable_and_timeout_do_not_break_checklist(self):
        for error in [FileNotFoundError(),subprocess.TimeoutExpired('nmcli',6)]:
            with patch.object(initial.subprocess,'run',side_effect=error):
                self.assertEqual(initial.command(['nmcli']),'')


class CompatibilityEvidence(unittest.TestCase):
    def item(self):
        return dict(status='tested',application_version='2.0',test_records=[dict(
            release='0.9.0~beta1',application_version='2.0',result='passed',
            checks=['install','open'],evidence='fixture.json',date=None,runner=None)])

    def test_old_release_cannot_approve_current_release(self):
        value=compatibility.assessment(self.item(),'1.0.0~rc1')
        self.assertFalse(value['current']);self.assertEqual(value['status'],'historical')
        self.assertTrue(compatibility.assessment(self.item(),'0.9.0~beta1')['current'])

    def test_application_version_and_evidence_are_required(self):
        for field,value in [('application_version','1.0'),('checks',[]),('evidence',''),('date','not-a-date')]:
            item=self.item();item['test_records'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compatibility.checked_records(item)

    def test_failure_is_not_replaced_by_old_success(self):
        item=self.item();record=copy.deepcopy(item['test_records'][0]);record.update(release='1.0.0~rc1',result='failed');item['test_records'].append(record)
        self.assertEqual(compatibility.assessment(item,'1.0.0~rc1')['status'],'failed')

    def test_legacy_claims_are_historical_and_missing_data_is_not_invented(self):
        self.assertEqual(compatibility.assessment(dict(status='tested'),'1.0.0')['status'],'historical')
        self.assertEqual(compatibility.assessment(dict(status='untested'),'1.0.0')['status'],'untested')
        text=compatibility.details(self.item(),'1.0.0~rc1')
        self.assertIn('data: não registrada',text);self.assertIn('Wine / Proton: não registrado',text)


class RepositorySearch(unittest.TestCase):
    def test_partial_failure_preserves_results_and_reports_failure(self):
        def execute(argv,**kwargs):
            if 'apt-cache' in argv[0]:return subprocess.CompletedProcess(argv,0,'hello - Greeting\n','')
            raise subprocess.TimeoutExpired(argv,20)
        with patch.object(repositories.subprocess,'run',side_effect=execute):
            value=repositories.search('hello',with_status=True)
        self.assertEqual(value['rows'][0]['id'],'deb:hello');self.assertTrue(value['errors'])

    def test_legacy_list_interface_is_preserved(self):
        with patch.object(repositories.subprocess,'run',side_effect=FileNotFoundError()):
            self.assertEqual(repositories.search('example'),[])


if __name__=='__main__':unittest.main()
