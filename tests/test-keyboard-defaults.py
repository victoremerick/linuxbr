#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('keyboard_defaults',ROOT/'packages/linuxbr-desktop/files/usr/lib/linuxbr-desktop/keyboard-defaults.py')
keyboard=importlib.util.module_from_spec(spec);spec.loader.exec_module(keyboard)


class KeyboardDefaults(unittest.TestCase):
    def test_brazilian_defaults_and_existing_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'keyboard';target=root/'config/kxkbrc'
            source.write_text('XKBMODEL="abnt2"\nXKBLAYOUT="br"\nXKBVARIANT=""\n')
            self.assertTrue(keyboard.apply_defaults(source,target))
            self.assertIn('LayoutList=br\n',target.read_text());self.assertIn('Model=abnt2\n',target.read_text())
            target.write_text('[Layout]\nLayoutList=de\n')
            self.assertFalse(keyboard.apply_defaults(source,target))
            self.assertEqual(target.read_text(),'[Layout]\nLayoutList=de\n')

    def test_installer_choice_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'keyboard';target=root/'kxkbrc'
            source.write_text('XKBMODEL="pc105"\nXKBLAYOUT="us"\nXKBVARIANT="intl"\n')
            keyboard.apply_defaults(source,target)
            self.assertIn('LayoutList=us\n',target.read_text());self.assertIn('VariantList=intl\n',target.read_text())
            source.write_text('XKBLAYOUT="br;touch /tmp/unwanted"\n')
            with self.assertRaises(ValueError):keyboard.read_keyboard(source)


if __name__=='__main__':unittest.main()
