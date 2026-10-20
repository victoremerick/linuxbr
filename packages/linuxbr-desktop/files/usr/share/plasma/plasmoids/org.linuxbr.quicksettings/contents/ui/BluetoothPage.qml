// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC
import org.kde.bluezqt as BluezQt

ColumnLayout {
    id: page
    required property QtObject backend
    signal back()
    property var deviceList: BluezQt.Manager.devices
    property var adapterList: BluezQt.Manager.adapters
    property var scanningAdapters: []
    property string busyAddress: ""
    property string message: ""
    function completed(call, callback) {
        if (call.isFinished) callback(call);
        else call.finished.connect(callback);
    }
    function stopScan() {
        for (const adapter of scanningAdapters) if (adapter) adapter.stopDiscovery();
        scanningAdapters = [];
    }
    function scan() {
        stopScan(); message = "";
        const owned = [];
        for (const adapter of adapterList) {
            if (!adapter.powered || adapter.discovering) continue;
            owned.push(adapter);
            completed(adapter.startDiscovery(), function(call) { if (call.error) page.message = call.errorText; });
        }
        scanningAdapters = owned; scanTimeout.restart();
    }
    function operate(device) {
        if (busyAddress) return;
        busyAddress = device.address; message = "";
        const pairing = !device.paired;
        const call = device.connected ? device.disconnectFromDevice() : pairing ? device.pair() : device.connectToDevice();
        completed(call, function(result) {
            page.busyAddress = "";
            if (result.error) { page.message = result.errorText; return; }
            if (pairing && device) {
                page.message = "Pareamento concluído. Selecione Conectar para usar o dispositivo.";
            }
        });
    }
    Timer { id: scanTimeout; interval: 30000; onTriggered: page.stopScan() }
    Component.onCompleted: if (backend.bluetoothOn) scan()
    Component.onDestruction: stopScan()
    RowLayout {
        PC.ToolButton { text: "Voltar"; icon.name: "go-previous"; onClicked: page.back() }
        PC.Label { text: "Bluetooth"; font.bold: true; Layout.fillWidth: true }
        PC.ToolButton { text: page.scanningAdapters.length ? "Buscando…" : "Buscar"; enabled: page.backend.bluetoothOn && page.scanningAdapters.length === 0; onClicked: page.scan() }
    }
    PC.Label { text: !page.backend.bluetoothOn ? "Ligue o Bluetooth para selecionar um dispositivo." : page.scanningAdapters.length ? "Buscando dispositivos próximos…" : "Dispositivos conhecidos"; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    PC.Label { text: page.message; visible: text.length > 0; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    PC.ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true; contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            Repeater {
                model: page.deviceList
                delegate: PC.Button {
                    required property var modelData
                    Layout.fillWidth: true
                    objectName: "device_" + modelData.address
                    text: modelData.name + " · " + (page.busyAddress === modelData.address ? "Aguarde…" : modelData.connected ? "Conectado — desconectar" : modelData.paired ? "Conectar" : "Parear")
                    icon.name: modelData.icon || "preferences-system-bluetooth"
                    enabled: page.backend.bluetoothOn && page.busyAddress === "" && !modelData.blocked
                    onClicked: page.operate(modelData)
                }
            }
            PC.Label { visible: page.deviceList.length === 0; text: "Nenhum dispositivo encontrado. Ative o modo de pareamento no dispositivo."; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }
    PC.Label { text: "Se solicitado, confirme o código no diálogo seguro de pareamento e no dispositivo."; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pointSize: 9 }
}
