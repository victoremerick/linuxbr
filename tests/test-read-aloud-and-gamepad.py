#!/usr/bin/env python3
"""Exercita a ferramenta de leitura e o perfil de diagnóstico de gamepads."""
import json
import ctypes
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0, str(MODULES))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QClipboard
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from gamepad_test import ControllerTest, SDLController, adjusted
from read_aloud import ReadAloud
import settings_catalog

APP = QApplication.instance() or QApplication([])

MOCK_SPEECH_MODULE = '''
import json
import os

class CallbackType:
    END = 'end'
    CANCEL = 'cancel'

class SSIPClient:
    def __init__(self, name):
        self.log('client', name)

    def log(self, *value):
        with open(os.environ['LINUXBR_SPEECH_EVENTS'], 'a') as stream:
            stream.write(json.dumps(value) + '\\n')

    def set_output_module(self, module):
        self.log('output', module)

    def set_language(self, lang):
        self.log('language', lang)

    def set_rate(self, rate):
        self.log('rate', rate)

    def speak(self, text, callback, event_types):
        self.log('say', text)
        self.callback = callback

    def pause(self):
        self.log('pause')

    def resume(self):
        self.log('resume')
        self.callback('end')

    def cancel(self):
        self.log('cancel')

    def close(self):
        self.log('close')
'''


class Device:
    def __init__(self):
        self.values = [3000, -1400, 0, 0, 15000, 0], ['A / Cruz']
        self.vibrated = False

    def devices(self):
        return [(0, 'Controle de laboratório')]

    def open(self, index):
        if index != 0:
            raise ValueError('Dispositivo indisponível')
        return 'control-id', True

    def read(self):
        return self.values

    def close(self):
        pass

    def shutdown(self):
        pass

    def rumble(self):
        self.vibrated = True
        return True


class DesktopToolTests(unittest.TestCase):
    def screenshot(self, page, name):
        output = os.environ.get('LINUXBR_DESKTOP_EVIDENCE')
        if output:
            QTest.qWait(125)
            self.assertTrue(page.grab().save(str(Path(output)/name)))

    def wait(self, expected):
        for _ in range(100):
            if expected():
                return
            QTest.qWait(20)
        self.fail('A operação gráfica não respondeu.')

    def test_portuguese_speech_pause_and_resume(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'speechd.py').write_text(MOCK_SPEECH_MODULE, encoding='utf-8')
            events = path/'events.json'
            with patch.dict(os.environ, {'PYTHONPATH': directory, 'LINUXBR_SPEECH_EVENTS': str(events)}):
                page = ReadAloud()
                page.resize(910, 620)
                page.show()
                APP.clipboard().setText('Olá, configuração local.')
                page.paste(QClipboard.Mode.Clipboard)
                page.rate.setValue(20)
                page.start.click()
                self.wait(lambda: page.ready)
                self.assertNotIn('Olá', ' '.join(page.speaker.arguments()))
                page.pause.click()
                self.assertTrue(page.paused)
                self.screenshot(page, '09-leitura-pausada.png')
                page.pause.click()
                self.wait(lambda: page.speaker is None)
                self.assertEqual(page.status.text(), 'Leitura concluída.')
                page.close()
            event_log = [json.loads(line) for line in events.read_text().splitlines()]
            self.assertEqual(event_log, [['client', 'LinuxBR'], ['output', 'espeak-ng'], ['language', 'pt-br'],
                ['rate', 20], ['say', 'Olá, configuração local.'], ['pause'], ['resume'], ['cancel'], ['close']])

    def test_axes_button_rumble_and_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Device()
            settings = QSettings(str(Path(directory)/'controllers.ini'), QSettings.Format.IniFormat)
            page = ControllerTest(backend=fixture, settings=settings)
            page.resize(910, 650)
            page.show()
            self.assertIn('bruto 3000', page.axes[0].format())
            self.assertEqual(page.buttons.text(), 'A / Cruz')
            page.center_button.click()
            page.zone.setValue(21)
            page.rumble_button.click()
            page.save_button.click()
            self.assertTrue(fixture.vibrated)
            self.screenshot(page, '10-controle-eixos.png')
            page.close()
            again = ControllerTest(backend=fixture, settings=settings)
            again.show()
            self.assertEqual(again.centers[:2], [3000, -1400])
            self.assertEqual(again.zone.value(), 21)
            fixture.values = None
            again.update_state()
            self.assertFalse(again.rumble_button.isEnabled())
            again.close()

    def test_deadzone_preserves_extremes_and_settings_routes(self):
        self.assertEqual(adjusted(1500, 1000, 8), 0)
        self.assertEqual(adjusted(32767, 1000, 8), 100)
        self.assertEqual(adjusted(-32768, -1000, 8), -100)
        ids = {item['id']: item for item in settings_catalog.PAGES}
        self.assertEqual(ids['controllers']['route'], ['tool', 'controllers'])
        self.assertEqual(ids['read-aloud']['route'], ['tool', 'read-aloud'])

    def test_sdl_library_reports_virtual_axis_button_and_removal(self):
        try:
            controller = SDLController()
        except OSError:
            self.skipTest('Biblioteca SDL2 indisponível neste laboratório.')
        controller.devices()
        lib = controller.library
        lib.SDL_JoystickAttachVirtual.argtypes = [ctypes.c_int] * 4
        lib.SDL_JoystickDetachVirtual.argtypes = [ctypes.c_int]
        lib.SDL_JoystickOpen.argtypes = [ctypes.c_int]
        lib.SDL_JoystickOpen.restype = ctypes.c_void_p
        lib.SDL_JoystickClose.argtypes = [ctypes.c_void_p]
        lib.SDL_JoystickSetVirtualAxis.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int16]
        lib.SDL_JoystickSetVirtualButton.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint8]
        index = lib.SDL_JoystickAttachVirtual(1, 6, 21, 1)
        self.assertGreaterEqual(index, 0)
        self.addCleanup(controller.shutdown)
        self.assertIn(index, dict(controller.devices()))
        controller.open(index)
        joy = lib.SDL_JoystickOpen(index)
        try:
            self.assertEqual(lib.SDL_JoystickSetVirtualAxis(joy, 0, 14600), 0)
            self.assertEqual(lib.SDL_JoystickSetVirtualButton(joy, 0, 1), 0)
            axes, buttons = controller.read()
            self.assertEqual(axes[0], 14600)
            self.assertEqual(buttons, ['A / Cruz'])
        finally:
            lib.SDL_JoystickClose(joy)
            lib.SDL_JoystickDetachVirtual(index)
        self.assertIsNone(controller.read())


if __name__ == '__main__':
    unittest.main()
