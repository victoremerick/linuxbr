"""Entrada acessível para os campos do assistente inicial."""
from PyQt6.QtWidgets import QApplication, QGridLayout, QLineEdit, QPushButton, QWidget


class ScreenKeyboard(QWidget):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.editor = None
        self.keyboard_layout = 'br'
        self.uppercase = False
        self.keys = QGridLayout(self)
        self.keys.setSpacing(4)
        self.keys.setContentsMargins(0, 0, 0, 0)
        QApplication.instance().focusChanged.connect(self.track_focus)
        self.build()

    def track_focus(self, _, current):
        if isinstance(current, QLineEdit) and self.pages.isAncestorOf(current):
            self.editor = current

    def set_layout(self, value):
        if self.keyboard_layout != value:
            self.keyboard_layout = value
            self.build()

    def build(self):
        while self.keys.count():
            self.keys.takeAt(0).widget().deleteLater()

        rows = ('1234567890', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm')
        accents = 'çáéíóúãõêâô' if self.keyboard_layout in ('br', 'pt') else 'ñáéíóúü' if self.keyboard_layout == 'es' else 'áéíóú'
        symbols = '!@#$%&*()_+=-.,:;/?{}[]\\|~\x60^\'"<>'
        blocks = (*rows, accents, symbols[:14], symbols[14:28], symbols[28:])
        for index, values in enumerate(blocks):
            self.row(index, values.upper() if self.uppercase else values)
        upper = QPushButton('Maiúsculas' if not self.uppercase else 'Minúsculas')
        upper.clicked.connect(self.toggle_case)
        self.keys.addWidget(upper, len(blocks), 0, 1, 4)
        space = QPushButton('Espaço')
        space.clicked.connect(lambda: self.type_key(' '))
        self.keys.addWidget(space, len(blocks), 4, 1, 4)
        back = QPushButton('Apagar')
        back.clicked.connect(lambda: self.type_key(None))
        self.keys.addWidget(back, len(blocks), 8, 1, 4)

    def row(self, number, keys):
        for index, letter in enumerate(keys):
            key = QPushButton(letter.replace('&', '&&'))
            key.setAccessibleName(letter)
            key.setMinimumHeight(30)
            key.clicked.connect(lambda checked, value=letter: self.type_key(value))
            self.keys.addWidget(key, number, index)

    def toggle_case(self):
        self.uppercase = not self.uppercase
        self.build()

    def type_key(self, character):
        editor = self.editor
        if editor is None or not editor.isVisible() or not editor.isEnabled():
            editor = next((control for control in self.pages.currentWidget().findChildren(QLineEdit)
                           if control.isVisible() and control.isEnabled()), None)
        if editor is None:
            return
        if character is None:
            editor.backspace()
        else:
            editor.insert(character)
        editor.setFocus()
