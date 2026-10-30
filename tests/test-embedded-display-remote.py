#!/usr/bin/python3
"""Display, remote-access and dark-palette regression without changing the host."""
import configparser
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'


def module(name):
    spec=importlib.util.spec_from_file_location(name,LIB/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


display=module('display_backend')
remote=module('remote_backend')
power=module('power_backend')


class EmbeddedSettings(unittest.TestCase):
    def test_display_arguments_and_last_screen_validation(self):
        screen={'id':7,'enabled':True,'currentModeId':'2','scale':1.25,
                'rotation':1,'pos':{'x':1920,'y':0}}
        current=display.settings(screen)
        self.assertEqual(display.arguments(current,{'1','2'}),
                         ['output.7.enable','output.7.mode.2','output.7.scale.1.25',
                          'output.7.rotation.none','output.7.position.1920,0'])
        with self.assertRaises(ValueError):display.arguments({**current,'mode':'3'}, {'1','2'})
        with self.assertRaises(ValueError):display.arguments({**current,'scale':8}, {'2'})

    def test_vnc_file_is_private_and_password_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'krfbrc'
            with patch.object(remote,'config_path',return_value=path),patch.object(remote,'command'):
                password=remote.set_vnc(True,5901)
                self.assertEqual(len(password),8)
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
                with patch.object(remote,'active',return_value=True):
                    self.assertEqual(remote.vnc_settings()['password'],password)
                cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read(path)
                self.assertEqual(cfg['TCP']['port'],'5901')
                self.assertNotEqual(cfg['Security']['desktopPassword'],password)
                self.assertEqual(cfg['Security']['allowUnattendedAccess'],'false')

    def test_rdp_uses_system_account_and_session_service(self):
        with patch.dict(remote.os.environ,{'XDG_SESSION_TYPE':'wayland'}),patch.object(remote,'command') as command:
            remote.set_rdp(True,3390)
        calls=[entry.args for entry in command.call_args_list]
        self.assertIn(('kwriteconfig6','--file','krdpserverrc','--group','General','--key','SystemUserEnabled','true'),calls)
        self.assertIn(('systemctl','--user','enable','--now',remote.RDP_UNIT),calls)
        with patch.dict(remote.os.environ,{'XDG_SESSION_TYPE':'x11'}):
            with self.assertRaises(ValueError):remote.set_rdp(True,3389)

    def test_each_dark_scheme_has_light_foreground_and_own_identity(self):
        root=ROOT/'packages/linuxbr-desktop/files/usr/share/color-schemes'
        for path in root.glob('LinuxBRDark*.colors'):
            cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read(path)
            self.assertEqual(cfg['General']['ColorScheme'],path.stem)
            r,g,b=map(int,cfg['Colors:Window']['ForegroundNormal'].split(','))
            self.assertGreater(min(r,g,b),200)

    def test_power_profile_is_written_and_refreshed_inside_central(self):
        values={'screen':600,'screen_enabled':True,'suspend':900,
                'suspend_action':1,'lid':0,'power':16}
        with patch.object(power,'command') as command:
            power.write('AC',values)
        calls=[entry.args for entry in command.call_args_list]
        self.assertIn(('kwriteconfig6','--file','powerdevilrc','--group','AC',
                       '--group','Display','--key','TurnOffDisplayIdleTimeoutSec','600'),calls)
        self.assertIn(('dbus-send','--session','--type=method_call',
                       '--dest=org.kde.Solid.PowerManagement','/org/kde/Solid/PowerManagement',
                       'org.kde.Solid.PowerManagement.refreshStatus'),calls)
        with self.assertRaises(ValueError):power.write('Unknown',values)
        with patch.object(power,'command') as command:
            power.write('AC',{**values,'screen':660},values)
        self.assertEqual(len(command.call_args_list),2)


if __name__=='__main__':unittest.main()
