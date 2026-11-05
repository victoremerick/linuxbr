#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint
import session_actions
APP=QApplication.instance() or QApplication([])


class SessionActions(unittest.TestCase):
    def test_open_and_cancel_do_not_call_session_services(self):
        with patch.object(session_actions,'session_call') as call:
            window=session_actions.SessionActions();window.close();call.assert_not_called()

    def test_logout_opens_native_confirmation(self):
        window=session_actions.SessionActions()
        with patch.object(session_actions,'session_call') as call:
            window.activate('logout')
            call.assert_called_once_with('org.kde.LogoutPrompt','/LogoutPrompt','org.kde.LogoutPrompt','promptLogout')

    def test_lock_uses_screen_lock_service(self):
        window=session_actions.SessionActions()
        with patch.object(session_actions,'session_call') as call:
            window.activate('lock')
            call.assert_called_once_with('org.freedesktop.ScreenSaver','/ScreenSaver','org.freedesktop.ScreenSaver','Lock')

    def test_task_manager_is_an_independent_command(self):
        window=session_actions.SessionActions()
        with patch.object(session_actions.shutil,'which',return_value='/usr/bin/linuxbr-task-manager'),patch.object(session_actions.QProcess,'startDetached',return_value=(True,123)) as start:
            window.activate('tasks');start.assert_called_once_with('linuxbr-task-manager',[])

    def test_failed_action_keeps_choices_available(self):
        window=session_actions.SessionActions()
        with patch.object(session_actions,'session_call',side_effect=OSError('indisponível')):
            window.activate('lock')
        self.assertTrue(all(button.isEnabled() for button in window.buttons))
        self.assertIn('Não foi possível',window.error.text());window.close()

    def test_cancel_background_keeps_blue_contrast(self):
        window=session_actions.SessionActions();window.resize(900,650);window.show();APP.processEvents()
        cancel=window.findChild(session_actions.QPushButton,'cancel')
        point=cancel.mapTo(window,QPoint(20,5))
        color=window.grab().toImage().pixelColor(point)
        self.assertGreater(color.blue(),color.red())
        window.close()


if __name__=='__main__':unittest.main()
