#!/usr/bin/python3
"""Exercise panel selection with fake services; never changes host connections."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from pathlib import Path
from PyQt6.QtCore import QUrl, Qt, QPointF, QPoint
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickView
from PyQt6.QtTest import QTest
app = QGuiApplication([])
view = QQuickView()
view.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / 'fixtures/quick-selection.qml')))
assert not view.errors()
view.show(); QTest.qWait(300)
root = view.rootObject()
def find(parent, name):
    if parent.objectName() == name: return parent
    for child in parent.childItems():
        result = find(child, name)
        if result is not None: return result

def click(name):
    item = find(root, name)
    assert item is not None and item.isVisible() and item.isEnabled(), name
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round(point.x()), round(point.y())))
    QTest.qWait(50)
service = root.property('service')
click('wifi_Aberta'); assert service.property('action') == 'new:/ap/Aberta'
click('wifi_Salva'); assert service.property('action') == 'saved:/Salva'
click('wifi_Ligando'); assert service.property('action') == 'disconnect:/Ligando'
click('wifi_Ativa'); assert service.property('action') == 'disconnect:/Ativa'
click('wifi_Protegida'); assert service.property('action') == 'disconnect:/Ativa'
password = find(root, 'password_Protegida')
assert password.isVisible()
password.setProperty('text', 'test-only-password')
click('connect_Protegida')
assert service.property('action') == 'new:/ap/Protegida'
assert service.property('secret') == 'test-only-password'
assert password.property('text') == '' and not password.isVisible()
root.setProperty('page', 1); QTest.qWait(100)
radio = root.property('radio')
for expected in ('pair', 'connect', 'disconnect'):
    click('device_test'); assert radio.property('action') == expected
radio.setProperty('blocked', True)
assert not find(root, 'device_test').isEnabled()
print('PASS: open/saved/protected Wi-Fi, disconnect, password cleared, Bluetooth pair/connect/disconnect and blocked device')
view.close()
