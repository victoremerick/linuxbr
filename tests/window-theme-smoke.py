#!/usr/bin/python3
"""Run in a disposable desktop container, with linuxbr-desktop files installed."""
import configparser
import os
from pathlib import Path
import subprocess
import sys

if sys.argv[1:] and sys.argv[1] in ('gtk3','gtk4'):
    import gi
    version='3.0' if sys.argv[1]=='gtk3' else '4.0'
    gi.require_version('Gtk',version)
    from gi.repository import Gtk
    if version=='3.0': Gtk.init([])
    else: Gtk.init()
    provider=Gtk.CssProvider()
    errors=[]
    provider.connect('parsing-error', lambda provider,section,error:errors.append(str(error)))
    provider.load_from_path('/usr/share/themes/LinuxBRClean/gtk-'+version+'/gtk.css')
    assert not errors, errors
    print('PASS: GTK '+version+' theme parsed')
    raise SystemExit()

# Dry-run must preserve KConfig nested groups instead of escaping the brackets.
import shlex
commands = subprocess.check_output(['/usr/bin/linuxbr-apply-theme', '--dry-run'], text=True)
assert any(['--group', 'Colors:Header', '--group', 'Inactive'] == shlex.split(line)[3:7]
           for line in commands.splitlines()), commands

from PyQt6.QtWidgets import (QApplication,QStyleFactory,QMainWindow,QWidget,QHBoxLayout,
                            QVBoxLayout,QListWidget,QLabel,QLineEdit,QPushButton,QProgressBar,QToolBar)
from PyQt6.QtGui import QPalette,QColor,QAction
app=QApplication([])
style=QStyleFactory.create('Breeze');assert style is not None
app.setStyle(style)
config=configparser.ConfigParser();config.read('/etc/xdg/kdeglobals')
palette=app.palette()
for role,section,key in [('Window','Window','BackgroundNormal'),('WindowText','Window','ForegroundNormal'),('Base','View','BackgroundNormal'),('AlternateBase','View','BackgroundAlternate'),('Text','View','ForegroundNormal'),('Button','Button','BackgroundNormal'),('ButtonText','Button','ForegroundNormal'),('Highlight','Selection','BackgroundNormal'),('HighlightedText','Selection','ForegroundNormal')]:
    palette.setColor(getattr(QPalette.ColorRole,role),QColor(*map(int,config['Colors:'+section][key].split(','))))
app.setPalette(palette)
window=QMainWindow();window.setWindowTitle('Linux BR Clean — controles nativos Qt');window.resize(1000,600)
bar=QToolBar();window.addToolBar(bar)
for label in ('Novo','Abrir','Salvar'):bar.addAction(QAction(label,window))
root=QWidget();window.setCentralWidget(root);layout=QHBoxLayout(root)
nav=QListWidget();nav.addItems(['Sistema','Dispositivos','Armazenamento','Rede']);nav.setFixedWidth(205);nav.setCurrentRow(0);layout.addWidget(nav)
content=QVBoxLayout();content.setContentsMargins(24,24,24,24);layout.addLayout(content)
heading=QLabel('Preferências do sistema');heading.setStyleSheet('font-size:24px;font-weight:600');content.addWidget(heading)
content.addWidget(QLabel('Superfícies sólidas e controles nativos'))
field=QLineEdit();field.setPlaceholderText('Pesquisar configurações');content.addWidget(field)
progress=QProgressBar();progress.setValue(62);content.addWidget(progress)
content.addStretch();buttons=QHBoxLayout();buttons.addStretch();buttons.addWidget(QPushButton('Cancelar'));buttons.addWidget(QPushButton('Aplicar'));content.addLayout(buttons)
window.show();app.processEvents();assert window.grab().save('/tmp/linuxbr-window-theme.png');window.close()
print('PASS: Qt Breeze native controls and palette')
