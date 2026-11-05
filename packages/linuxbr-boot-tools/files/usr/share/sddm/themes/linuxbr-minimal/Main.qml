import QtQuick
import QtQuick.Controls.Basic as Controls
import QtQuick.VirtualKeyboard
import org.linuxbr.boot 1.0

Rectangle {
    id: root
    width: 1280
    height: 768
    color: "#101820"
    property bool authenticating: false
    property bool keyboardVisible: false
    function login() {
        if (!username.text.length || !password.text.length || authenticating) return;
        error.text = "";
        authenticating = true;
        sddm.login(username.text, password.text, 0);
    }
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: root.keyboardVisible ? -130 : 0
        width: Math.min(380, root.width - 64)
        spacing: root.keyboardVisible ? 8 : 16
        Image {
            visible: !root.keyboardVisible
            source: "/usr/share/linuxbr/identity/symbol-color.svg"
            width: 84; height: 84
            anchors.horizontalCenter: parent.horizontalCenter
            fillMode: Image.PreserveAspectFit
        }
        Text {
            text: "Linux BR"
            visible: !root.keyboardVisible
            color: "#edf4fa"; font.pixelSize: 32
            anchors.horizontalCenter: parent.horizontalCenter
        }
        Text {
            text: "Entre para acessar a configuração e manutenção."
            visible: !root.keyboardVisible
            width: parent.width; wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: "#c6d4e0"; font.pixelSize: 15
        }
        Controls.TextField {
            id: username
            width: parent.width; height: 46
            placeholderText: "Usuário"
            text: userModel.lastUser || config.liveUser || ""
            font.pixelSize: 18
            enabled: !root.authenticating
            Accessible.name: "Usuário"
            KeyNavigation.tab: password
            onAccepted: password.forceActiveFocus()
        }
        Controls.TextField {
            id: password
            width: parent.width; height: 46
            placeholderText: "Senha"
            font.pixelSize: 18
            echoMode: TextInput.Password
            enabled: !root.authenticating
            Accessible.name: "Senha"
            KeyNavigation.tab: enter
            onAccepted: root.login()
        }
        Controls.Button {
            id: enter
            text: root.authenticating ? "Entrando…" : "Entrar"
            width: parent.width; height: 46
            enabled: !root.authenticating
            font.pixelSize: 18
            onClicked: root.login()
        }
        Text {
            id: error
            width: parent.width; wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            color: "#ffb7b7"; font.pixelSize: 15
        }
        Text {
            text: config.liveHint || ""
            visible: text.length > 0 && !root.keyboardVisible
            width: parent.width; wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            horizontalAlignment: Text.AlignHCenter
            color: "#c6d4e0"; font.pixelSize: 14
        }
        Row {
            spacing: 12
            anchors.horizontalCenter: parent.horizontalCenter
            Controls.Button {
                text: "Reiniciar"
                enabled: sddm.canReboot && !root.authenticating
                onClicked: {
                    if (!Boot.shiftHeld() || Boot.prepareRecovery()) sddm.reboot();
                    else error.text = Boot.lastError;
                }
            }
            Controls.Button {
                text: "Desligar"
                enabled: sddm.canPowerOff && !root.authenticating
                onClicked: sddm.powerOff()
            }
        }
        Text {
            text: "Shift + Reiniciar abre a recuperação no próximo boot."
            visible: !root.keyboardVisible
            width: parent.width; wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: "#c6d4e0"; font.pixelSize: 13
        }
    }
    Item {
        id: keyboardArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Math.min(300, root.height * 0.4)
        visible: root.keyboardVisible
        InputPanel {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            width: root.width
            scale: Math.min(1, keyboardArea.height / height)
            transformOrigin: Item.Bottom
        }
    }
    Controls.Button {
        anchors.right: parent.right
        anchors.bottom: root.keyboardVisible ? keyboardArea.top : parent.bottom
        anchors.margins: 16
        text: root.keyboardVisible ? "Ocultar teclado" : "Teclado na tela"
        onClicked: {
            root.keyboardVisible = !root.keyboardVisible;
            if (root.keyboardVisible) { password.forceActiveFocus(); Qt.inputMethod.show(); }
            else Qt.inputMethod.hide();
        }
    }
    Connections {
        target: sddm
        function onLoginFailed() {
            root.authenticating = false;
            password.clear();
            error.text = "Não foi possível entrar. Confira o usuário e a senha.";
            password.forceActiveFocus();
        }
    }
    Component.onCompleted: {
        if (username.text.length) password.forceActiveFocus();
        else username.forceActiveFocus();
    }
}
