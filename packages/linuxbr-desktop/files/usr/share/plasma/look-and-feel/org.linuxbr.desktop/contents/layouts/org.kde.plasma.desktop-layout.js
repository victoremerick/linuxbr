// Used by Plasma when creating the initial layout, not on every login.
// Do not replace panels when invoked against an already configured desktop.
if (panels().length === 0) {
    var panel = new Panel;
    panel.location = "bottom";
    panel.floating = false;
    panel.opacity = "translucent";
    panel.height = 2 * Math.ceil(gridUnit * 2.5 / 2);
    panel.hiding = "none";
    var menu = panel.addWidget("org.kde.plasma.kickoff");
    menu.currentConfigGroup = ["General"];
    menu.writeConfig("icon", "linuxbr");
    menu.writeConfig("alphaSort", true);
    menu.writeConfig("favorites", ["org.kde.dolphin.desktop", "chromium.desktop", "linuxbr-system.desktop", "linuxbr-store.desktop", "linuxbr-welcome.desktop"]);
    var tasks = panel.addWidget("org.kde.plasma.icontasks");
    tasks.currentConfigGroup = ["General"];
    // One button per program; a click on a group opens its window previews.
    tasks.writeConfig("groupingStrategy", 1);
    tasks.writeConfig("groupedTaskVisualization", 1);
    tasks.writeConfig("groupPopups", true);
    tasks.writeConfig("onlyGroupWhenFull", false);
    tasks.writeConfig("sortingStrategy", 1);
    tasks.writeConfig("separateLaunchers", false);
    tasks.writeConfig("showOnlyCurrentDesktop", true);
    tasks.writeConfig("showOnlyCurrentScreen", false);
    tasks.writeConfig("showToolTips", true);
    tasks.writeConfig("highlightWindows", true);
    tasks.writeConfig("minimizeActiveTaskOnClick", true);
    tasks.writeConfig("middleClickAction", 2);
    tasks.writeConfig("wheelEnabled", false);
    tasks.writeConfig("fill", true);
    tasks.writeConfig("maxStripes", 1);
    tasks.writeConfig("launchers", [
        "applications:org.kde.dolphin.desktop",
        "applications:chromium.desktop",
        "applications:linuxbr-system.desktop",
        "applications:linuxbr-store.desktop"
    ]);
    panel.addWidget("org.kde.plasma.systemtray");
    panel.addWidget("org.linuxbr.quicksettings");
    var clock = panel.addWidget("org.kde.plasma.digitalclock");
    clock.currentConfigGroup = ["Appearance"];
    clock.writeConfig("showDate", true);
    clock.writeConfig("dateFormat", "custom");
    clock.writeConfig("customDateFormat", "dd/MM/yyyy");
    clock.writeConfig("dateDisplayFormat", 2);
    clock.writeConfig("use24hFormat", 2);
    clock.writeConfig("showSeconds", 1);
    clock.writeConfig("showWeekNumbers", false);
    clock.writeConfig("firstDayOfWeek", 0);
    clock.writeConfig("wheelChangesTimezone", false);
    panel.addWidget("org.kde.plasma.notifications");
    panel.addWidget("org.kde.plasma.showdesktop");

    // Fresh desktops only: columns grow downwards from the top-left corner.
    var initialDesktops = desktops();
    for (var d = 0; d < initialDesktops.length; d++) {
        initialDesktops[d].currentConfigGroup = ["General"];
        initialDesktops[d].writeConfig("arrangement", 1);
        initialDesktops[d].writeConfig("alignment", 0);
        initialDesktops[d].writeConfig("iconSize", 2);
        initialDesktops[d].writeConfig("sortMode", 0);
        initialDesktops[d].writeConfig("sortDirsFirst", true);
        initialDesktops[d].writeConfig("renameInline", true);
        initialDesktops[d].writeConfig("toolTips", true);
        initialDesktops[d].writeConfig("selectionMarkers", false);
        initialDesktops[d].writeConfig("popups", false);
        initialDesktops[d].writeConfig("showHiddenFiles", false);
    }
}
