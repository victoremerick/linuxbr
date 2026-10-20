#!/usr/bin/python3
"""Layout/keyboard regression; simulated inventory, no host operations."""
import os
from pathlib import Path
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication,QGroupBox,QToolButton,QScrollArea
from PyQt6.QtTest import QTest
root=Path(__file__).resolve().parents[1]
for name in ('linuxbr-system','linuxbr-drive-manager','linuxbr-device-manager'):
    sys.path.insert(0,str(root/'packages'/name/'files/usr/lib'/name))
import central
from app import Window
central.Devices.refresh=lambda self:None
Window.refresh=lambda self:None
app=QApplication([])
window=central.Central();window.drives.timer.stop();window.devices.timer.stop()
window.resize(900,560);window.show();app.processEvents()
assert window.width()==900, 'Embedded tools must not force a wider window'
about=window.stack.widget(0)
assert not about.findChildren(QGroupBox), 'About should use open sections'
assert about.widget().width()<=about.viewport().width()
buttons={b.text():b for b in about.findChildren(QToolButton)}
buttons['Discos e unidades'].click();assert window.stack.currentIndex()==2
window.nav.setFocus();QTest.keyClick(window.nav,Qt.Key.Key_Down)
assert window.stack.currentIndex()==3, 'Keyboard navigation must remain available'
window.navigate('Administração');app.processEvents()
page=window.stack.currentWidget();assert isinstance(page,QScrollArea)
assert page.widget().width()<=page.viewport().width()
assert all(b.width()<page.viewport().width()-40 for b in page.findChildren(QToolButton)), 'Actions should keep natural width'
window.navigate('Sistema');app.processEvents()
assert window.grab().save(os.environ.get('CLEAN_LAYOUT_PREVIEW','/tmp/linuxbr-clean-small.png'))
window.close()
print('PASS: 900x560, open sections, compact actions, scrolling and keyboard navigation')
