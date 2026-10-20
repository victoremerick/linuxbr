import QtQuick 2.15
import calamares.slideshow 1.0
Presentation {
    Slide {
        Image {
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.35, 240)
            height: width
            source: "logo.svg"
            fillMode: Image.PreserveAspectFit
        }
    }
}
