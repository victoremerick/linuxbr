// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.networkmanagement as NM
import "../../packages/linuxbr-desktop/files/usr/share/plasma/plasmoids/org.linuxbr.quicksettings/contents/ui" as Quick
Item {
    width: 500; height: 650
    property alias service: service
    property alias radio: radio
    property alias bluetoothPage: bluetoothPage
    property int page: 0
    QtObject { id: backend; property bool wifiOn: true; property bool bluetoothOn: true; property string errorMessage: "" }
    QtObject {
        id: service
        property bool scanning: false
        property string action: ""
        property string secret: ""
        signal connectionActivationFailed(string path, string message)
        function requestScan() {}
        function addAndActivateConnection(device, ap, password) { action = "new:" + ap; secret = password || ""; }
        function activateConnection(path, device, ap) { action = "saved:" + path; }
        function deactivateConnection(path, device) { action = "disconnect:" + path; }
    }
    ListModel {
        id: networks
        Component.onCompleted: {
            for (const name of ["Aberta", "Protegida", "Salva", "Ativa", "Ligando"]) append({ItemUniqueName:name, Type:NM.Enums.Wireless, ConnectionState:name === "Ativa" ? NM.Enums.Activated : name === "Ligando" ? NM.Enums.Activating : NM.Enums.Deactivated, Uuid:name === "Salva" || name === "Ativa" ? name : "", SecurityType:name === "Protegida" ? NM.Enums.Wpa2Psk : 0, ConnectionPath:"/"+name, DevicePath:"/wifi", SpecificPath:"/ap/"+name, ConnectionIcon:"network-wireless"});
        }
    }
    QtObject { id: done; property bool isFinished: true; property int error: 0; property string errorText: "" }
    QtObject {
        id: radio
        property string address: "test"
        property string name: "Fone de teste"
        property string icon: "audio-headphones"
        property bool paired: false
        property bool connected: false
        property bool blocked: false
        property string action: ""
        function pair() { action = "pair"; paired = true; return done; }
        function connectToDevice() { action = "connect"; connected = true; return done; }
        function disconnectFromDevice() { action = "disconnect"; connected = false; return done; }
    }
    Quick.WifiPage { anchors.fill: parent; visible: parent.page === 0; backend: backend; networkList: networks; networkHandler: service }
    Quick.BluetoothPage { id: bluetoothPage; anchors.fill: parent; visible: parent.page === 1; backend: backend; deviceList: [radio]; adapterList: [] }
}
