#!/usr/bin/python3
"""QML interaction regression with simulated devices; no host settings changed."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from pathlib import Path
from PyQt6.QtCore import QObject,QUrl,QPoint,QPointF,Qt,QMetaObject
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickView,QQuickItem
from PyQt6.QtTest import QTest
app=QGuiApplication([])
view=QQuickView();view.setSource(QUrl.fromLocalFile(str(Path(__file__).parent/'fixtures/quick-controls.qml')))
assert not view.errors(), '\n'.join(e.toString() for e in view.errors())
view.show();QTest.qWait(200)
root=view.rootObject();backend=root.property('controller')
def visual_item(parent,name):
    if parent.objectName()==name:return parent
    for child in parent.childItems():
        found=visual_item(child,name)
        if found is not None:return found
    return None
def item(name):
    found=visual_item(root,name)
    assert found is not None,name
    return found
def click(name,ratio=0.5):
    control=item(name);point=control.mapToScene(QPointF(0,0))
    QTest.mouseClick(view,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(int(point.x()+control.width()*ratio),int(point.y()+control.height()/2)))
    QTest.qWait(30)
click('wifiToggle');assert backend.property('wifiOn') and backend.property('wifiWrites')==1
backend.setProperty('wifiOn',False);QTest.qWait(30)
assert not item('wifiToggle').property('highlighted')
backend.setProperty('wifiBlocked',True);click('wifiToggle');assert backend.property('wifiWrites')==1
backend.setProperty('wifiBlocked',False);backend.setProperty('wifiAvailable',False)
assert not item('wifiToggle').isEnabled()
click('bluetoothToggle');assert backend.property('bluetoothOn') and backend.property('bluetoothWrites')==1
backend.setProperty('bluetoothBusy',True);click('bluetoothToggle');assert backend.property('bluetoothWrites')==1
click('volumeSlider',0.7);assert 55 < backend.property('volume') < 85
writes=backend.property('volumeWrites');backend.setProperty('volume',20);QTest.qWait(30)
assert item('volumeSlider').property('value')==20 and backend.property('volumeWrites')==writes
click('muteToggle');assert backend.property('muted')
backend.setProperty('audioAvailable',False);assert not item('volumeSlider').isEnabled()
click('brightness_screen1',0.6);assert backend.property('brightnessWrites')>=1
assert item('brightness_screen2').property('value')==160
writes=backend.property('brightnessWrites');QMetaObject.invokeMethod(backend,'externalBrightness');QTest.qWait(30)
assert item('brightness_screen1').property('value')==25 and backend.property('brightnessWrites')==writes
QMetaObject.invokeMethod(backend,'unplug');QTest.qWait(30)
assert visual_item(root,'brightness_screen1') is None
print('PASS: toggles, blocked/absent/busy devices, volume/mute, per-screen brightness, external updates and hot unplug')
view.close()
