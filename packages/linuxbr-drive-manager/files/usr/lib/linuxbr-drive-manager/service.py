#!/usr/bin/python3
"""One service per login session. State stays available when the UI is closed."""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Store
from service_model import query, places_for, resolve, computer_bookmark

BUS='org.linuxbr.DriveManager1'
PATH='/org/linuxbr/DriveManager1'

class Service(dbus.service.Object):
    def __init__(self, name):
        super().__init__(name, PATH)
        self.session_bus=dbus.SessionBus()
        self.store=Store()
        self.pool=ThreadPoolExecutor(max_workers=1)
        self.busy=False; self.again=False
        self.state=dict(rows=[], data=dict(letters={},shares={}), places=[], error='Consultando unidades…')
        system=dbus.SystemBus()
        for signal, interface in [('InterfacesAdded','org.freedesktop.DBus.ObjectManager'),
                                  ('InterfacesRemoved','org.freedesktop.DBus.ObjectManager'),
                                  ('PropertiesChanged','org.freedesktop.DBus.Properties')]:
            system.add_signal_receiver(self.changed, signal_name=signal, dbus_interface=interface,
                                       bus_name='org.freedesktop.UDisks2')
        system.add_signal_receiver(self.changed, signal_name='NameOwnerChanged',
                                   dbus_interface='org.freedesktop.DBus',arg0='org.freedesktop.UDisks2')
        GLib.timeout_add_seconds(5, self.tick)
        self.refresh()

    def changed(self,*args): self.refresh()
    def tick(self): self.refresh(); return True
    def refresh(self):
        if self.busy: self.again=True; return
        self.busy=True
        def collect():
            rows=query(['list'])
            data=self.store.discover(rows)
            places=places_for(rows,data)
            result=subprocess.run(['/usr/lib/linuxbr-drive-manager/linuxbr-places-sync'],
                                  input=json.dumps(computer_bookmark()), text=True, capture_output=True, timeout=15)
            error='' if result.returncode==0 else 'Não foi possível atualizar os Locais do Explorador de arquivos; os favoritos existentes foram preservados.'
            return dict(rows=rows,data=data,places=places,error=error)
        future=self.pool.submit(collect)
        future.add_done_callback(lambda result: GLib.idle_add(self.complete,result))

    def complete(self,future):
        self.busy=False
        try: state=future.result()
        except Exception as error:
            state={**self.state,'error':str(error)}
        if state!=self.state:
            self.state=state; self.Changed()
            # KDirLister refreshes an open Computer view when drives/shares change.
            signal=dbus.lowlevel.SignalMessage('/', 'org.kde.KDirNotify', 'FilesAdded')
            signal.append('linuxbr:/',signature='s')
            self.session_bus.send_message(signal)
        if self.again:
            self.again=False; self.refresh()
        return False

    @dbus.service.signal(BUS,signature='')
    def Changed(self): pass

    @dbus.service.method(BUS,out_signature='s')
    def GetState(self): return json.dumps(self.state,ensure_ascii=False)

    @dbus.service.method(BUS,in_signature='ss',out_signature='s')
    def Assign(self,key,letter):
        result=self.store.assign(str(key),str(letter)); self.refresh(); return json.dumps(result)

    @dbus.service.method(BUS,in_signature='ss',out_signature='s')
    def AddShare(self,url,label):
        result=self.store.add_share(str(url),str(label)); self.refresh(); return json.dumps(result)

    @dbus.service.method(BUS,in_signature='s',out_signature='s')
    def Forget(self,key):
        result=self.store.forget(str(key)); self.refresh(); return json.dumps(result)

    @dbus.service.method(BUS,in_signature='s',out_signature='s',async_callbacks=('reply','error'))
    def Resolve(self,letter,reply,error):
        future=self.pool.submit(resolve,str(letter),self.store)
        def done(result):
            def deliver():
                try: reply(result.result())
                except Exception as exc: error(dbus.exceptions.DBusException(str(exc),name=BUS+'.Unavailable'))
                self.refresh(); return False
            GLib.idle_add(deliver)
        future.add_done_callback(done)

if __name__=='__main__':
    DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus()
    try: name=dbus.service.BusName(BUS,bus=bus,do_not_queue=True)
    except dbus.exceptions.NameExistsException: raise SystemExit(0)
    service=Service(name)
    GLib.MainLoop().run()
