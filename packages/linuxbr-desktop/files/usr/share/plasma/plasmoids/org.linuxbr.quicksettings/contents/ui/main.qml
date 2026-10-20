// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC
import org.kde.plasma.extras as Extras
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

PlasmoidItem {
    id: root
    Layout.minimumWidth: 32
    Layout.minimumHeight: 32
    preferredRepresentation: compactRepresentation
    Plasmoid.icon: "configure"
    toolTipMainText: "Configurações rápidas"
    toolTipSubText: "Rede, Bluetooth, áudio, tela e energia"
    compactRepresentation: MouseArea {
        anchors.fill: parent
        implicitWidth: 32
        implicitHeight: 32
        onClicked: root.expanded = !root.expanded
        Accessible.name: "Configurações rápidas"
        Accessible.role: Accessible.Button
        Accessible.onPressAction: root.expanded = !root.expanded
        Kirigami.Icon { anchors.centerIn: parent; width: 24; height: 24; source: "configure" }
    }
    property string selection: ""
    onExpandedChanged: if (!root.expanded) selection = ""
    ControlsBackend { id: liveBackend }
    fullRepresentation: Extras.Representation {
        Layout.minimumWidth: 380
        Layout.preferredWidth: 440
        Layout.minimumHeight: 360
        Layout.preferredHeight: 460
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            QuickControls { backend: liveBackend; visible: root.selection === ""; Layout.fillWidth: true; Layout.fillHeight: true }
            RowLayout {
                visible: root.selection === ""
                PC.Button { text: "Redes Wi-Fi"; Layout.fillWidth: true; enabled: liveBackend.wifiOn; onClicked: root.selection = "wifi" }
                PC.Button { text: "Dispositivos Bluetooth"; Layout.fillWidth: true; enabled: liveBackend.bluetoothOn; onClicked: root.selection = "bluetooth" }
            }
            Loader {
                Layout.fillWidth: true; Layout.fillHeight: true
                visible: active; active: root.selection !== ""
                sourceComponent: root.selection === "wifi" ? wifiPage : bluetoothPage
            }
            Component { id: wifiPage; WifiPage { backend: liveBackend; onBack: root.selection = "" } }
            Component { id: bluetoothPage; BluetoothPage { backend: liveBackend; onBack: root.selection = "" } }
            PC.ToolButton {
                text: "Mais configurações"; icon.name: "configure"
                onClicked: advanced.open()
                PC.Menu {
                    id: advanced
                    function settings(module) { KCMUtils.KCMLauncher.openSystemSettings(module); root.expanded=false; }
                    PC.MenuItem { text: "Redes e VPN"; onTriggered: advanced.settings("kcm_networkmanagement") }
                    PC.MenuItem { text: "Dispositivos Bluetooth"; onTriggered: advanced.settings("kcm_bluetooth") }
                    PC.MenuItem { text: "Saídas de áudio"; onTriggered: advanced.settings("kcm_pulseaudio") }
                    PC.MenuItem { text: "Telas"; onTriggered: advanced.settings("kcm_kscreen") }
                    PC.MenuItem { text: "Energia"; onTriggered: advanced.settings("kcm_powerdevilprofilesconfig") }
                    PC.MenuItem { text: "Luz noturna"; onTriggered: advanced.settings("kcm_nightlight") }
                }
            }
        }
    }
}
