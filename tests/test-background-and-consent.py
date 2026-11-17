#!/usr/bin/env python3
"""Ensaios de inicialização da conta e leitura filtrada de autorizações."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QClipboard
import background_apps
import consent_history
import temporary_clipboard


APP = QApplication.instance() or QApplication([])


class SessionTests(unittest.TestCase):
    def test_background_groups_scoped_app_and_reuses_startup_entry(self):
        rows = [dict(pid=pid,start='7',cpu=seconds,rss=memory,name='Executável')
                for pid, seconds, memory in [(100,5,4096),(101,7,4096),(102,3,8192)]]
        startup = dict(id='org.kde.kate.desktop',name='Kate',command='/bin/true',status='Habilitado',
                       editable=True,hidden=False,protected=False,sha256='test')
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            for pid, scope in [(100,'app-org.kde.kate@autostart.service'),
                               (101,'app-org.kde.kate-100.scope'),
                               (102,'app-flatpak-com.example.Jogo-102.scope')]:
                (proc/str(pid)).mkdir()
                (proc/str(pid)/'cgroup').write_text('0::/user.slice/app.slice/'+scope+'\n')
            with patch.object(background_apps,'snapshot',return_value=(rows,{})) as snapshot, \
                    patch.object(background_apps.startup,'inventory',return_value=[startup]), \
                    patch.object(background_apps.time,'monotonic',return_value=12):
                current, _, groups = background_apps.apps_snapshot({(100,'7'):4,(101,'7'):6,(102,'8'):100},10,proc=proc)
                snapshot.assert_called_once_with(os.getuid())
        indexed = {app['key']:app for app in groups}
        kate = indexed['org.kde.kate']
        game = indexed['com.example.Jogo']
        self.assertEqual(kate['count'],2)
        self.assertEqual(kate['cpu'],100)
        self.assertEqual(kate['rss'],8192)
        self.assertEqual(kate['startup'],startup)
        self.assertEqual(game['flatpak'],'com.example.Jogo')
        self.assertEqual(game['cpu'],0)
        self.assertIn((102,'7'),current)
        widget=background_apps.BackgroundApps(lambda identifier:None,lambda identifier:None)
        widget.loaded((current,12,groups))
        self.assertEqual(widget.table.rowCount(),2)

    def test_polkit_records_filter_trusted_origin_owner_and_arguments(self):
        message = ('Operator of unix-session:4 successfully authenticated as unix-user:admin to gain '
                   'ONE-SHOT authorization for action org.freedesktop.policykit.exec for '
                   'unix-process:152:4342 [/usr/bin/program --token=segredo (owned by unix-user:outra)] '
                   '(owned by unix-user:conta)')
        source = {'_COMM':'polkitd','_SYSTEMD_UNIT':'polkit.service',
                  '__REALTIME_TIMESTAMP':'1700000000000000','MESSAGE':message}
        row = consent_history.journal_row(source,'conta',1000)
        self.assertEqual(row['app'],'program')
        self.assertEqual(row['account'],'conta')
        self.assertNotIn('segredo',json.dumps(row))
        self.assertNotIn('outra',json.dumps(row))
        self.assertIsNone(consent_history.journal_row(source,'outra',4000))
        self.assertIsNone(consent_history.journal_row(dict(source,_COMM='fake'),'conta',1000))
        denied = message.replace('successfully authenticated as unix-user:admin to gain ONE-SHOT',
                                 'FAILED to authenticate to gain')
        self.assertEqual(consent_history.journal_row(dict(source,MESSAGE=denied),'conta',1000)['result'],
                         'Autenticação não concluída')

    def test_local_history_keeps_private_bounded_outcome_without_arguments(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'XDG_STATE_HOME':directory}):
            entry = consent_history.request('Alterar fontes',
                ['/usr/bin/pkexec','/usr/bin/python3','/usr/lib/linuxbr-system/store_sources.py','--segredo'])
            self.assertIsNone(consent_history.request('Consulta',['/usr/bin/true']))
            for code in (0,126,127):
                consent_history.record_result(entry,code)
            file = consent_history.record_path()
            self.assertEqual(file.stat().st_mode & 0o777,0o600)
            records = consent_history.stored_records(file)
            self.assertEqual([value['result'] for value in records],
                             ['Operação concluída','Solicitação cancelada','Não autorizada ou indisponível'])
            self.assertNotIn('segredo',file.read_text())
            self.assertEqual(records[0]['app'],'store_sources')
            with patch.object(consent_history.subprocess,'run',side_effect=OSError):
                values, available = consent_history.history()
            self.assertFalse(available)
            self.assertEqual(values,list(reversed(records)))

    def test_temporary_clipboard_expires_only_the_owned_copy(self):
        class FakeClipboard(QObject):
            changed = pyqtSignal(QClipboard.Mode)

            def __init__(self):
                super().__init__()
                self.mime, self.owned, self.cleared = None,False,0

            def setMimeData(self, mime, mode):
                self.mime,self.owned = mime,True
                self.changed.emit(mode)

            def ownsClipboard(self):
                return self.owned

            def mimeData(self, mode):
                return self.mime

            def clear(self, mode):
                self.mime,self.owned = None,False
                self.cleared += 1
                self.changed.emit(mode)

        clipboard = FakeClipboard()
        temporary = temporary_clipboard.TemporaryClipboard(clipboard)
        temporary.copy('segredo de teste',15)
        self.assertEqual(bytes(clipboard.mime.data(temporary_clipboard.SECRET_FORMAT)),b'secret')
        self.assertTrue(temporary.ours())
        temporary.expire()
        self.assertEqual(clipboard.cleared,1)
        temporary.copy('segredo de teste',30)
        clipboard.owned = False
        clipboard.changed.emit(QClipboard.Mode.Clipboard)
        temporary.expire()
        self.assertEqual(clipboard.cleared,1)


if __name__ == '__main__':
    unittest.main()
