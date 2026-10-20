#!/usr/bin/python3
"""Version-checked, reversible presentation patches for Debian Plasma 6.3.

Keep the upstream applets, models, translations, actions and notification server.
Never guess when an upstream layout changes; keep that component unmodified.
"""
import argparse
import hashlib
import json
from pathlib import Path


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('upstream layout changed: '+old[:65])
    return text.replace(old, new, 1)


def patches():
    return {
      'org.kde.plasma.kickoff/contents/ui/main.qml': [
        ('    Plasmoid.contextualActions: [\n        PlasmaCore.Action {\n            text: i18n("Edit Applications…")', '''    Plasmoid.contextualActions: [
            PlasmaCore.Action { text: "Aplicativos instalados"; onTriggered: Qt.openUrlExternally("linuxbr-action:///apps") },
            PlasmaCore.Action { text: "Energia"; onTriggered: Qt.openUrlExternally("linuxbr-action:///power-settings") },
            PlasmaCore.Action { text: "Logs do sistema"; onTriggered: Qt.openUrlExternally("linuxbr-action:///logs") },
            PlasmaCore.Action { text: "Sistema"; onTriggered: Qt.openUrlExternally("linuxbr-action:///system") },
            PlasmaCore.Action { text: "Gerenciador de dispositivos"; onTriggered: Qt.openUrlExternally("linuxbr-action:///devices") },
            PlasmaCore.Action { text: "Usuários e grupos"; onTriggered: Qt.openUrlExternally("linuxbr-action:///users") },
            PlasmaCore.Action { text: "Conexões de rede e IP/DNS"; onTriggered: Qt.openUrlExternally("linuxbr-action:///network") },
            PlasmaCore.Action { text: "Gerenciamento de discos"; onTriggered: Qt.openUrlExternally("linuxbr-action:///disks") },
            PlasmaCore.Action { text: "Firewall"; onTriggered: Qt.openUrlExternally("linuxbr-action:///firewall") },
            PlasmaCore.Action { text: "Áudio e mixer"; onTriggered: Qt.openUrlExternally("linuxbr-action:///audio") },
            PlasmaCore.Action { text: "Terminal"; onTriggered: Qt.openUrlExternally("linuxbr-action:///terminal") },
            PlasmaCore.Action { text: "Gerenciador de Tarefas"; onTriggered: Qt.openUrlExternally("linuxbr-action:///tasks") },
            PlasmaCore.Action { text: "Central do Sistema"; onTriggered: Qt.openUrlExternally("linuxbr-action:///settings") },
            PlasmaCore.Action { text: "Explorador de arquivos"; onTriggered: Qt.openUrlExternally("linuxbr-action:///files") },
            PlasmaCore.Action { text: "Pesquisar"; onTriggered: Qt.openUrlExternally("linuxbr-action:///search") },
            PlasmaCore.Action { text: "Executar…"; onTriggered: Qt.openUrlExternally("linuxbr-action:///run") },
            PlasmaCore.Action { text: "Desligar ou sair…"; onTriggered: Qt.openUrlExternally("linuxbr-action:///logout") },
        PlasmaCore.Action {
            text: i18n("Edit Applications…")''')],
      'org.kde.plasma.kickoff/contents/ui/NormalPage.qml': [
        ('import QtQuick\n', 'import QtQuick\nimport QtQuick.Layouts\n'),
        ('    contentItem: HorizontalStackView {', '''    contentItem: RowLayout {
        spacing: 12
        HorizontalStackView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 460'''),
        ('    footer: Footer {', '''        // Linux BR: pinned tiles stay beside the application list.
        DropAreaGridView {
            Layout.preferredWidth: 280
            Layout.fillHeight: true
            model: kickoff.rootModel.favoritesModel
            visible: footer.tabBar.currentIndex === 0
        }
    }

    footer: Footer {''')],
      'org.kde.plasma.kickoff/contents/ui/ApplicationsPage.qml': [
        ('initialItem: preferredFavoritesViewComponent', 'initialItem: preferredAllAppsViewComponent'),
        ('property int appsModelRow: 0', 'property int appsModelRow: 1')],
      'org.kde.plasma.kickoff/contents/ui/KickoffListView.qml': [
        ('currentIndex: count > 0 ? 0 : -1', 'currentIndex: count > 0 ? (model === kickoff.rootModel ? 1 : 0) : -1'),
        ('view.currentIndex = 0', 'view.currentIndex = view.model === kickoff.rootModel ? 1 : 0')],
      'org.kde.plasma.notifications/contents/ui/CompactRepresentation.qml': [
        ('    id: compactRoot', '    id: compactRoot\n    anchors.fill: parent\n    implicitWidth: 32\n    implicitHeight: 32')],
      'org.kde.plasma.notifications/contents/ui/main.qml': [
        ('import QtQuick 2.8', 'import QtQuick 2.8\nimport QtQuick.Layouts'),
        ('    id: root', '    id: root\n    Layout.minimumWidth: 32\n    Layout.minimumHeight: 32\n    preferredRepresentation: compactRepresentation')],
      'org.kde.plasma.notifications/contents/ui/FullRepresentation.qml': [
        ('import QtQuick\n', 'import QtQuick\nimport QtQuick.Window\n'),
        ('Layout.preferredWidth: Kirigami.Units.gridUnit * 18', 'Layout.preferredWidth: Kirigami.Units.gridUnit * 22'),
        ('Layout.preferredHeight: Kirigami.Units.gridUnit * 24', 'Layout.preferredHeight: Math.min(Screen.desktopAvailableHeight * 0.85, Kirigami.Units.gridUnit * 42)'),
        ('Layout.maximumHeight: Kirigami.Units.gridUnit * 40', 'Layout.maximumHeight: Kirigami.Units.gridUnit * 48')],
      'org.kde.plasma.private.systemtray/contents/ui/HiddenItemsView.qml': [
        ('readonly property int columns: 2', 'readonly property int columns: 3'),
        ('readonly property int delegateHeight: (metrics.height * delegateMaxTextLines) + (delegateMargins * 2)', 'readonly property int delegateHeight: Math.max(80, (metrics.height * delegateMaxTextLines) + (delegateMargins * 2))')],
    }


def apply(root, restore=False):
    base=root/'usr/share/plasma/plasmoids'
    state=root/'var/lib/linuxbr/plasma-layout';state.mkdir(parents=True,exist_ok=True)
    manifest=state/'manifest.json'
    records=json.loads(manifest.read_text()) if manifest.exists() else {}
    for name,edits in patches().items():
        path=base/name
        if not path.exists():continue
        text=path.read_text();digest=hashlib.sha256(text.encode()).hexdigest()
        record=records.get(name)
        if restore:
            if record and digest==record['patched']:
                path.write_text(record['original'])
            records.pop(name,None)
            continue
        if record and digest==record['patched']:continue
        try:
            changed=text
            for old,new in edits:changed=replace(changed,old,new)
        except ValueError as error:
            print('Linux BR: mantendo '+name+': '+str(error));continue
        records[name]={'original':text,'patched':hashlib.sha256(changed.encode()).hexdigest()}
        path.write_text(changed)
    manifest.write_text(json.dumps(records,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/'));parser.add_argument('--restore',action='store_true')
    args=parser.parse_args();apply(args.root,args.restore)
