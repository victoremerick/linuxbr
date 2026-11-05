#!/usr/bin/python3
"""Navigation and native action guards using an isolated Qt widget."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QPushButton,QToolButton
import desktopflows08 as flows

APP=QApplication.instance() or QApplication([])


class DesktopNavigation08(unittest.TestCase):
    def setUp(self):
        self.launch=patch.object(flows.backend,'launch_native').start();self.addCleanup(patch.stopall)
        patch.object(flows.backend,'autostart_entries',return_value=[]).start()
        self.page=flows.DesktopFlowsPage('overview');self.addCleanup(self.page.close)
        self.page.resize(930,720);self.page.show();APP.processEvents()

    def test_categories_and_pages_do_not_launch_or_write_preferences(self):
        for key in self.page.pages:
            self.page.navigate(key);APP.processEvents()
            self.assertEqual(self.page.tabs.currentIndex(),self.page.pages[key])
            self.assertFalse(self.page.tabs.tabBar().isVisible())
        self.launch.assert_not_called()

    def test_card_enter_and_back_restore_real_leaf_and_focus(self):
        card=self.page.navigation[('overview','startup')];card.setFocus();APP.processEvents()
        QTest.keyClick(card,Qt.Key.Key_Return);APP.processEvents()
        self.assertEqual(self.page.current_page,'startup');self.assertIs(self.page.focusWidget(),self.page.startup)
        QTest.keyClick(self.page,Qt.Key.Key_Left,Qt.KeyboardModifier.AltModifier);APP.processEvents()
        self.assertEqual(self.page.current_page,'overview');self.launch.assert_not_called()

    def test_breadcrumb_ancestors_are_real_category_pages(self):
        self.page.navigate('defaults');APP.processEvents()
        self.assertEqual([button.text() for button in self.page.breadcrumb_buttons[1:]],['Configurações','Aplicativos'])
        self.page.breadcrumb_buttons[-1].click();APP.processEvents()
        self.assertEqual(self.page.current_page,'apps')
        self.assertIn(('apps','startup'),self.page.navigation)
        self.page.navigation[('apps','startup')].click();APP.processEvents()
        self.assertEqual(self.page.current_page,'startup')
        self.page.breadcrumb_buttons[1].click();self.assertEqual(self.page.current_page,'overview')
        self.launch.assert_not_called()

    def test_navigation_preserves_query_and_file_state(self):
        self.page.navigate('search');self.page.query.setText('inicialização')
        self.page.navigate('apps');self.page.navigate('search')
        self.assertEqual(self.page.query.text(),'inicialização');self.assertGreater(self.page.actions.topLevelItemCount(),0)
        self.assertFalse(self.page.apply_default.isEnabled());self.assertFalse(self.page.open_default.isEnabled())
        self.launch.assert_not_called()

    def test_native_action_requires_explicit_button_activation(self):
        self.page.navigate('transfers');APP.processEvents();self.launch.assert_not_called()
        button=self.page.transfer_open;self.assertEqual(button.accessibleName(),'Abrir Explorador de arquivos')
        button.setFocus();QTest.keyClick(button,Qt.Key.Key_Space);APP.processEvents()
        self.launch.assert_called_once_with('files','')

    def test_large_text_can_scroll_without_horizontal_overflow(self):
        self.page.setFont(QFont('Sans Serif',18));self.page.resize(930,720)
        for key in ('overview','apps','search','startup','defaults','transfers'):
            self.page.navigate(key);APP.processEvents()
            scroll=self.page.tabs.currentWidget()
            self.assertEqual(scroll.horizontalScrollBar().maximum(),0,key)
            target=self.page.focus_targets[key]
            self.assertTrue(target.isEnabled() or key=='startup')
        self.launch.assert_not_called()


if __name__=='__main__':unittest.main()
