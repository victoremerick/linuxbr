#!/usr/bin/python3
"""Integration test for a disposable Plasma VM with virtual Wi-Fi/BT/audio.

Requires LINUXBR_DISPOSABLE_VM=1 and an active audio stream on a test sink
(PipeWire's suspended null sink may not apply volume changes until activated).
Run as the graphical session user. Restores radio, mute and volume states.
"""
import os
if os.environ.get("LINUXBR_DISPOSABLE_VM") != "1":
    raise SystemExit("Run only inside a disposable VM with LINUXBR_DISPOSABLE_VM=1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
import json
import subprocess
from pathlib import Path
from PyQt6.QtCore import QUrl, QPoint, QPointF, Qt, QMetaObject, Q_ARG, QVariant
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickView
from PyQt6.QtTest import QTest

app = QGuiApplication([])
view = QQuickView()
view.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "fixtures/quick-controls-native.qml")))
assert not view.errors()
view.show()
QTest.qWait(1500)
root = view.rootObject()
backend = root.property("controller")

def wait_for(predicate):
    for _ in range(60):
        if predicate():
            return
        QTest.qWait(100)
    raise AssertionError("Service did not confirm the requested state")

def find(parent, name):
    if parent.objectName() == name:
        return parent
    for child in parent.childItems():
        result = find(child, name)
        if result is not None:
            return result

def click(name, ratio=.5):
    control = find(root, name)
    assert control is not None and control.isEnabled(), name
    p = control.mapToScene(QPointF(control.width() * ratio, control.height() / 2))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(round(p.x()), round(p.y())))

def command(*args):
    return subprocess.check_output(args, text=True).strip()

def sink():
    default = command("pactl", "get-default-sink")
    return next(s for s in json.loads(command("pactl", "-f", "json", "list", "sinks")) if s["name"] == default)

def restore(method, value):
    QMetaObject.invokeMethod(backend, method, Q_ARG(QVariant, value))

assert backend.property("wifiAvailable") and not backend.property("wifiBlocked")
assert backend.property("bluetoothAvailable") and not backend.property("bluetoothBlocked")
assert backend.property("audioAvailable")
initial = {key: backend.property(key) for key in ("wifiOn", "bluetoothOn", "volume", "muted")}
try:
    for _ in range(2):
        desired = not backend.property("wifiOn")
        click("wifiToggle")
        wait_for(lambda: backend.property("wifiOn") == desired and not backend.property("wifiBusy"))
        assert command("nmcli", "radio", "wifi") == ("enabled" if desired else "disabled")
        desired_bt = not backend.property("bluetoothOn")
        click("bluetoothToggle")
        wait_for(lambda: backend.property("bluetoothOn") == desired_bt and not backend.property("bluetoothBusy"))
        assert f"Powered: {'yes' if desired_bt else 'no'}" in command("bluetoothctl", "show")
    click("volumeSlider", .7)
    wait_for(lambda: 55 < backend.property("volume") < 85)
    assert 55 < next(iter(sink()["volume"].values()))["value"] * 100 / 65536 < 85
    click("muteToggle")
    wait_for(lambda: backend.property("muted") != initial["muted"])
    assert sink()["mute"] == backend.property("muted")
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "23%"], check=True)
    wait_for(lambda: backend.property("volume") == 23)
    assert find(root, "volumeSlider").property("value") == 23
    print("PASS: native Wi-Fi/Bluetooth on and off, volume/mute, external volume synchronization")
finally:
    restore("setWifi", initial["wifiOn"])
    restore("setBluetooth", initial["bluetoothOn"])
    restore("setVolume", initial["volume"])
    restore("setMuted", initial["muted"])
    QTest.qWait(1000)
    view.close()
