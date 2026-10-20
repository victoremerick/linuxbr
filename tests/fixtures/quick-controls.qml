// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../../packages/linuxbr-desktop/files/usr/share/plasma/plasmoids/org.linuxbr.quicksettings/contents/ui" as Quick
Item {
    width: 440; height: 540
    property alias controller: mock
    QtObject {
        id: mock
        property bool wifiAvailable: true
        property bool wifiBlocked: false
        property bool wifiOn: false
        property bool wifiBusy: false
        property bool bluetoothAvailable: true
        property bool bluetoothBlocked: false
        property bool bluetoothOn: false
        property bool bluetoothBusy: false
        property bool audioAvailable: true
        property string audioName: "Saída de teste"
        property real volume: 35
        property bool muted: false
        property string errorMessage: ""
        property int wifiWrites: 0
        property int bluetoothWrites: 0
        property int volumeWrites: 0
        property int brightnessWrites: 0
        property var displays: ListModel {
            ListElement { displayName: "screen1"; label: "Tela 1"; brightness: 40; maxBrightness: 100 }
            ListElement { displayName: "screen2"; label: "Tela 2"; brightness: 160; maxBrightness: 200 }
        }
        function setWifi(on) { wifiWrites++; wifiOn=on; }
        function setBluetooth(on) { bluetoothWrites++; bluetoothOn=on; }
        function setVolume(value) { volumeWrites++; volume=value; }
        function setMuted(value) { muted=value; }
        function setBrightness(name,value) {
            brightnessWrites++;
            for (let i=0;i<displays.count;i++) if (displays.get(i).displayName===name) displays.setProperty(i,"brightness",value);
        }
        function externalBrightness() { displays.setProperty(0,"brightness",25); }
        function unplug() { displays.clear(); }
    }
    Quick.QuickControls { anchors.fill: parent; backend: mock }
}
