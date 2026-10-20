#!/usr/bin/python3
"""Run with QT_PLUGIN_PATH pointing to a directory containing styles/liblinuxbrclean.so."""
from PyQt6.QtWidgets import QApplication,QPushButton
from PyQt6.QtGui import QPalette,QColor
app=QApplication([]);assert app.setStyle('LinuxBRClean') is not None
palette=app.palette();palette.setColor(QPalette.ColorRole.Highlight,QColor('#6054a3'));palette.setColor(QPalette.ColorRole.Window,QColor('#f3f4f6'));app.setPalette(palette)
primary=QPushButton('Salvar');primary.setDefault(True);primary.resize(160,40)
secondary=QPushButton('Cancelar');secondary.resize(160,40)
# Render without keyboard focus, which deliberately adds a visible outline.
a=primary.grab().toImage();b=secondary.grab().toImage()
assert a.pixelColor(8,8).name()=='#6054a3'
assert b.pixelColor(8,8).name()=='#f3f4f6'
print('PASS: native primary solid accent; secondary uses window surface')
