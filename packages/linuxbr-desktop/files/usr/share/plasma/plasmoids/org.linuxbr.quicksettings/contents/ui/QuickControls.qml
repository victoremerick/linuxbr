// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC
import org.kde.kirigami as Kirigami

PC.ScrollView {
    id: controls
    required property QtObject backend
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: controls.availableWidth
        spacing: 14
        Kirigami.Heading { text: "Configurações rápidas"; level: 2; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            PC.Button {
                id: wifi; objectName: "wifiToggle"
                Layout.fillWidth: true; Layout.preferredHeight: 76
                text: !controls.backend.wifiAvailable ? "Wi-Fi indisponível" : controls.backend.wifiBlocked ? "Wi-Fi bloqueado" : controls.backend.wifiBusy ? "Alterando Wi-Fi…" : "Wi-Fi " + (controls.backend.wifiOn ? "ligado" : "desligado")
                icon.name: "network-wireless"
                display: PC.AbstractButton.TextUnderIcon
                enabled: controls.backend.wifiAvailable && !controls.backend.wifiBlocked && !controls.backend.wifiBusy
                // Never display an optimistic state before the service confirms it.
                highlighted: controls.backend.wifiOn
                onClicked: controls.backend.setWifi(!controls.backend.wifiOn)
                Accessible.name: text
            }
            PC.Button {
                objectName: "bluetoothToggle"
                Layout.fillWidth: true; Layout.preferredHeight: 76
                text: !controls.backend.bluetoothAvailable ? "Bluetooth indisponível" : controls.backend.bluetoothBlocked ? "Bluetooth bloqueado" : controls.backend.bluetoothBusy ? "Alterando Bluetooth…" : "Bluetooth " + (controls.backend.bluetoothOn ? "ligado" : "desligado")
                icon.name: "preferences-system-bluetooth"
                display: PC.AbstractButton.TextUnderIcon
                enabled: controls.backend.bluetoothAvailable && !controls.backend.bluetoothBlocked && !controls.backend.bluetoothBusy
                highlighted: controls.backend.bluetoothOn
                onClicked: controls.backend.setBluetooth(!controls.backend.bluetoothOn)
                Accessible.name: text
            }
        }
        PC.Label {
            text: controls.backend.errorMessage; visible: text.length > 0
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            color: Kirigami.Theme.negativeTextColor
        }
        PC.Label { text: "Volume"; font.bold: true }
        PC.Label {
            text: controls.backend.audioName; Layout.fillWidth: true
            elide: Text.ElideRight
        }
        RowLayout {
            Layout.fillWidth: true
            PC.ToolButton {
                objectName: "muteToggle"
                icon.name: controls.backend.muted ? "audio-volume-muted" : "audio-volume-high"
                text: controls.backend.muted ? "Ativar som" : "Silenciar"
                display: PC.AbstractButton.IconOnly
                enabled: controls.backend.audioAvailable
                onClicked: controls.backend.setMuted(!controls.backend.muted)
                Accessible.name: text
                PC.ToolTip { text: parent.text }
            }
            PC.Slider {
                id: volume; objectName: "volumeSlider"
                Layout.fillWidth: true
                from: 0; to: 100; stepSize: 1
                enabled: controls.backend.audioAvailable
                Accessible.name: "Volume da saída padrão"
                onMoved: controls.backend.setVolume(value)
                Binding { target: volume; property: "value"; value: Math.min(100, controls.backend.volume); when: !volume.pressed; restoreMode: Binding.RestoreNone }
            }
            PC.Label { text: controls.backend.audioAvailable ? controls.backend.volume + "%" : "—"; Layout.minimumWidth: 45 }
        }
        PC.Label { text: controls.backend.muted ? "Som silenciado" : ""; visible: controls.backend.muted }
        PC.Label { text: "Brilho"; font.bold: true }
        PC.Label {
            text: "Ajuste indisponível nesta tela"; visible: brightnessRows.count === 0
            Layout.fillWidth: true; wrapMode: Text.WordWrap
        }
        Repeater {
            id: brightnessRows
            model: controls.backend.displays
            delegate: ColumnLayout {
                id: displayRow
                required property string displayName
                required property string label
                required property int brightness
                required property int maxBrightness
                Layout.fillWidth: true
                PC.Label { text: displayRow.label; elide: Text.ElideRight; Layout.fillWidth: true }
                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Icon { source: "video-display-brightness"; Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                    PC.Slider {
                        id: light; objectName: "brightness_" + displayRow.displayName
                        Layout.fillWidth: true
                        from: 0; to: Math.max(1, displayRow.maxBrightness)
                        stepSize: Math.max(1, Math.round(displayRow.maxBrightness / 100))
                        enabled: displayRow.maxBrightness > 0
                        Accessible.name: "Brilho de " + displayRow.label
                        onMoved: controls.backend.setBrightness(displayRow.displayName, Math.round(value))
                        Binding { target: light; property: "value"; value: displayRow.brightness; when: !light.pressed; restoreMode: Binding.RestoreNone }
                    }
                    PC.Label { text: displayRow.maxBrightness > 0 ? Math.round(displayRow.brightness * 100 / displayRow.maxBrightness) + "%" : "—"; Layout.minimumWidth: 45 }
                }
            }
        }
    }
}
