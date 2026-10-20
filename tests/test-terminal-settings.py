from pathlib import Path
import sys
from PyQt6.QtWidgets import QApplication,QLabel,QRadioButton
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
from terminal_settings import Settings
app=QApplication([]);window=Settings()
assert not window.findChildren(QRadioButton)
assert any('sempre iniciam' in label.text() for label in window.findChildren(QLabel))
print('PASS: configurações explicam letras obrigatórias ao abrir e compatibilidade por sessão')
