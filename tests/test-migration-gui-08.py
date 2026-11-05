#!/usr/bin/python3
"""Private file fixtures for real migration workers and enlarged-font navigation."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import (QApplication, QComboBox, QLineEdit,
                            QPushButton, QScrollArea)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import migration
import migration_backend
import maintenance

APP = QApplication.instance() or QApplication([])
if APP.setStyle('LinuxBRClean') is None:
    raise RuntimeError('LinuxBRClean deve estar disponível em QT_PLUGIN_PATH.')
QIcon.setThemeSearchPaths(['/usr/share/icons'])
QIcon.setThemeName('breeze')
FONT = QFont(APP.font())
SCALE = float(os.environ.get('LINUXBR_TEST_FONT_SCALE', '1.35'))
FONT.setPointSizeF(FONT.pointSizeF() * SCALE)
APP.setFont(FONT)
ARTIFACTS = Path(os.environ['LINUXBR_TEST_ARTIFACTS']) if os.environ.get('LINUXBR_TEST_ARTIFACTS') else None
if ARTIFACTS:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def pump_until(predicate, timeout=15):
    until = time.monotonic() + timeout
    while not predicate():
        APP.processEvents()
        if time.monotonic() >= until:
            raise AssertionError('A operação da interface não concluiu no prazo de teste.')
        QTest.qWait(5)
    APP.processEvents()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(window, name):
    APP.processEvents()
    if ARTIFACTS:
        window.grab().save(str(ARTIFACTS / (name + '-offscreen.png')))


def visible_controls(window):
    report = []
    controls = [widget for kind in (QPushButton, QComboBox, QLineEdit)
                for widget in window.findChildren(kind)]
    for widget in controls:
        if not widget.isVisible():
            continue
        point = widget.mapTo(window, QPoint(0, 0))
        text = widget.text() if isinstance(widget, (QPushButton, QLineEdit)) else widget.currentText()
        report.append({'class': type(widget).__name__, 'text': text,
                       'accessible_name': widget.accessibleName(), 'enabled': widget.isEnabled(),
                       'rect': [point.x(), point.y(), widget.width(), widget.height()],
                       'size_hint': [widget.sizeHint().width(), widget.sizeHint().height()]})
    return report


class MigrationGui(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='linuxbr-migration-gui-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'Documentos do Windows'
        self.destination = self.base / 'Destino'
        self.source.mkdir()
        self.destination.mkdir()
        self.file = self.source / 'ação e açúcar.txt'
        self.file.write_text('Conteúdo preservado, com acentos.\n', encoding='utf-8')
        self.window = migration.MigrationWindow()
        self.window.sources.addItem(str(self.source))
        self.window.destination.setText(str(self.destination))
        self.window.show()
        APP.processEvents()
        self.addCleanup(self.finish_window)

    def finish_window(self):
        if self.window.worker:
            self.window.cancel()
            pump_until(lambda: self.window.worker is None)
        self.window.close()
        APP.processEvents()

    def scan(self):
        self.window.scan.setFocus(Qt.FocusReason.TabFocusReason)
        activated = QSignalSpy(self.window.scan.clicked)
        QTest.keyClick(self.window.scan, Qt.Key.Key_Return)
        self.assertEqual(len(activated), 1)
        self.assertIsNotNone(self.window.worker)
        self.assertFalse(self.window.destination.isEnabled())
        pump_until(lambda: self.window.worker is None)
        self.assertIsNotNone(self.window.plan)
        self.assertTrue(self.window.start.isEnabled())

    def test_real_scan_copy_hash_report_and_source_preservation(self):
        (self.source / 'Pasta vazia').mkdir()
        before = digest(self.file)
        stamp = self.file.stat().st_mtime_ns
        self.scan()
        self.assertEqual(self.window.preview.item(0, 1).text(), '1')
        self.assertEqual(self.window.plan['files'][0]['sha256'], before)
        capture(self.window, 'migration-preview-font135')
        QTest.mouseClick(self.window.start, Qt.MouseButton.LeftButton)
        pump_until(lambda: self.window.worker is None)
        target = self.destination / self.source.name / self.file.name
        self.assertEqual(digest(target), before)
        self.assertEqual(digest(self.file), before)
        self.assertEqual(self.file.stat().st_mtime_ns, stamp)
        self.assertTrue((target.parent / 'Pasta vazia').is_dir())
        reports = list(self.destination.glob('.linuxbr-importacao-*.json'))
        if not reports:
            reports = list(self.destination.glob('*importacao*.json'))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['copied'][0]['sha256'], before)
        self.assertFalse(self.window.start.isEnabled())
        self.assertFalse(self.window.stop.isEnabled())
        self.assertIn('concluída e conferida', self.window.status.text())
        capture(self.window, 'migration-completed-font135')

    def test_real_cancel_mid_copy_cleans_temporary_and_close_is_guarded(self):
        self.file.write_bytes(b'arquivo privado\n' * (256 * 1024))
        before = digest(self.file)
        self.scan()
        reached_chunk = threading.Event()
        actual_transfer = migration_backend.transfer

        def synchronized_transfer(plan, policy, cancel, notify):
            def progress(info):
                notify(info)
                if not reached_chunk.is_set():
                    reached_chunk.set()
                    if not cancel.wait(5):
                        raise AssertionError('O cancelamento da interface não foi recebido.')
            return actual_transfer(plan, policy, cancel, progress)

        with patch.object(migration, 'transfer', side_effect=synchronized_transfer):
            QTest.mouseClick(self.window.start, Qt.MouseButton.LeftButton)
            pump_until(reached_chunk.is_set)
            QTest.mouseClick(self.window.stop, Qt.MouseButton.LeftButton)
            self.assertTrue(self.window.worker.cancel.is_set())
            self.assertFalse(self.window.close())
            self.assertTrue(self.window.isVisible())
            self.assertTrue(self.window.worker.cancel.is_set())
            self.assertFalse(self.window.stop.isEnabled())
            pump_until(lambda: self.window.worker is None)
        self.assertIn('cancelada', self.window.status.text())
        self.assertEqual(digest(self.file), before)
        self.assertFalse((self.destination / self.source.name / self.file.name).exists())
        self.assertEqual(list(self.destination.rglob('.linuxbr-import-*')), [])
        self.assertTrue(self.window.scan.isEnabled())
        capture(self.window, 'migration-cancelled-font135')

    def test_scan_failure_recovers_controls_and_destination_edit_invalidates_plan(self):
        self.window.destination.setText(str(self.base / 'inexistente'))
        QTest.mouseClick(self.window.scan, Qt.MouseButton.LeftButton)
        pump_until(lambda: self.window.worker is None)
        self.assertIsNone(self.window.plan)
        self.assertTrue(self.window.scan.isEnabled())
        self.assertFalse(self.window.stop.isEnabled())
        self.window.destination.setText(str(self.destination))
        self.scan()
        self.window.destination.setText(str(self.base))
        self.assertIsNone(self.window.plan)
        self.assertFalse(self.window.start.isEnabled())

    def test_enlarged_font_layout_and_keyboard_navigation(self):
        self.window.resize(1280, 720)
        self.window.activateWindow()
        APP.processEvents()
        self.assertLessEqual(self.window.width(), 1280)
        self.assertLessEqual(self.window.height(), 768)
        self.assertTrue(self.window.destination.accessibleName())
        self.assertTrue(self.window.policy.accessibleName())
        header = self.window.preview.horizontalHeader()
        for column in range(3):
            caption = self.window.preview.horizontalHeaderItem(column).text()
            self.assertGreaterEqual(header.sectionSize(column), header.fontMetrics().horizontalAdvance(caption) + 12)
        for widget in (self.window.add, self.window.remove, self.window.pick,
                       self.window.scan, self.window.start, self.window.stop):
            with self.subTest(button=widget.text()):
                self.assertGreaterEqual(widget.width(), widget.sizeHint().width())
                self.assertFalse(widget.icon().isNull())
                position = widget.mapTo(self.window, QPoint(0, 0))
                self.assertGreaterEqual(position.y(), 0)
                self.assertLessEqual(position.y() + widget.height(), self.window.height())
        expected = {self.window.sources, self.window.add, self.window.remove,
                    self.window.destination, self.window.pick, self.window.policy,
                    self.window.preview, self.window.scan}
        self.window.sources.setFocus(Qt.FocusReason.TabFocusReason)
        visited = set()
        for _ in range(24):
            focused = APP.focusWidget()
            for control in expected:
                if focused is control or (focused and control.isAncestorOf(focused)):
                    visited.add(control)
            QTest.keyClick(focused or self.window, Qt.Key.Key_Tab)
        self.assertEqual(visited, expected)
        self.window.policy.setFocus()
        QTest.keyClick(self.window.policy, Qt.Key.Key_Down)
        self.assertEqual(self.window.policy.currentData(), 'skip')
        capture(self.window, 'migration-layout-font135')
        if ARTIFACTS:
            (ARTIFACTS / 'migration-layout.json').write_text(json.dumps({
                'platform': APP.platformName(), 'style': APP.style().objectName(),
                'font_scale': SCALE, 'font_points': APP.font().pointSizeF(),
                'window': [self.window.width(), self.window.height()],
                'controls': visible_controls(self.window), 'keyboard_controls_reached': len(visited),
            }, ensure_ascii=False, indent=2))


class MaintenanceLayout(unittest.TestCase):
    def test_all_sections_fit_workarea_and_keyboard_switches_tabs(self):
        window = maintenance.MaintenanceWindow('protection')
        self.addCleanup(window.close)
        window.resize(1280, 720)
        window.show()
        window.activateWindow()
        APP.processEvents()
        self.assertLessEqual(window.height(), 768)
        tabs = window.page.tabs
        self.assertTrue(window.page.problem.accessibleName())
        self.assertTrue(window.page.category.accessibleName())
        reports = {}
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            APP.processEvents()
            scroll = tabs.currentWidget()
            self.assertIsInstance(scroll, QScrollArea)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            for button in scroll.findChildren(QPushButton):
                self.assertFalse(button.icon().isNull(), button.text())
                self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
                scroll.ensureWidgetVisible(button)
                APP.processEvents()
                point = button.mapTo(scroll.viewport(), QPoint(0, 0))
                self.assertGreaterEqual(point.y(), 0, button.text())
                self.assertLessEqual(point.y() + button.height(), scroll.viewport().height(), button.text())
            scroll.verticalScrollBar().setValue(0)
            reports[tabs.tabText(index)] = visible_controls(window)
            capture(window, 'maintenance-section-' + str(index) + '-font135')
        tabs.setCurrentIndex(0)
        bar = tabs.tabBar()
        bar.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(bar, Qt.Key.Key_Right)
        self.assertEqual(tabs.currentIndex(), 1)
        QTest.keyClick(bar, Qt.Key.Key_Right)
        self.assertEqual(tabs.currentIndex(), 2)
        QTest.keyClick(bar, Qt.Key.Key_Left)
        self.assertEqual(tabs.currentIndex(), 1)
        tabs.setCurrentIndex(2)
        action = next(button for button in tabs.currentWidget().findChildren(QPushButton)
                      if button.text() == 'Analisar o espaço por pastas')
        with patch.object(maintenance, 'launch') as launch:
            action.setFocus(Qt.FocusReason.TabFocusReason)
            QTest.keyClick(action, Qt.Key.Key_Return)
            launch.assert_called_once()
        if ARTIFACTS:
            (ARTIFACTS / 'maintenance-layout.json').write_text(json.dumps({
                'platform': APP.platformName(), 'font_scale': SCALE,
                'window': [window.width(), window.height()], 'sections': reports,
                'network_or_maintenance_actions_started': False,
            }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    unittest.main()
