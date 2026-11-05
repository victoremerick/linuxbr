#!/usr/bin/env python3
"""Run with QT_QPA_PLATFORM=offscreen; fixtures never mount or touch disks."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
from PyQt6.QtWidgets import QApplication, QInputDialog
from PyQt6.QtCore import QTimer
from app import Window
from core import Store
from properties import Properties
from show_properties import lookup
from PyQt6.QtWidgets import QProgressBar

application = QApplication([])
class Preview(Window):
    def refresh(self): pass

with tempfile.TemporaryDirectory() as tmp:
    window = Preview()
    window.timer.stop()
    window.store = Store(Path(tmp) / 'settings.json')
    window.store.add_share('smb://servidor/Equipe', 'Equipe')
    fixture = [dict(key='system', name='Sistema', kind='Sistema', size=128 * 1024**3, fs='ext4', mounts=['/'], path='', protected=True),
               dict(key='uuid:data', name='Documentos', kind='Volume', size=256 * 1024**3, fs='ext4', mounts=['/media/documentos'], path='/data', device='/dev/vdb1', mountable=True),
               dict(key='uuid:usb', name='Pendrive', kind='Removível', size=32 * 1024**3, fs='vfat', mounts=[], path='/usb', device='/dev/vdc1', mountable=True)]
    fixture[0]['usage']=dict(total=128*1024**3,used=80*1024**3,free=44*1024**3,reserved=4*1024**3)
    window.populate(fixture)
    assert isinstance(window.table.cellWidget(0,6), QProgressBar)
    assert window.table.cellWidget(0,6).value()==625
    assert 'Monte' in window.table.cellWidget(2,6).text()
    state=dict(rows=fixture,data=window.data)
    assert lookup(state,'linuxbr:/C')[0]['key']=='system'
    try: lookup(state,'linuxbr:/C/subfolder')
    except ValueError: pass
    else: raise AssertionError('nested path accepted')
    dialog=Properties(fixture[0],'C'); dialog.show(); application.processEvents()
    assert dialog.grab().save('/tmp/linuxbr-drive-properties.png')
    dialog.close()
    window.table.selectRow(0)
    assert not window.buttons['Desmontar'].isEnabled()
    assert not window.buttons['Alterar letra'].isEnabled()
    window.table.selectRow(2)
    assert window.buttons['Montar'].isEnabled()
    assert not window.buttons['Abrir'].isEnabled()
    calls = []
    window.worker = lambda args, callback: calls.append(args)
    window.buttons['Montar'].trigger()
    assert calls == [['mount', '/usb', 'uuid:usb', '/dev/vdc1']]
    window.table.selectRow(3)
    assert window.buttons['Abrir'].isEnabled() and window.buttons['Remover rede'].isEnabled()
    assert not window.buttons['Montar'].isEnabled()
    window.show()
    application.processEvents()
    target = os.environ.get('DRIVE_PREVIEW', '/tmp/linuxbr-drive-manager.png')
    assert window.grab().save(target)
    window.buttons['Remover rede'].trigger()
    assert not window.store.update()['shares']
    window.close()
print('PASS: UI, estados de ações, roteamento de montagem, rede e captura')
