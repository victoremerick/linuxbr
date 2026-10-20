#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
sys.path.insert(0,str(root/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
sys.path.insert(0,str(root/'packages/linuxbr-device-manager/files/usr/lib/linuxbr-device-manager'))
import central
central.Devices.refresh=lambda self:None
central.AccountsPage.refresh=lambda self:None
from app import Window
Window.refresh=lambda self:None
application=QApplication([])
window=central.Central(); window.drives.timer.stop()
window.drives.populate(dict(rows=[dict(key='system',name='Sistema',kind='Sistema',size=0,fs='ext4',mounts=['/'],path='',protected=True)],data=dict(letters={},shares={})))
window.show();application.processEvents()
assert window.stack.count()==len(central.PAGES)
assert window.stack.currentIndex()==0
assert not window.drives.isWindow()
window.nav.setCurrentRow(4);assert window.stack.currentIndex()==4
window.search.setText('tampa');assert window.nav.currentItem().text()=='Energia e bateria'
window.search.clear()
window.navigate('Sistema')
about=window.stack.currentWidget()
assert len(about.details)==2
about.copy_details()
assert 'Kernel:' in application.clipboard().text()
window.navigate('Armazenamento'); assert window.stack.currentIndex()==2
window.navigate('Sistema')
assert window.grab().save(os.environ.get('CENTRAL_PREVIEW','/tmp/linuxbr-system.png'))
window.close()
print('PASS: Central, navigation, embedded storage and screenshot')
