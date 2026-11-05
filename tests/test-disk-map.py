#!/usr/bin/env python3
"""Synthetic UDisks topology and Qt selection tests; never accesses real disks."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
from core import PREFIX, inventory, Store
from diskmap import disk_groups
from PyQt6.QtWidgets import QApplication
from app import Window

def block(device, size, fs=''):
    return {'Device': device.encode()+b'\0', 'Size': size, 'Drive': '/drive/ssd', 'IdType': fs, 'IdUUID': device}
G = 1024**3
objects = {
 '/drive/ssd': {PREFIX+'Drive': {'Model': 'SSD'}},
 '/disk': {PREFIX+'Block': block('/dev/vda', 256*G), PREFIX+'PartitionTable': {'Type': 'gpt'}},
 '/data': {PREFIX+'Block': block('/dev/vda2', 128*G, 'ext4'), PREFIX+'Partition': {'Table': '/disk', 'Offset': 128*G, 'Number': 2}, PREFIX+'Filesystem': {'MountPoints': []}},
 '/root': {PREFIX+'Block': block('/dev/vda1', 127*G, 'ext4'), PREFIX+'Partition': {'Table': '/disk', 'Offset': G, 'Number': 1}, PREFIX+'Filesystem': {'MountPoints': [b'/\0']}},
}
rows = inventory(objects)
rows[0]['usage'] = dict(total=127*G, used=60*G, free=67*G, reserved=0)
groups, other = disk_groups(rows)
assert len(groups) == 1 and not other
assert [r['device'] for _, r in groups[0][2]] == ['/dev/vda1', '/dev/vda2']
assert rows[0]['parent'] == '/disk' and rows[0]['protected']
app = QApplication([])
class Preview(Window):
    def refresh(self): pass
with tempfile.TemporaryDirectory() as tmp:
    window = Preview(); window.timer.stop(); window.store = Store(Path(tmp)/'state.json')
    window.populate(rows); window.show(); app.processEvents()
    data_index = next(i for i,r in enumerate(window.rows) if r.get('device') == '/dev/vda2')
    window.diskmap.buttons[data_index].click()
    assert window.selected()['device'] == '/dev/vda2'
    assert window.buttons['Montar'].isEnabled()
    window.table.selectRow(0)
    assert window.diskmap.buttons[0].isChecked()
    assert not window.buttons['Desmontar'].isEnabled()
    window.populate(inventory(objects))
    assert window.selected()['key'] == 'system'
    # Unplug removes all stale partition widgets and selections.
    window.populate([dict(key='system', name='Sistema', kind='Sistema', size=0, fs='', mounts=['/'], path='', protected=True)])
    assert len(window.diskmap.buttons) == 1
    final_rows = inventory(objects)
    final_rows[0]['usage'] = rows[0]['usage']
    window.populate(final_rows); app.processEvents()
    assert window.grab().save('/tmp/linuxbr-disk-management.png')
    window.close()
print('PASS: topologia física, ordem das partições, seleção sincronizada, proteção e desconexão')
