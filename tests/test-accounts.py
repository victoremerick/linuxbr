#!/usr/bin/python3
"""Account/domain input and UI contracts; never changes accounts or joins a domain."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0,str(LIB))
import accounts_backend as backend

class Validation(unittest.TestCase):
    def test_domain(self):
        self.assertEqual(backend.domain_name(' CORP.Example.com. '),'corp.example.com')
        for name in ('','localhost','-bad.com','a..com','x;id.com','a/b.com','a'*64+'.com'):
            with self.assertRaises(ValueError): backend.domain_name(name)
    def test_error_redacts_secret(self):
        import io
        output=io.StringIO()
        with patch('sys.stdin',io.StringIO(json.dumps({'password':'SECRET'}))), patch('sys.stdout',output), patch.object(backend,'execute',side_effect=RuntimeError('failure SECRET')):
            backend.main()
        self.assertNotIn('SECRET',output.getvalue())
        self.assertFalse(json.loads(output.getvalue())['ok'])
    def test_join_credentials_contract(self):
        import dbus
        from unittest.mock import MagicMock
        props={'Name':'corp.example.com','Configured':'','LoginFormats':['%U@corp.example.com'],'LoginPolicy':'','SupportedJoinCredentials':[('password','administrator')]}
        api=MagicMock()
        api.GetAll.return_value=props
        api.Discover.return_value=(100,['/realm'])
        with patch('dbus.SystemBus'), patch('dbus.Interface',return_value=api):
            backend.execute(dict(action='join',domain='corp.example.com',username='admin',password='secret',ou='OU=Linux,DC=corp,DC=example,DC=com'))
        args=api.Join.call_args.args
        self.assertEqual(args[0].signature,'ssv')
        self.assertEqual(tuple(args[0][:2]),('password','administrator'))
        self.assertEqual(args[0][2].variant_level,1)
        self.assertEqual(tuple(args[0][2]),('admin','secret'))
        self.assertEqual(args[1]['membership-software'],'adcli')
        self.assertIn('computer-ou',args[1])

    def test_gui(self):
        from PyQt6.QtWidgets import QApplication
        from accounts import AccountsPage
        app=QApplication.instance() or QApplication([])
        calls=[]
        page=AccountsPage(False,calls.append)
        from PyQt6.QtWidgets import QPushButton
        next(b for b in page.findChildren(QPushButton) if 'Gerenciar' in b.text()).click()
        self.assertEqual(calls,[['kcmshell6','kcm_users']])
        domain=AccountsPage(True,calls.append)
        self.assertEqual(domain.table.columnCount(),4)
        self.assertEqual(domain.domain.accessibleName(),'Domínio da empresa')
        page.deleteLater(); domain.deleteLater()

if __name__=='__main__': unittest.main()
