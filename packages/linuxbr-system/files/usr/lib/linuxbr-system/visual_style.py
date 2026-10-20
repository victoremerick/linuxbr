"""Shared solid controls for the Linux BR settings applications."""
BUTTONS = '''
QPushButton { background: palette(window); color: palette(window-text);
 border: 1px solid palette(mid); border-radius: 0; padding: 7px 14px; }
QPushButton:hover { border-color: palette(highlight); }
QPushButton:focus { border: 2px solid palette(highlight); }
QPushButton:pressed { background: palette(midlight); }
QPushButton:default, QPushButton[primary="true"] {
 background: palette(highlight); color: palette(highlighted-text); border: none; }
QPushButton:default:focus, QPushButton[primary="true"]:focus {
 border: 2px solid palette(window-text); }
QPushButton:disabled { color: palette(mid); background: palette(window); }
'''
