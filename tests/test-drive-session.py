#!/usr/bin/env python3
"""Run under dbus-run-session in a disposable Debian container.
Real session D-Bus service, native Places and KIO; simulated UDisks inventory only.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import dbus
ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'
if len(sys.argv)>1 and sys.argv[1]=='server':
    sys.path.insert(0,str(LIB))
    import service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    # The storage backend is the only fixture; session bus/JSON/Places are real.
    class System:
        def add_signal_receiver(self,*args,**kwargs): pass
    dbus.SystemBus=lambda:System()
    row=dict(key='uuid:test',name='Dados',kind='Volume',mounts=[os.environ['TEST_VOLUME']],mountable=True,protected=False,path='/block/test',device='/dev/test',usage=dict(total=100*1024**3,used=60*1024**3,free=40*1024**3,reserved=0))
    service.query=lambda args:[row]
    import service_model
    original=service_model.resolve
    service.resolve=lambda letter,store:original(letter,store,lambda args:[row])
    name=dbus.service.BusName(service.BUS,bus=dbus.SessionBus(),do_not_queue=True)
    instance=service.Service(name)
    GLib.MainLoop().run()
else:
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    notifications=[]
    dbus.SessionBus().add_signal_receiver(lambda url:notifications.append(str(url)),signal_name='FilesAdded',dbus_interface='org.kde.KDirNotify',path='/')
    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ,XDG_CONFIG_HOME=tmp+'/config',XDG_DATA_HOME=tmp+'/data',TEST_VOLUME=tmp+'/volume')
        volume=Path(env['TEST_VOLUME']);volume.mkdir();(volume/'sentinel').touch()
        process=subprocess.Popen([sys.executable,__file__,'server'],env=env)
        try:
            for attempt in range(100):
                try:
                    proxy=dbus.Interface(dbus.SessionBus().get_object('org.linuxbr.DriveManager1','/org/linuxbr/DriveManager1'),'org.linuxbr.DriveManager1')
                    state=json.loads(proxy.GetState())
                    if state['rows']:break
                except dbus.DBusException:pass
                time.sleep(.1)
            else:raise AssertionError('service failed to initialize')
            assert not state['error'],state
            import xml.etree.ElementTree as ET
            bookmarks=ET.parse(Path(env['XDG_DATA_HOME'])/'user-places.xbel').getroot().findall('bookmark')
            assert [b.get('href') for b in bookmarks]==['linuxbr:/']
            assert (Path(env['XDG_DATA_HOME'])/'dolphin/view_properties/linuxbr-computer/.directory').is_file()
            assert state['data']['letters']['uuid:test']=='D'
            assert str(proxy.Resolve('D'))==volume.as_uri()
            data=json.loads(proxy.AddShare('smb://server/team','Equipe'))
            assert str(proxy.Resolve(data['letters']['smb:smb://server/team']))=='smb://server/team'
            subprocess.run([os.environ['KIO_PROBE']],env=env,check=True,timeout=30)
            json.loads(proxy.Assign('uuid:test','E'))
            assert str(proxy.Resolve('E'))==volume.as_uri()
            process.terminate();process.wait(timeout=10)
            process=subprocess.Popen([sys.executable,__file__,'server'],env=env)
            for attempt in range(100):
                try:
                    proxy=dbus.Interface(dbus.SessionBus().get_object('org.linuxbr.DriveManager1','/org/linuxbr/DriveManager1'),'org.linuxbr.DriveManager1')
                    state=json.loads(proxy.GetState())
                    if state['rows']:break
                except dbus.DBusException:pass
                time.sleep(.1)
            assert state['data']['letters']['uuid:test']=='E',state
            context=GLib.MainContext.default()
            while context.pending():context.iteration(False)
            assert 'linuxbr:/' in notifications,notifications
            print('PASS: real D-Bus session, native Dolphin Places, KIO redirect, persistent aliases across service restart')
        finally:
            process.terminate();process.wait(timeout=10)
