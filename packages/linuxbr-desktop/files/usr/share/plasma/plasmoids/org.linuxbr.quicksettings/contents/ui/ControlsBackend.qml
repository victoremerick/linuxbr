// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.networkmanagement as NM
import org.kde.bluezqt as BluezQt
import org.kde.plasma.private.volume as Audio
import org.kde.plasma.private.brightnesscontrolplugin as Brightness

Item {
    id: backend
    visible: false
    NM.AvailableDevices { id: devices }
    NM.EnabledConnections { id: radios }
    NM.Handler { id: network }
    Audio.SinkModel { id: sinks } // Keep the audio context and preferred-device model alive.
    Brightness.ScreenBrightnessControl { id: screens; isSilent: true }

    property string errorMessage: ""
    readonly property bool wifiAvailable: devices.wirelessDeviceAvailable
    readonly property bool wifiBlocked: !radios.wirelessHwEnabled || NM.Configuration.airplaneModeEnabled || !radios.networkingEnabled
    readonly property bool wifiOn: wifiAvailable && radios.wirelessHwEnabled && radios.wirelessEnabled
    readonly property bool wifiBusy: wifiTimeout.running
    property bool wifiWanted: false
    function setWifi(on) {
        if (!wifiAvailable || wifiBlocked || wifiBusy) return;
        errorMessage = ""; wifiWanted = on; wifiTimeout.start();
        network.enableWireless(on);
    }
    onWifiOnChanged: if (wifiTimeout.running && wifiOn === wifiWanted) wifiTimeout.stop()
    Timer {
        id: wifiTimeout; interval: 5000
        onTriggered: if (backend.wifiOn !== backend.wifiWanted) backend.errorMessage = "Não foi possível alterar o Wi-Fi. Verifique bloqueios e permissões de rede.";
    }

    readonly property bool bluetoothAvailable: BluezQt.Manager.adapters.length > 0 || BluezQt.Manager.rfkill.state !== BluezQt.Rfkill.Unknown
    readonly property bool bluetoothBlocked: BluezQt.Manager.rfkill.state === BluezQt.Rfkill.HardBlocked
    readonly property bool bluetoothOn: BluezQt.Manager.bluetoothOperational && !BluezQt.Manager.bluetoothBlocked
    readonly property bool bluetoothBusy: bluetoothTimeout.running
    property bool bluetoothWanted: false
    function setBluetooth(on) {
        if (!bluetoothAvailable || bluetoothBlocked || bluetoothBusy) return;
        errorMessage = ""; bluetoothWanted = on; bluetoothTimeout.start();
        BluezQt.Manager.bluetoothBlocked = !on;
        for (const adapter of BluezQt.Manager.adapters) adapter.powered = on;
    }
    onBluetoothOnChanged: if (bluetoothTimeout.running && bluetoothOn === bluetoothWanted) bluetoothTimeout.stop()
    Connections {
        target: BluezQt.Manager
        function onAdapterAdded(adapter) {
            if (bluetoothTimeout.running) adapter.powered = backend.bluetoothWanted;
        }
    }
    Timer {
        id: bluetoothTimeout; interval: 5000
        onTriggered: if (backend.bluetoothOn !== backend.bluetoothWanted) backend.errorMessage = "Não foi possível alterar o Bluetooth. Verifique bloqueios e permissões do dispositivo.";
    }

    readonly property var sink: Audio.PreferredDevice.sink
    readonly property bool audioAvailable: sink !== null && sink !== undefined && sink.name !== "auto_null"
    readonly property string audioName: audioAvailable ? (sink.description || sink.name) : "Nenhuma saída de áudio disponível"
    readonly property real volume: audioAvailable ? Math.round(sink.volume / Audio.PulseAudio.NormalVolume * 100) : 0
    readonly property bool muted: audioAvailable && sink.muted
    function setVolume(percent) {
        if (!audioAvailable) return;
        sink.volume = Math.round(Math.max(0, Math.min(100, percent)) * Audio.PulseAudio.NormalVolume / 100);
    }
    function setMuted(value) { if (audioAvailable) sink.muted = value; }

    readonly property var displays: screens.displays
    function setBrightness(name, value) { screens.setBrightness(name, Math.round(value)); }
}
