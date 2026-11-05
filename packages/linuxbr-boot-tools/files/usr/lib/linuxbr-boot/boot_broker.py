"""Allow an active local session to select authenticated maintenance for one boot."""
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import boot_backend


class Broker(dbus.service.Object):
    def __init__(self,bus):
        self.bus=bus
        self.name=dbus.service.BusName('org.linuxbr.Boot',bus=bus)
        super().__init__(self.name,'/org/linuxbr/Boot')

    @dbus.service.method('org.linuxbr.Boot',in_signature='',out_signature='b',sender_keyword='sender')
    def PrepareRecovery(self,sender=None):
        authority=dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1','/org/freedesktop/PolicyKit1/Authority'),'org.freedesktop.PolicyKit1.Authority')
        subject=('system-bus-name',{'name':dbus.String(sender,variant_level=1)})
        authorized,_,_=authority.CheckAuthorization(subject,'org.linuxbr.boot.recovery',{},dbus.UInt32(0),'',timeout=5)
        if not authorized:raise dbus.exceptions.DBusException('Use uma sessão local ativa para solicitar a manutenção.',name='org.linuxbr.Boot.NotAuthorized')
        try:boot_backend.configure({'action':'once','mode':'recovery'})
        except Exception as error:raise dbus.exceptions.DBusException(str(error),name='org.linuxbr.Boot.Failed') from None
        print('Manutenção selecionada para um boot por sessão local autorizada.',flush=True)
        return True


if __name__=='__main__':
    DBusGMainLoop(set_as_default=True)
    service=Broker(dbus.SystemBus());loop=GLib.MainLoop()
    GLib.timeout_add_seconds(30,lambda:(loop.quit(),False)[1]);loop.run()
