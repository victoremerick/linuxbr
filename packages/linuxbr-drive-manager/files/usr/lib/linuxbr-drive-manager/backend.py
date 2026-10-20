"""Short-lived D-Bus worker; launched without root, with polkit authorization."""
import json
import sys
import dbus
from core import PREFIX, inventory
from capacity import enrich


def main():
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object('org.freedesktop.UDisks2', '/org/freedesktop/UDisks2'), 'org.freedesktop.DBus.ObjectManager')
    objects = manager.GetManagedObjects(timeout=20)
    if sys.argv[1] == 'list':
        from partitioning import annotate
        return enrich(annotate(inventory(objects), objects))
    if sys.argv[1] == 'partition':
        from partition_worker import execute
        return execute(bus, manager, json.loads(sys.argv[2]))
    operation, path = sys.argv[1:3]
    if operation not in ('mount', 'unmount'):
        raise ValueError('Operação desconhecida.')
    row = next((r for r in inventory(objects) if r['path'] == path), None)
    if not row or not row.get('mountable') or row['protected']:
        raise ValueError('Volume indisponível ou protegido. Atualize a lista.')
    # Recheck identity after selection; hot-unplug must not redirect an operation.
    if row['key'] != sys.argv[3] or row['device'] != sys.argv[4]:
        raise ValueError('O dispositivo mudou. Atualize a lista antes de continuar.')
    fs = dbus.Interface(bus.get_object('org.freedesktop.UDisks2', path), PREFIX + 'Filesystem')
    options = dbus.Dictionary({}, signature='sv')
    if operation == 'mount':
        return str(fs.Mount(options, timeout=120))
    fs.Unmount(options, timeout=120)
    return 'Volume desmontado.'

if __name__ == '__main__':
    try:
        print(json.dumps({'result': main()}, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        sys.exit(1)
