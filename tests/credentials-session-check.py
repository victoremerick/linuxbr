#!/usr/bin/python3
"""Exercise a real secret provider on an isolated D-Bus and temporary home."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system/credentials.py'


def main():
    address = os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')
    if not address or '/run/user/' in address:
        raise SystemExit('Execute este teste com dbus-run-session em uma sessão isolada.')
    with tempfile.TemporaryDirectory(prefix='linuxbr-credentials-test-') as directory:
        home = Path(directory)
        runtime = home/'runtime'
        runtime.mkdir(mode=0o700)
        control = runtime/'keyring'
        control.mkdir(mode=0o700)
        os.environ.update(HOME=str(home), XDG_DATA_HOME=str(home/'data'),
                          XDG_CONFIG_HOME=str(home/'config'), XDG_RUNTIME_DIR=str(runtime),
                          DISPLAY='', WAYLAND_DISPLAY='')
        os.environ.pop('GNOME_KEYRING_CONTROL', None)
        log = (home/'provider.log').open('w')
        provider = subprocess.Popen(['gnome-keyring-daemon', '--foreground', '--components=secrets',
                                     '--control-directory='+str(control)], stdout=log, stderr=log)
        try:
            import gi
            gi.require_version('Secret', '1')
            from gi.repository import Gio, GLib, Secret
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            for _ in range(60):
                if bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                        'org.freedesktop.DBus', 'NameHasOwner',
                        GLib.Variant('(s)', ('org.freedesktop.secrets',)),
                        None, Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError('Provedor isolado não iniciou.')

            def check(expected, *options):
                process = subprocess.run([sys.executable, str(COMMAND), '--check', *options],
                                         capture_output=True, text=True, timeout=12)
                result = json.loads(process.stdout)
                assert result['state'] == expected, result
                return result

            check('missing')
            subprocess.run(['gnome-keyring-daemon', '--unlock', '--control-directory='+str(control)],
                           input='senha-apenas-do-teste-isolado', text=True,
                           capture_output=True, check=True, timeout=10)
            # Load the newly provisioned encrypted store in a fresh provider process.
            provider.terminate()
            provider.wait(timeout=5)
            provider = subprocess.Popen(['gnome-keyring-daemon', '--foreground', '--components=secrets',
                                         '--control-directory='+str(control)], stdout=log, stderr=log)
            time.sleep(0.3)
            subprocess.run(['gnome-keyring-daemon', '--unlock', '--control-directory='+str(control)],
                           input='senha-apenas-do-teste-isolado', text=True,
                           capture_output=True, check=True, timeout=10)
            prepared = subprocess.run([sys.executable, str(COMMAND), '--prepare-session'],
                                      capture_output=True, text=True, timeout=12)
            assert json.loads(prepared.stdout)['state'] == 'ready', prepared.stdout
            assert check('ready', '--probe')['write_verified']
            service = Secret.Service.get_sync(Secret.ServiceFlags.OPEN_SESSION, None)
            collection = Secret.Collection.for_alias_sync(service, 'default', Secret.CollectionFlags.LOAD_ITEMS, None)
            assert collection is not None and not collection.get_items(), 'Entrada temporária não removida.'
            service.lock_sync([collection], None)
            assert not check('locked', '--probe')['write_verified']
            print(json.dumps(dict(result='PASS', isolated_bus=True, temporary_home=True,
                                  missing=True, write_read_remove=True, locked_without_prompt=True)))
        finally:
            provider.terminate()
            try:
                provider.wait(timeout=5)
            except subprocess.TimeoutExpired:
                provider.kill()
                provider.wait()
            log.close()


if __name__ == '__main__':
    main()
