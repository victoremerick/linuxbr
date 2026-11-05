#!/usr/bin/env python3
"""Qt confirmation, map selection and request routing; uses no real disks."""
import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
spec=importlib.util.spec_from_file_location('fixtures', ROOT/'tests/test-partitioning.py')
fixtures=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
from PyQt6.QtWidgets import QApplication, QDialog
from partition_dialog import PartitionDialog
from partitioning import annotate, MIB
from core import inventory, Store
from app import Window

app=QApplication([])
objects=fixtures.fixture()
rows=annotate(inventory(objects), objects)
rows[0].update(size=128*1024**3, fs='ext4', usage=dict(total=128*1024**3, used=50*1024**3, free=78*1024**3, reserved=0))
row=next(r for r in rows if r['path']=='/p1')
for action in ('delete', 'format'):
    dialog=PartitionDialog(row, action)
    assert not dialog.apply.isEnabled()
    dialog.confirm.setChecked(True)
    assert not dialog.apply.isEnabled()
    dialog.typed.setText('/dev/wrong')
    assert not dialog.apply.isEnabled()
    dialog.typed.setText('/dev/fixture1')
    assert dialog.apply.isEnabled()
    dialog.reject()

class Preview(Window):
    def refresh(self): pass
with tempfile.TemporaryDirectory() as tmp:
    window=Preview(); window.timer.stop(); window.store=Store(Path(tmp)/'settings.json')
    window.populate(rows)
    gaps=[i for i,r in enumerate(window.rows) if r.get('unallocated')]
    assert len(gaps)==1
    window.diskmap.buttons[gaps[0]].click()
    assert window.partition_actions['create'].isEnabled()
    assert not window.partition_actions['format'].isEnabled()
    assert not window.buttons['Montar'].isEnabled()
    dialog=PartitionDialog(window.selected(), 'create')
    dialog.confirm.setChecked(True); dialog.size.setValue(64)
    assert dialog.apply.isEnabled()
    payload=dialog.request()
    assert payload['start']==257*MIB and payload['size']==64*MIB
    calls=[]
    window.worker=lambda args, callback: calls.append(args)
    with patch('app.PartitionDialog.exec', return_value=QDialog.DialogCode.Rejected): window.edit_partition('create')
    assert not calls
    with patch('app.PartitionDialog.exec', return_value=QDialog.DialogCode.Accepted), patch('app.PartitionDialog.request', return_value=payload):
        window.edit_partition('create')
    assert calls[0][0]=='partition' and '"create"' in calls[0][1]
    # System disk's free space remains visible, but cannot be edited while mounted.
    objects['/p1'][fixtures.PREFIX+'Filesystem']['MountPoints']=[b'/\0']
    window.populate(annotate(inventory(objects), objects))
    gap=next(i for i,r in enumerate(window.rows) if r.get('unallocated'))
    window.table.selectRow(gap)
    assert not any(a.isEnabled() for a in window.partition_actions.values())
    window.populate(rows); window.resize(1100, 740); window.show(); app.processEvents(); app.processEvents()
    assert window.grab().save('/tmp/linuxbr-partitions-integrated.png')
    window.timer.stop(); window.close()
print('PASS: confirmação explícita, cancelamento, ações integradas, espaço não alocado e proteção do sistema')
