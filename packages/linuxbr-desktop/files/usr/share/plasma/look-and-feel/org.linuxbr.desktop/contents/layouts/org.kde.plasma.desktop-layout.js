// Used by Plasma when creating the initial layout, not on every login.
// Do not replace panels when invoked against an already configured desktop.
if (panels().length === 0) {
    var panel = new Panel;
    panel.location = "bottom";
    panel.floating = false;
    panel.opacity = "translucent";
    panel.height = 2 * Math.ceil(gridUnit * 2.5 / 2);
    var menu = panel.addWidget("org.kde.plasma.kickoff");
    menu.currentConfigGroup = ["General"];
    menu.writeConfig("icon", "linuxbr");
    menu.writeConfig("alphaSort", true);
    menu.writeConfig("favorites", ["org.kde.dolphin.desktop", "firefox-esr.desktop", "linuxbr-system.desktop", "org.kde.discover.desktop"]);
    var tasks = panel.addWidget("org.kde.plasma.icontasks");
    tasks.currentConfigGroup = ["General"];
    tasks.writeConfig("launchers", [
        "applications:org.kde.dolphin.desktop",
        "applications:firefox-esr.desktop",
        "applications:linuxbr-system.desktop",
        "applications:org.kde.discover.desktop"
    ]);
    panel.addWidget("org.kde.plasma.systemtray");
    panel.addWidget("org.linuxbr.quicksettings");
    panel.addWidget("org.kde.plasma.digitalclock");
    panel.addWidget("org.kde.plasma.notifications");
    panel.addWidget("org.kde.plasma.showdesktop");
}
