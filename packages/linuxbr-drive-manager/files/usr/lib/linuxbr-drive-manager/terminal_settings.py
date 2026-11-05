#!/usr/bin/python3
"""Describe the distribution default and the per-session Linux compatibility mode."""
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
class Settings(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Terminal do Linux BR'); self.resize(530,250)
        body=QVBoxLayout(self)
        text=QLabel("A pasta atual aparece antes de cada comando, com letras e barras no estilo Windows: D:\\Projetos>\n\nUse D: para abrir a unidade ou cd 'D:\\Minha pasta' para navegar. As aspas preservam espaços e barras invertidas. Também é possível usar cd D:/Projetos. As letras são as mesmas do Explorador de arquivos.\n\nOs comandos continuam sendo do Bash. Para usar o modo Linux somente na janela atual, execute terminal-modo linux. Para voltar, execute terminal-modo letras.")
        text.setWordWrap(True); body.addWidget(text)
        close=QPushButton('Fechar'); close.clicked.connect(self.close); body.addWidget(close)
if __name__=='__main__':
    app=QApplication(sys.argv); window=Settings(); window.show(); sys.exit(app.exec())
