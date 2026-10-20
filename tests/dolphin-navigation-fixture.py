"""Synthetic disks only; start inside an isolated session with a temporary HOME."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
import service,dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Store
DBusGMainLoop(set_as_default=True)
class System:
 def add_signal_receiver(self,*args,**kwargs):pass
service.dbus.SystemBus=lambda:System()
rows=[dict(key='system',name='Sistema',kind='Sistema',mounts=['/'],protected=True,usage=dict(total=128*1024**3,used=80*1024**3,free=44*1024**3,reserved=4*1024**3)),dict(key='uuid:data',name='Dados',kind='Volume',mounts=['/tmp'],mountable=True,protected=False,path='/data',device='/dev/test',usage=dict(total=256*1024**3,used=240*1024**3,free=16*1024**3,reserved=0)),dict(key='uuid:usb',name='Pendrive',kind='Removível',mounts=[],mountable=True,protected=False,path='/usb',device='/dev/test2')]
service.query=lambda args:rows
from service_model import resolve as resolve_fixture

def fixture_backend(args):
 if args==['list']: return rows
 raise ValueError('Fixture: mounting real devices is disabled')
service.resolve=lambda letter,store=None: resolve_fixture(letter,store=store,backend=fixture_backend)
Store().add_share('smb://servidor/empresa','Empresa')
name=dbus.service.BusName(service.BUS,bus=dbus.SessionBus(),do_not_queue=True)
instance=service.Service(name)
GLib.MainLoop().run()
