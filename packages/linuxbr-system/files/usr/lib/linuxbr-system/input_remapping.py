"""Open the native per-device remapping editor and its installation route."""
import sys

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout


def main():
    from pathlib import Path
    from desktop_theme import initialize
    initialize()
    app = QApplication(sys.argv)
    dialog = QDialog()
    dialog.setWindowTitle('Remapeamento de teclas e botões')
    dialog.setWindowIcon(QIcon.fromTheme('input-keyboard'))
    dialog.resize(610, 255)
    layout = QVBoxLayout(dialog)
    installed = Path('/usr/bin/input-remapper-gtk').is_file()
    detail = QLabel('Escolha o teclado e crie um perfil. Combine teclas para atalhos ou macros. '
                    'Use Parar no editor para voltar aos controles originais e teste antes de ativar ao entrar na conta.'
                    if installed else 'Instale o recurso Remapeamento de teclas e botões nas Configurações para '
                    'ativar o editor de perfis por dispositivo.')
    detail.setWordWrap(True)
    layout.addWidget(detail)
    open_editor = QPushButton(QIcon.fromTheme('configure'), 'Abrir editor' if installed else 'Abrir Recursos opcionais')
    layout.addWidget(open_editor)
    close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close.rejected.connect(dialog.reject)
    layout.addWidget(close)

    def launch():
        program, arguments = ('/usr/bin/input-remapper-gtk', []) if installed else (
            '/usr/bin/linuxbr-system', ['--page', 'optional-features'])
        if QProcess.startDetached(program, arguments)[0]:
            dialog.accept()
        else:
            detail.setText('O editor ou a página de recursos não pôde ser aberta.')

    open_editor.clicked.connect(launch)
    dialog.exec()


if __name__ == '__main__':
    main()
