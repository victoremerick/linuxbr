// Simulated Plasma API: verifies layout behavior without modifying the host desktop.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../packages/linuxbr-desktop/files/usr/share/plasma/look-and-feel/org.linuxbr.desktop/contents/layouts/org.kde.plasma.desktop-layout.js'), 'utf8');
function run(existing) {
    const panels = existing ? [{custom: true}] : [];
    const context = {gridUnit: 18, panels: () => panels, Panel: function () {
        this.widgets = [];
        this.addWidget = name => {
            const widget = {name, config: {}, writeConfig(key, value) { this.config[key] = value; }};
            this.widgets.push(widget); return widget;
        };
        panels.push(this);
    }};
    vm.runInNewContext(script, context);
    vm.runInNewContext(script, context);
    assert.equal(panels.length, 1);
    if (existing) { assert.deepEqual(panels, [{custom: true}]); return; }
    assert.equal(panels[0].location, 'bottom');
    assert.equal(panels[0].floating, false);
    assert.equal(panels[0].opacity, 'translucent');
    const widgets = panels[0].widgets;
    assert.equal(widgets.length, 7);
    assert.equal(widgets[0].config.icon, 'linuxbr');
    assert.equal(widgets[1].config.launchers.length, 4);
    assert.equal(widgets[3].name, 'org.linuxbr.quicksettings');
    assert.equal(widgets[5].name, 'org.kde.plasma.notifications');
    assert.equal(widgets[6].name, 'org.kde.plasma.showdesktop');
}
run(false); run(true);
console.log('PASS: initial panel, repeat execution and existing user panel preserved (simulated API)');
