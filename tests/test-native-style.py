#!/usr/bin/python3
"""Exercise the installed native style; QT_PLUGIN_PATH must contain its plugin."""
import json
import os
from pathlib import Path
import unittest

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QImage, QPainter, QPalette, QPixmap
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import (QApplication, QPushButton, QStyle, QStyleOptionButton,
                            QVBoxLayout, QWidget)


APP = QApplication.instance() or QApplication([])
if APP.setStyle('LinuxBRClean') is None:
    raise RuntimeError('O estilo nativo LinuxBRClean não está disponível em QT_PLUGIN_PATH.')
PALETTE = APP.palette()
for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
    for role, color in ((QPalette.ColorRole.Highlight, '#6054a3'),
                        (QPalette.ColorRole.Window, '#f3f4f6'),
                        (QPalette.ColorRole.WindowText, '#172033'),
                        (QPalette.ColorRole.ButtonText, '#172033'),
                        (QPalette.ColorRole.HighlightedText, '#ffffff'),
                        (QPalette.ColorRole.Mid, '#9399a2')):
        PALETTE.setColor(group, role, QColor(color))
for role, color in ((QPalette.ColorRole.Highlight, '#a6a5af'),
                    (QPalette.ColorRole.Window, '#e4e5e8'),
                    (QPalette.ColorRole.ButtonText, '#737986'),
                    (QPalette.ColorRole.HighlightedText, '#e9e9ee')):
    PALETTE.setColor(QPalette.ColorGroup.Disabled, role, QColor(color))
APP.setPalette(PALETTE)
ICON_IMAGE = QPixmap(16, 16)
ICON_IMAGE.fill(QColor('#cf2475'))
ICON = QIcon(ICON_IMAGE)
STATES = {
    'enabled': QStyle.StateFlag.State_Enabled,
    'disabled': QStyle.StateFlag.State_None,
    'hover': QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_MouseOver,
    'pressed': QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Sunken,
    'focus': QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_HasFocus,
}


def render(primary=False, state='enabled', text='Salvar', icon=True):
    option = QStyleOptionButton()
    option.rect = QRect(0, 0, 180, 44)
    option.palette = PALETTE
    option.state = STATES[state]
    option.fontMetrics = QFontMetrics(APP.font())
    if primary:
        option.features = QStyleOptionButton.ButtonFeature.DefaultButton
    option.text = text
    if icon:
        option.icon = ICON
        option.iconSize = QSize(16, 16)
    result = QImage(option.rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    APP.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter)
    painter.end()
    return result


def changed(a, b, rect):
    return sum(a.pixel(x, y) != b.pixel(x, y)
               for x in range(rect.left(), rect.right() + 1)
               for y in range(rect.top(), rect.bottom() + 1))


class NativeButtons(unittest.TestCase):
    def test_primary_and_secondary_surfaces(self):
        self.assertEqual(render(True).pixelColor(8, 8).name(), '#6054a3')
        self.assertEqual(render(False).pixelColor(8, 8).name(), '#f3f4f6')

    def test_disabled_uses_disabled_palette(self):
        for primary, expected in ((True, '#a6a5af'), (False, '#e4e5e8')):
            with self.subTest(primary=primary):
                self.assertEqual(render(primary, 'disabled').pixelColor(8, 8).name(), expected)
                self.assertGreater(changed(render(primary), render(primary, 'disabled'), QRect(4, 4, 172, 36)), 100)

    def test_pressed_surface_and_visible_focus(self):
        for primary in (False, True):
            with self.subTest(primary=primary):
                normal = render(primary)
                self.assertNotEqual(normal.pixelColor(8, 8), render(primary, 'pressed').pixelColor(8, 8))
                self.assertGreater(changed(normal, render(primary, 'focus'), QRect(0, 0, 180, 4)), 50)

    def test_hover_changes_secondary_border_without_replacing_surface(self):
        normal, hover = render(False), render(False, 'hover')
        self.assertEqual(normal.pixelColor(8, 8), hover.pixelColor(8, 8))
        self.assertGreater(changed(normal, hover, QRect(0, 0, 180, 4)), 50)

    def test_text_and_icon_survive_every_state(self):
        label = QRect(12, 8, 156, 28)
        for primary in (False, True):
            for state in STATES:
                with self.subTest(primary=primary, state=state):
                    complete = render(primary, state)
                    self.assertGreater(changed(complete, render(primary, state, text=''), label), 20)
                    self.assertGreater(changed(complete, render(primary, state, icon=False), label), 40)
                    self.assertEqual(complete.pixelColor(8, 8).alpha(), 255)

    def test_real_keyboard_focus_and_disabled_activation(self):
        window = QWidget()
        layout = QVBoxLayout(window)
        first, second = QPushButton('Salvar'), QPushButton('Cancelar')
        first.setDefault(True)
        first.setIcon(ICON)
        layout.addWidget(first)
        layout.addWidget(second)
        window.show()
        window.activateWindow()
        APP.processEvents()
        first.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(first, Qt.Key.Key_Tab)
        self.assertTrue(second.hasFocus())
        spy = QSignalSpy(second.clicked)
        second.setEnabled(False)
        QTest.mouseClick(second, Qt.MouseButton.LeftButton)
        self.assertEqual(len(spy), 0)
        window.close()


def save_examples():
    location = os.environ.get('LINUXBR_TEST_ARTIFACTS')
    if not location:
        return
    folder = Path(location)
    folder.mkdir(parents=True, exist_ok=True)
    result = QImage(940, 152, QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(QColor('#ffffff'))
    painter = QPainter(result)
    painter.setPen(QColor('#172033'))
    for column, state in enumerate(STATES):
        painter.drawText(QRect(column * 188, 0, 180, 24), Qt.AlignmentFlag.AlignCenter, state)
        for row, primary in enumerate((True, False)):
            painter.drawImage(column * 188, 28 + row * 56, render(primary, state))
    painter.end()
    result.save(str(folder / 'native-button-states-offscreen.png'))
    (folder / 'native-style-context.json').write_text(json.dumps({
        'style': APP.style().objectName(), 'platform': APP.platformName(),
        'plugin_path': os.environ.get('QT_PLUGIN_PATH'), 'states': list(STATES),
        'checks': 'surface, disabled palette, pressed fill, hover border, focus cue, text, icon, keyboard',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    save_examples()
    unittest.main()
