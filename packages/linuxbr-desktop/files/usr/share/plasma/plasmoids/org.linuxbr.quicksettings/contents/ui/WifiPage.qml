// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC
import org.kde.plasma.networkmanagement as NM

ColumnLayout {
    id: page
    required property QtObject backend
    signal back()
    property var networkList: available
    property var networkHandler: handler
    NM.NetworkModel { id: networks }
    NM.AppletProxyModel { id: available; sourceModel: networks }
    NM.Handler { id: handler }
    Connections {
        target: page.networkHandler
        function onConnectionActivationFailed(path, message) { page.backend.errorMessage = message; }
    }
    Component.onCompleted: if (backend.wifiOn) page.networkHandler.requestScan()
    RowLayout {
        PC.ToolButton { text: "Voltar"; icon.name: "go-previous"; onClicked: page.back() }
        PC.Label { text: "Redes Wi-Fi"; font.bold: true; Layout.fillWidth: true }
        PC.ToolButton { text: page.networkHandler.scanning ? "Buscando…" : "Atualizar"; enabled: page.backend.wifiOn && !page.networkHandler.scanning; onClicked: page.networkHandler.requestScan() }
    }
    PC.Label { visible: !page.backend.wifiOn; text: "Ligue o Wi-Fi para selecionar uma rede."; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    PC.Label { visible: text.length > 0; text: page.backend.errorMessage; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    PC.ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true; contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            Repeater {
                model: page.networkList
                delegate: ColumnLayout {
                    id: row
                    required property var model
                    readonly property bool personal: [NM.Enums.StaticWep, NM.Enums.WpaPsk, NM.Enums.Wpa2Psk, NM.Enums.SAE].indexOf(model.SecurityType) >= 0
                    property bool enteringPassword: false
                    visible: model.Type === NM.Enums.Wireless && page.backend.wifiOn
                    Layout.fillWidth: true
                    PC.Button {
                        Layout.fillWidth: true
                        objectName: "wifi_" + row.model.ItemUniqueName
                        text: row.model.ItemUniqueName + (row.model.ConnectionState === NM.Enums.Activated ? " · Conectado — desconectar" : row.model.ConnectionState === NM.Enums.Activating ? " · Conectando — cancelar" : " · Conectar")
                        icon.name: row.model.ConnectionIcon
                        enabled: row.model.ConnectionState !== NM.Enums.Deactivating
                        onClicked: {
                            page.backend.errorMessage = "";
                            if (row.model.ConnectionState === NM.Enums.Activated || row.model.ConnectionState === NM.Enums.Activating) page.networkHandler.deactivateConnection(row.model.ConnectionPath, row.model.DevicePath);
                            else if (row.model.Uuid) page.networkHandler.activateConnection(row.model.ConnectionPath, row.model.DevicePath, row.model.SpecificPath);
                            else if (row.personal) { row.enteringPassword = true; password.forceActiveFocus(); }
                            else page.networkHandler.addAndActivateConnection(row.model.DevicePath, row.model.SpecificPath);
                        }
                    }
                    RowLayout {
                        visible: row.enteringPassword
                        PC.TextField {
                            id: password; objectName: "password_" + row.model.ItemUniqueName; Layout.fillWidth: true; echoMode: TextInput.Password
                            placeholderText: "Senha da rede"; Accessible.name: "Senha de " + row.model.ItemUniqueName
                            onAccepted: if (submit.enabled) submit.clicked()
                        }
                        PC.Button {
                            id: submit; objectName: "connect_" + row.model.ItemUniqueName; text: "Conectar"; enabled: password.text.length > 0
                            onClicked: {
                                page.networkHandler.addAndActivateConnection(row.model.DevicePath, row.model.SpecificPath, password.text);
                                password.clear(); row.enteringPassword = false;
                            }
                        }
                        PC.ToolButton { text: "Cancelar"; onClicked: { password.clear(); row.enteringPassword = false; } }
                    }
                }
            }
        }
    }
    PC.Label { text: "Redes corporativas podem solicitar credenciais e certificados pelo diálogo seguro do sistema."; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pointSize: 9 }
}
