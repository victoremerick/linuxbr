#!/usr/bin/python3
"""Version-checked, reversible presentation patches for Debian Plasma 6.3.

Keep the upstream applets, models, translations, actions and notification server.
Never guess when an upstream layout changes; keep that component unmodified.
"""
import argparse
import hashlib
import json
from pathlib import Path

RETIRED_PATCHES = ('org.kde.plasma.taskmanager/contents/ui/main.qml',)


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('upstream layout changed: '+old[:65])
    return text.replace(old, new, 1)


def patches():
    return {
      "org.kde.panel/contents/ui/main.qml": [( "    id: root", "    id: root\n    Plasmoid.contextualActions: [\n        PlasmaCore.Action { text: \"Gerenciador de Tarefas\"; icon.name: \"utilities-system-monitor\"; onTriggered: Qt.openUrlExternally(\"linuxbr-action:///tasks\") }\n    ]" )],
      "org.kde.plasma.taskmanager/contents/ui/ContextMenu.qml": [
        ("    id: menu", """    id: menu
    PlasmaExtras.MenuItem {
        text: "Gerenciador de Tarefas"
        icon: "utilities-system-monitor"
        onClicked: Qt.openUrlExternally("linuxbr-action:///tasks")
    }
    PlasmaExtras.MenuItem {
        text: "Mídia e microfone deste aplicativo"
        icon: "audio-volume-high"
        visible: menu.visualParent && !menu.get(atm.IsLauncher) && Number(menu.get(atm.AppPid)) > 1
        onClicked: Qt.openUrlExternally("linuxbr-action:///app-audio/" + Math.trunc(Number(menu.get(atm.AppPid))))
    }
    PlasmaExtras.MenuItem { separator: true }""")],
      'org.kde.plasma.kickoff/contents/ui/main.qml': [
        ('''        Component.onCompleted: {
            favoritesModel.initForClient("org.kde.plasma.kickoff.favorites.instance-" + Plasmoid.id)

            if (!Plasmoid.configuration.favoritesPortedToKAstats) {
                if (favoritesModel.count < 1) {
                    favoritesModel.portOldFavorites(Plasmoid.configuration.favorites);
                }
                Plasmoid.configuration.favoritesPortedToKAstats = true;
            }
        }''', '''        // Wait until the initial layout has written the distribution favorites.
        Component.onCompleted: Qt.callLater(() => {
            favoritesModel.initForClient("org.kde.plasma.kickoff.favorites.instance-" + Plasmoid.id)

            if (!Plasmoid.configuration.favoritesPortedToKAstats) {
                if (favoritesModel.count < 1) {
                    favoritesModel.portOldFavorites(Plasmoid.configuration.favorites);
                }
                Plasmoid.configuration.favoritesPortedToKAstats = true;
            }
        })'''),
        ('    Plasmoid.contextualActions: [\n        PlasmaCore.Action {\n            text: i18n("Edit Applications…")', '''    Plasmoid.contextualActions: [
            PlasmaCore.Action { text: "Aplicativos instalados"; icon.name: "applications-all"; onTriggered: Qt.openUrlExternally("linuxbr-action:///apps") },
            PlasmaCore.Action { text: "Energia"; icon.name: "preferences-system-power-management"; onTriggered: Qt.openUrlExternally("linuxbr-action:///power-settings") },
            PlasmaCore.Action { text: "Logs do sistema"; icon.name: "view-list-text"; onTriggered: Qt.openUrlExternally("linuxbr-action:///logs") },
            PlasmaCore.Action { text: "Sobre o sistema"; icon.name: "help-about"; onTriggered: Qt.openUrlExternally("linuxbr-action:///system") },
            PlasmaCore.Action { text: "Gerenciador de dispositivos"; icon.name: "preferences-devices-tree"; onTriggered: Qt.openUrlExternally("linuxbr-action:///devices") },
            PlasmaCore.Action { text: "Usuários e grupos"; icon.name: "system-users"; onTriggered: Qt.openUrlExternally("linuxbr-action:///users") },
            PlasmaCore.Action { text: "Conexões de rede"; icon.name: "network-workgroup"; onTriggered: Qt.openUrlExternally("linuxbr-action:///network") },
            PlasmaCore.Action { text: "Gerenciamento de discos"; icon.name: "drive-harddisk"; onTriggered: Qt.openUrlExternally("linuxbr-action:///disks") },
            PlasmaCore.Action { text: "Firewall"; icon.name: "security-high"; onTriggered: Qt.openUrlExternally("linuxbr-action:///firewall") },
            PlasmaCore.Action { text: "Áudio e mixer"; icon.name: "audio-volume-high"; onTriggered: Qt.openUrlExternally("linuxbr-action:///audio") },
            PlasmaCore.Action { text: "Terminal"; icon.name: "utilities-terminal"; onTriggered: Qt.openUrlExternally("linuxbr-action:///terminal") },
            PlasmaCore.Action { text: "Configurações"; icon.name: "preferences-system"; onTriggered: Qt.openUrlExternally("linuxbr-action:///settings") },
            PlasmaCore.Action { text: "Explorador de arquivos"; icon.name: "system-file-manager"; onTriggered: Qt.openUrlExternally("linuxbr-action:///files") },
            PlasmaCore.Action { text: "Pesquisar"; icon.name: "system-search"; onTriggered: Qt.openUrlExternally("linuxbr-action:///search") },
            PlasmaCore.Action { text: "Executar…"; icon.name: "system-run"; onTriggered: Qt.openUrlExternally("linuxbr-action:///run") },
            PlasmaCore.Action { text: "Desligar ou sair…"; icon.name: "system-log-out"; onTriggered: Qt.openUrlExternally("linuxbr-action:///logout") },
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
        ('import QtQuick\n', 'import QtQuick\nimport QtQuick.Window\nimport org.kde.plasma.plasma5support as LinuxBRSupport\n'),
        ('PlasmaExtras.Representation {', '''PlasmaExtras.Representation {

    LinuxBRSupport.DataSource {
        id: linuxbrNotificationRouter
        engine: "executable"
        property string pendingCommand: ""
        property var openAction: null
        function route(entry, action) {
            if (!/^[A-Za-z0-9_][A-Za-z0-9_.+-]{0,248}$/.test(entry || "") || openAction) {
                action();
                return;
            }
            pendingCommand = "/usr/bin/linuxbr-workspaces --notification " + entry;
            openAction = action;
            connectSource(pendingCommand);
            linuxbrNotificationTimeout.restart();
        }
        function finish() {
            const action = openAction;
            disconnectSource(pendingCommand);
            linuxbrNotificationTimeout.stop();
            openAction = null;
            pendingCommand = "";
            if (action) {
                action();
            }
        }
        onNewData: (sourceName, data) => {
            if (sourceName === pendingCommand) {
                finish();
            }
        }
    }
    Timer {
        id: linuxbrNotificationTimeout
        interval: 3500
        repeat: false
        onTriggered: linuxbrNotificationRouter.finish()
    }'''),
        ('                    historyModel.invokeDefaultAction(idx);', '''                    const entry = historyModel.data(idx, NotificationManager.Notifications.DesktopEntryRole);
                    linuxbrNotificationRouter.route(entry, function() {
                        if (historyModel.data(idx, NotificationManager.Notifications.DesktopEntryRole) === entry) {
                            historyModel.invokeDefaultAction(idx);
                        }
                    });'''),
        ('''                        onActionInvoked: {
                            if (actionName === "default") {
                                historyModel.invokeDefaultAction(historyModel.index(index, 0));
                            } else {
                                historyModel.invokeAction(historyModel.index(index, 0), actionName);
                            }

                            delegateLoader.expire();
                        }''', '''                        onActionInvoked: {
                             const idx = historyModel.index(index, 0);
                             const entry = model.desktopEntry;
                             const selectedAction = actionName;
                             linuxbrNotificationRouter.route(entry, function() {
                                 if (historyModel.data(idx, NotificationManager.Notifications.DesktopEntryRole) !== entry) {
                                     return;
                                 }
                                 if (selectedAction === "default") {
                                     historyModel.invokeDefaultAction(idx);
                                 } else {
                                     historyModel.invokeAction(idx, selectedAction);
                                 }
                                 delegateLoader.expire();
                             });
                        }'''),
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
    # The panel supplies the task manager action to empty applet menus.
    # Retire the previous applet action on upgrades without overwriting edits.
    for name in RETIRED_PATCHES:
        record=records.pop(name,None)
        path=base/name
        if record and path.is_file():
            digest=hashlib.sha256(path.read_text().encode()).hexdigest()
            if digest==record['patched']:
                path.write_text(record['original'])
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
        # Reapply from the saved upstream source so package upgrades can revise
        # our patch definitions without accumulating edits or losing restore.
        if record and digest==record['patched']:
            text=record['original']
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
