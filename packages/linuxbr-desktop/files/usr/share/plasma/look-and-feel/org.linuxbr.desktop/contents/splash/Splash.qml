import QtQuick

Rectangle {
    id: root
    color: "#10191f"
    property int stage: 0

    Image {
        id: logo
        source: "file:///usr/share/linuxbr/identity/symbol-color.svg"
        width: 128
        height: 128
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.36 - height / 2
        fillMode: Image.PreserveAspectFit
    }
    Text {
        text: "Linux BR"
        color: "#e6ebed"
        font.pixelSize: 16
        anchors.horizontalCenter: parent.horizontalCenter
        y: logo.y + logo.height + 12
    }
    Item {
        id: spinner
        width: 64
        height: 64
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.64 - height / 2
        Repeater {
            model: 12
            Rectangle {
                required property int index
                width: 6
                height: 6
                radius: 3
                color: "#e4df91"
                opacity: (index + 1) / 12
                x: 29 + 24 * Math.sin(index * Math.PI / 6)
                y: 29 - 24 * Math.cos(index * Math.PI / 6)
            }
        }
        RotationAnimator on rotation {
            from: 0
            to: 360
            duration: 1000
            loops: Animation.Infinite
            running: true
        }
    }
}
