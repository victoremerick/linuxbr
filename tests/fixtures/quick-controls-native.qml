// SPDX-License-Identifier: GPL-3.0-or-later
// For disposable VMs only: this fixture operates the current session's devices.
import QtQuick
import "../../packages/linuxbr-desktop/files/usr/share/plasma/plasmoids/org.linuxbr.quicksettings/contents/ui" as Quick
Item {
    width: 440; height: 540
    property alias controller: liveControls
    Quick.ControlsBackend { id: liveControls }
    Quick.QuickControls { anchors.fill: parent; backend: liveControls }
}
