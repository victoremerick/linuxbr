"""Shared service client; never creates a second letter database."""
import json
import dbus
BUS='org.linuxbr.DriveManager1'
def interface():
    return dbus.Interface(dbus.SessionBus().get_object(BUS,'/org/linuxbr/DriveManager1'), BUS)

def state(): return json.loads(interface().GetState(timeout=5))

class ServiceStore:
    def call(self,name,*args):
        try: return json.loads(getattr(interface(),name)(*args,timeout=5))
        except dbus.DBusException as error: raise ValueError(str(error))
    def assign(self,key,letter): return self.call('Assign',key,letter)
    def add_share(self,url,label): return self.call('AddShare',url,label)
    def forget(self,key): return self.call('Forget',key)
    def discover(self,rows): return state()['data']

if __name__=='__main__':
    try: print(json.dumps({'result':state()},ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False)); raise SystemExit(1)
