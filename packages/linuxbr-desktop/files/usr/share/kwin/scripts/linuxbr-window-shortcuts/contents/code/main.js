// SPDX-License-Identifier: GPL-3.0-or-later
// KWin 6: workspace.activeWindow, Window.maximizeMode and setMaximize().
// Enabled in /etc/skel only. Existing shortcut choices are never migrated.
"use strict";

var minimizedByLinuxBR = [];
var previouslyActive = null;

function activeApplication() {
    var window = workspace.activeWindow;
    if (!window || window.desktopWindow || window.dock || window.fullScreen || window.popupWindow) {
        return null;
    }
    return window;
}

registerShortcut("LinuxBR Maximize", "Linux BR: maximizar janela", "Meta+Up", function () {
    var window = activeApplication();
    if (window && window.maximizable) {
        // Deliberately not a toggle: repeated Up keeps the window maximized.
        window.setMaximize(true, true);
    }
});

registerShortcut("LinuxBR Restore or Minimize", "Linux BR: restaurar ou minimizar janela", "Meta+Down", function () {
    var window = activeApplication();
    if (!window) return;
    // MaximizeRestore is 0 in the KWin 6 MaximizeMode enum.
    if (window.maximizeMode !== 0) {
        window.setMaximize(false, false);
    } else if (window.minimizable) {
        window.minimized = true;
    }
});

function onCurrentDesktop(window) {
    return (!window.desktops.length || window.desktops.indexOf(workspace.currentDesktop) !== -1)
        && (!window.activities.length || window.activities.indexOf(workspace.currentActivity) !== -1);
}

registerShortcut("LinuxBR Minimize All", "Linux BR: minimizar todas as janelas", "Meta+M", function () {
    var windows = workspace.windowList();
    if (minimizedByLinuxBR.length === 0) previouslyActive = workspace.activeWindow;
    for (var i = 0; i < windows.length; i++) {
        var window = windows[i];
        if (window.minimizable && !window.minimized && onCurrentDesktop(window)) {
            if (minimizedByLinuxBR.indexOf(window) === -1) minimizedByLinuxBR.push(window);
            window.minimized = true;
        }
    }
});

registerShortcut("LinuxBR Restore All", "Linux BR: restaurar janelas minimizadas", "Meta+Shift+M", function () {
    var windows = workspace.windowList();
    for (var i = 0; i < minimizedByLinuxBR.length; i++) {
        var window = minimizedByLinuxBR[i];
        if (windows.indexOf(window) !== -1 && onCurrentDesktop(window)) window.minimized = false;
    }
    if (previouslyActive && windows.indexOf(previouslyActive) !== -1 && onCurrentDesktop(previouslyActive)) {
        workspace.activeWindow = previouslyActive;
    }
    minimizedByLinuxBR = [];
    previouslyActive = null;
});

workspace.windowRemoved.connect(function (window) {
    var index = minimizedByLinuxBR.indexOf(window);
    if (index !== -1) minimizedByLinuxBR.splice(index, 1);
    if (previouslyActive === window) previouslyActive = null;
});

registerShortcut("LinuxBR New Desktop", "Linux BR: nova área de trabalho", "Meta+Ctrl+D", function () {
    var count = workspace.desktops.length;
    workspace.createDesktop(count, "Área de trabalho " + (count + 1));
    if (workspace.desktops.length > count) workspace.currentDesktop = workspace.desktops[count];
});

registerShortcut("LinuxBR Close Desktop", "Linux BR: fechar área de trabalho", "Meta+Ctrl+F4", function () {
    var desktops = workspace.desktops;
    if (desktops.length < 2) return;
    var current = workspace.currentDesktop;
    var index = desktops.indexOf(current);
    workspace.currentDesktop = desktops[index > 0 ? index - 1 : 1];
    // KWin reassigns windows when a desktop is removed; no application is closed.
    workspace.removeDesktop(current);
});
