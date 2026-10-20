#!/usr/bin/python3
"""Describe the distribution default and the per-session Linux compatibility mode."""
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
class Settings(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Terminal do Linux BR'); self.resize(530,250)
        body=QVBoxLayout(self)
        text=QLabel('Novas janelas e abas do terminal sempre iniciam com letras de unidades: C:, D: e cd D:/Projetos.\n\nOs comandos continuam sendo do Bash. Caminhos como /home também funcionam.\n\nPara usar o modo Linux somente na janela atual, execute terminal-modo linux. Para voltar, execute terminal-modo letras.')
        text.setWordWrap(True); body.addWidget(text)
        close=QPushButton('Fechar'); close.clicked.connect(self.close); body.addWidget(close)
if __name__=='__main__':
    app=QApplication(sys.argv); window=Settings(); window.show(); sys.exit(app.exec())
