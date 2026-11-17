from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QNativeGestureEvent, QPointingDevice, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0, str(FILES))

import action
import app_access
import app_audio
import audio_roles
import concentration
import display_backend as display
import keyboard_focus
import power_devices
import screen_reader_test
import touchpad_profiles
import window_groups
import workspace_tasks


def monitor(name, output_id, mode, priority, hardware='Example Display'):
    return dict(id=output_id, name=name, connected=True, enabled=True, priority=priority,
                model=hardware, scale=1.25, rotation=2, pos=dict(x=640, y=30),
                currentModeId=mode, modes=[dict(id=mode, size=dict(width=1920, height=1080), refreshRate=60)])


class WorkspacePlasma(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        isolated = patch.dict(os.environ, {'XDG_CONFIG_HOME': self.temporary.name, 'XDG_DATA_HOME': self.temporary.name})
        isolated.start()
        self.addCleanup(isolated.stop)

    def test_named_monitor_profile_uses_live_ids_and_restores_priority(self):
        old = [monitor('DP-1', 1, 'a', 2), monitor('eDP-1', 2, 'b', 1)]
        saved = display.snapshot(old)
        display.save_profiles({'Escritório': saved})
        self.assertEqual(display.load_profiles()['Escritório'], saved)
        live = [monitor('eDP-1', 3, 'c', 2), monitor('DP-1', 4, 'd', 1)]
        command = display.profile_arguments(saved, live)
        self.assertEqual(command[-2:], ['output.3.priority.1', 'output.4.priority.2'])
        for command_part in ('output.3.mode.c', 'output.4.mode.d', 'output.3.rotation.left',
                             'output.3.scale.1.25', 'output.4.position.640,30'):
            self.assertIn(command_part, command)
        with self.assertRaisesRegex(ValueError, 'mesmos monitores'):
            display.profile_arguments(saved, live[:1])
        with self.assertRaisesRegex(ValueError, 'identidade'):
            display.profile_arguments(saved, [live[0], {**live[1], 'model': 'Monitor diferente'}])
        with patch.object(display.subprocess, 'run') as run:
            display.apply_profile(saved, live)
            self.assertEqual(run.call_args.args[0], ['kscreen-doctor', *command])

    def test_concentration_schedule_crosses_midnight_and_is_persisted(self):
        friday = dict(enabled=True, days=[4], start='23:00', end='07:00')
        concentration.save(friday)
        self.assertEqual(concentration.load(), friday)
        self.assertTrue(concentration.active(friday, datetime(2026, 11, 20, 23, 50)))
        self.assertTrue(concentration.active(friday, datetime(2026, 11, 21, 6, 59)))
        self.assertFalse(concentration.active(friday, datetime(2026, 11, 21, 7, 0)))
        self.assertFalse(concentration.active(friday, datetime(2026, 11, 22, 6, 59)))
        with self.assertRaises(ValueError):
            concentration.save({**friday, 'end': '23:00'})

    def test_inhibition_tracks_plasma_owner_and_releases_its_own_cookie(self):
        service, bus = Mock(), Mock()
        service.Inhibit.return_value = 30
        bus.get_name_owner.return_value = ':1.8'
        with patch.object(concentration.dbus, 'Interface', return_value=service):
            controller = concentration.Inhibition(bus)
            controller.update(True)
            controller.update(True)
            service.Inhibit.assert_called_once()
            self.assertEqual(service.Inhibit.call_args.args[0], 'linuxbr-concentration')
            controller.update(False)
            self.assertEqual(service.UnInhibit.call_args.args[0], 30)
            bus.get_name_owner.return_value = ':1.9'
            controller.update(True)
            self.assertEqual(service.Inhibit.call_count, 2)

    def test_audio_uses_selected_task_process_only_and_validates_argv(self):
        for pid, parent in ((100, 1), (101, 100), (102, 1)):
            location = self.root / str(pid)
            location.mkdir()
            (location / 'status').write_text(f'Name: teste\nPPid:\t{parent}\n')
        self.assertTrue(app_audio.belongs(101, 100, self.root))
        self.assertFalse(app_audio.belongs(102, 100, self.root))
        self.assertEqual(action.action_from_url('linuxbr-action:///app-audio/100'), 'app-audio/100')
        for bad in ('linuxbr-action:///app-audio/-1', 'linuxbr-action:///app-audio/123/456',
                    'linuxbr-action:///app-audio/123?other=456'):
            with self.assertRaises(ValueError):
                action.action_from_url(bad)
        row = dict(index=7, mute=False, volume={}, properties={'application.process.id': '101'})
        with patch.object(app_audio, 'owned_process', return_value=True), \
                patch.object(app_audio, 'belongs', side_effect=lambda pid, target: pid == 101 and target == 100), \
                patch.object(app_audio, 'pactl', return_value=json.dumps([row])) as pactl:
            app_audio.apply(100, 'source-outputs', 7, 'mute', True)
            self.assertEqual(pactl.call_args.args, ('set-source-output-mute', '7', '1'))
            with self.assertRaises(ValueError):
                app_audio.apply(102, 'source-outputs', 7, 'mute', True)

    def test_role_audio_follows_device_reconnection_but_respects_manual_route(self):
        routes = audio_roles.load()
        routes['calls'] = ['blue.headset', 'usb.speaker']
        routes['media'] = ['analog.o', 'usb.speaker']
        speaker = dict(index=10, name='usb.speaker')
        headset = dict(index=11, name='blue.headset')
        analog = dict(index=12, name='analog.o')
        call = dict(index=4, sink=9, properties={'media.role': 'Communication', 'object.serial': '1'})
        music = dict(index=5, sink=9, properties={'media.role': 'music', 'object.serial': '2'})
        notification = dict(index=6, sink=9, properties={'media.role': 'event'})
        router = audio_roles.Router()
        with patch.object(audio_roles, 'pactl') as pulse:
            router.update(routes, [speaker, analog], [call, music, notification])
            self.assertEqual([entry.args for entry in pulse.call_args_list],
                             [('move-sink-input', '4', 'usb.speaker'), ('move-sink-input', '5', 'analog.o')])
            pulse.reset_mock()
            router.update(routes, [speaker, analog], [call, music, notification])
            pulse.assert_not_called()
            router.update(routes, [speaker, analog, headset], [call, music, notification])
            pulse.assert_called_once_with('move-sink-input', '4', 'blue.headset')
            pulse.reset_mock()
            headset['active_port'] = {'availability': 'not available'}
            router.update(routes, [speaker, analog, headset], [call, music, notification])
            pulse.assert_called_once_with('move-sink-input', '4', 'usb.speaker')
        with patch.object(audio_roles.subprocess, 'run') as systemctl:
            audio_roles.configure(routes)
            self.assertEqual(audio_roles.load(), routes)
            self.assertEqual(systemctl.call_args.args[0][-3:], ['enable', '--now', 'linuxbr-audio-roles.service'])
        with self.assertRaises(ValueError):
            audio_roles.validate({**routes, 'media': ['--help', '']})

    def test_touchpad_writes_only_selected_supported_device_properties(self):
        properties = dict(touchpad=True, name='Touchpad', vendor=9, product=10, tapFingerCount=3,
                          tapToClick=False, supportsScrollTwoFinger=True, scrollTwoFinger=False,
                          supportsScrollEdge=True, scrollEdge=True)
        backend = touchpad_profiles.Touchpads(Mock())
        backend.read = Mock(return_value=properties)
        interface = Mock()
        backend.interface = Mock(return_value=interface)
        interface.Get.return_value = True
        backend.apply('event3', ('Touchpad', 9, 10), {'tapToClick': True}, 'scrollTwoFinger')
        self.assertEqual([call.args for call in interface.Set.call_args_list],
                         [(touchpad_profiles.DEVICE, 'tapToClick', True),
                          (touchpad_profiles.DEVICE, 'scrollTwoFinger', True)])
        with self.assertRaisesRegex(ValueError, 'substituído'):
            backend.apply('event3', ('Outro', 9, 10), {'tapToClick': True}, 'scrollTwoFinger')
        with self.assertRaisesRegex(ValueError, 'não oferece'):
            backend.apply('event3', ('Touchpad', 9, 10), {'tapToClick': True}, 'scrollOnButtonDown')

    def test_touchpad_reverts_rollover_and_other_changes_on_failure(self):
        properties = dict(touchpad=True, name='Touchpad', vendor=9, product=10, tapFingerCount=2,
                          tapToClick=False, supportsScrollTwoFinger=True, scrollTwoFinger=False,
                          supportsScrollEdge=True, scrollEdge=True)
        backend = touchpad_profiles.Touchpads(Mock())
        backend.read = Mock(return_value=properties)
        interface = Mock()
        backend.interface = Mock(return_value=interface)
        interface.Get.side_effect = [True, False, True, False]
        with self.assertRaisesRegex(ValueError, 'anteriores foram mantidas'):
            backend.apply('event3', ('Touchpad', 9, 10), {'tapToClick': True}, 'scrollTwoFinger')
        self.assertEqual([call.args[1:] for call in interface.Set.call_args_list],
                         [('tapToClick', True), ('scrollTwoFinger', True), ('scrollEdge', True), ('tapToClick', False)])

    def test_touchpad_practice_detects_click_drag_scroll_and_pinch(self):
        app = QApplication.instance() or QApplication([])
        status = QLabel()
        practice = touchpad_profiles.Practice(status)
        practice.resize(480, 120)
        practice.show()
        app.processEvents()
        QTest.mouseClick(practice, Qt.MouseButton.RightButton, pos=QPoint(240, 60))
        self.assertEqual(status.text(), 'Clique secundário detectado.')
        QTest.mousePress(practice, Qt.MouseButton.LeftButton, pos=QPoint(240, 60))
        QTest.mouseMove(practice, QPoint(280, 60))
        QTest.mouseRelease(practice, Qt.MouseButton.LeftButton, pos=QPoint(280, 60))
        self.assertEqual(status.text(), 'Arraste detectado.')
        no_button, no_modifier = Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
        position = QPointF(280, 60)
        app.sendEvent(practice, QWheelEvent(position, position, QPoint(0, -10), QPoint(), no_button,
                                           no_modifier, Qt.ScrollPhase.ScrollUpdate, False))
        self.assertEqual(status.text(), 'Rolagem para baixo detectada.')
        app.sendEvent(practice, QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture,
                      QPointingDevice.primaryPointingDevice(), 2, position, position, position, 0.3, QPointF()))
        self.assertEqual(status.text(), 'Pinça detectada. Ampliação de 130%.')

    def test_accessible_shortcut_keeps_other_apps_independent(self):
        preferences = dict(scale='1.5', contrast=True, motion=True)
        self.assertTrue(app_access.save('dolphin', preferences))
        self.assertEqual(app_access.load('dolphin'), preferences)
        self.assertFalse(app_access.load('kate')['contrast'])
        self.assertIn('Exec=/usr/bin/linuxbr-app-access --launch dolphin\n', app_access.shortcut('dolphin').read_text())
        with patch.object(app_access, 'app_path', return_value=self.root / 'dolphin'), \
                patch.object(app_access.subprocess, 'Popen') as launch:
            (self.root / 'dolphin').touch()
            app_access.launch('dolphin')
            self.assertEqual(launch.call_args.args[0][0:2], [str(self.root / 'dolphin'), '-stylesheet'])
            self.assertEqual(launch.call_args.kwargs['env']['QT_SCALE_FACTOR'], '1.5')
            stylesheet = Path(launch.call_args.args[0][2]).read_text()
            self.assertIn('widget-animation-duration: 0', stylesheet)
            self.assertIn('#111111', stylesheet)
        self.assertFalse(app_access.save('dolphin', dict(scale='', contrast=False, motion=False)))
        self.assertFalse(app_access.shortcut('dolphin').exists())
        with self.assertRaises(ValueError):
            app_access.launch('../../x')

    def test_keyboard_focus_control_and_reader_results(self):
        self.assertFalse(keyboard_focus.preference().exists())
        keyboard_focus.set_preference(True)
        self.assertTrue(keyboard_focus.preference().is_file())
        keyboard_focus.set_preference(False)
        self.assertFalse(keyboard_focus.preference().exists())
        self.assertEqual(screen_reader_test.result_text('', ''), 'Revisar nome e descrição')
        self.assertEqual(screen_reader_test.result_text('Nome', ''), 'Nome disponível')

    def test_dock_identity_and_power_profiles_apply_only_owned_cookies(self):
        for port, serial in (('usb1', 'root'), ('1-3', 'dock-N'), ('1-4', '')):
            path = self.root / port
            path.mkdir()
            for key, content in dict(idVendor='34a1', idProduct='4012', serial=serial, product='Dock').items():
                (path / key).write_text(content)
        devices = power_devices.usb_devices(self.root)
        self.assertEqual(set(devices), {'34a1:4012:serial=dock-N', '34a1:4012:port=1-4'})
        configuration = power_devices.load()
        configuration['dock'] = '34a1:4012:serial=dock-N'
        configuration['rules']['dock'] = ['performance', True, False]
        self.assertEqual(power_devices.verify(configuration), configuration)
        self.assertEqual(power_devices.context(False, configuration['dock'], devices), 'dock')
        self.assertEqual(power_devices.context(True, configuration['dock'], devices), 'battery')
        self.assertEqual(power_devices.context(False, configuration['dock'], {}), 'charger')
        session, system = Mock(), Mock()
        system.get_name_owner.return_value = ':1.3'
        session.get_name_owner.return_value = ':1.9'
        profile, policy = Mock(), Mock()
        profile.HoldProfile.return_value = 61
        policy.AddInhibition.return_value = 82
        controller = power_devices.PowerRules(system, session)
        with patch.object(power_devices.dbus, 'Interface', side_effect=lambda _, name: profile if name == power_devices.PPD else policy):
            controller.apply('dock', configuration['rules']['dock'])
            controller.apply('dock', configuration['rules']['dock'])
            profile.HoldProfile.assert_called_once_with('performance', power_devices.CONTEXTS['dock'],
                                                        power_devices.APP_ID, timeout=3)
            self.assertEqual(policy.AddInhibition.call_args.args[0], 4)
            controller.apply('battery', ['', False, True])
            profile.ReleaseProfile.assert_called_once_with(61, timeout=3)
            policy.ReleaseInhibition.assert_called_once_with(82, timeout=3)
            self.assertEqual(policy.AddInhibition.call_args.args[0], 1)

    def test_native_activity_configuration_and_notification_routing(self):
        identity = 'f34922a8-7098-4511-9a31-fdb749407d41'
        picture = self.root / 'Área de Trabalho.png'
        picture.touch()
        settings = workspace_tasks.validate('Estudo', str(picture), [('app', 'org.kde.kate.desktop')], True)
        workspace_tasks.save(identity, settings)
        self.assertEqual(workspace_tasks.notification_activity('org.kde.kate', workspace_tasks.settings()), identity)
        self.assertIsNone(workspace_tasks.notification_activity('org.kde.kate;other', workspace_tasks.settings()))
        script = workspace_tasks.wallpaper_script(identity, str(picture))
        self.assertIn('desktopsForActivity', script)
        self.assertIn(picture.as_uri(), script)
        api = Mock()
        api.CurrentActivity.return_value = 'other'
        workspace_tasks.activate(identity, api)
        api.SetCurrentActivity.assert_called_once_with(identity, timeout=8)

    def test_window_group_accepts_verified_desktop_ids_and_geometry(self):
        accepted = dict(application='org.kde.kate.desktop', monitor='eDP-1', x=20,
                        y=10, width=900, height=700, maximize=0, minimized=False)
        candidates = [accepted, {**accepted, 'application': 'linuxbr-window-groups.desktop'},
                      {**accepted, 'width': -1}, {**accepted, 'application': 'não-instalado.desktop'}]
        self.assertEqual(window_groups.plan(candidates, {'org.kde.kate.desktop', 'linuxbr-window-groups.desktop'}),
                         [accepted])


if __name__ == '__main__':
    unittest.main()
