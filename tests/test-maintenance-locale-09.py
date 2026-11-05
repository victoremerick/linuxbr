"""Check the standard confirmation labels used by maintenance windows."""
from pathlib import Path
import os
import sys
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import QLocale
from PyQt6.QtWidgets import QApplication, QDialogButtonBox

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from desktop_theme import initialize


class MaintenanceLocale(unittest.TestCase):
    def test_brazilian_confirmation_buttons(self):
        app=QApplication.instance() or QApplication([])
        QLocale.setDefault(QLocale('pt_BR'))
        initialize()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Yes|QDialogButtonBox.StandardButton.Cancel)
        self.assertEqual(buttons.button(QDialogButtonBox.StandardButton.Yes).text().replace('&',''),'Sim')
        self.assertEqual(buttons.button(QDialogButtonBox.StandardButton.Cancel).text().replace('&',''),'Cancelar')


if __name__=='__main__':unittest.main()
