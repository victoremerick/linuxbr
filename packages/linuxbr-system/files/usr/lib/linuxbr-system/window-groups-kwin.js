// SPDX-License-Identifier: GPL-3.0-or-later
(function () {
    "use strict";

    function usable(window) {
        return window.normalWindow && !window.skipTaskbar && !window.fullScreen &&
            (!window.desktops.length || window.desktops.indexOf(workspace.currentDesktop) >= 0) &&
            (!window.activities.length || window.activities.indexOf(workspace.currentActivity) >= 0);
    }

    function application(window) {
        const name = String(window.desktopFileName || "");
        return name && (name.endsWith(".desktop") ? name : name + ".desktop");
    }

    function report(value) {
        callDBus(linuxbrReceiver, "/WindowGroups", "org.linuxbr.WindowGroups", "complete", JSON.stringify(value));
    }

    const windows = workspace.windowList().filter(usable);
    if (linuxbrPlan.length === 0) {
        report(windows.map(window => {
            const area = workspace.clientArea(KWin.PlacementArea, window.output, workspace.currentDesktop);
            const frame = window.frameGeometry;
            return {
                application: application(window),
                monitor: window.output.name,
                x: Math.round(frame.x - area.x), y: Math.round(frame.y - area.y),
                width: Math.round(frame.width), height: Math.round(frame.height),
                maximize: Number(window.maximizeMode), minimized: window.minimized,
            };
        }));
        return;
    }

    const used = [];
    const missing = [];
    for (const entry of linuxbrPlan) {
        const window = windows.find(candidate => !used.includes(candidate) && application(candidate) === entry.application);
        if (!window) {
            missing.push(entry.application);
            continue;
        }
        used.push(window);
        const screen = workspace.screens.find(output => output.name === entry.monitor) || workspace.activeScreen;
        if (!screen) {
            missing.push(entry.application);
            continue;
        }
        if (window.output !== screen && window.moveableAcrossScreens) workspace.sendClientToScreen(window, screen);
        const area = workspace.clientArea(KWin.PlacementArea, window.output, workspace.currentDesktop);
        if (window.maximizable) window.setMaximize(false, false);
        const frame = window.frameGeometry;
        if (window.resizeable) {
            frame.width = Math.min(area.width, entry.width);
            frame.height = Math.min(area.height, entry.height);
        }
        if (window.moveable) {
            frame.x = Math.round(area.x + Math.max(0, Math.min(entry.x, area.width - frame.width)));
            frame.y = Math.round(area.y + Math.max(0, Math.min(entry.y, area.height - frame.height)));
        }
        if (window.moveable || window.resizeable) window.frameGeometry = frame;
        if (window.maximizable) window.setMaximize(Boolean(entry.maximize & 1), Boolean(entry.maximize & 2));
        if (window.minimizable) window.minimized = entry.minimized;
    }
    report(missing);
})();
