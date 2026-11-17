"""Exercise the monitor chooser without recording or retaining a stream."""
import sys
import uuid

from gi.repository import Gio, GLib


SERVICE = 'org.freedesktop.portal.Desktop'
DESKTOP = '/org/freedesktop/portal/desktop'
SCREENCAST = 'org.freedesktop.portal.ScreenCast'
REQUEST = 'org.freedesktop.portal.Request'
SESSION = 'org.freedesktop.portal.Session'


class Portal:
    def __init__(self):
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.sender = self.connection.get_unique_name()[1:].replace('.', '_')

    def call(self, path, interface, method, args=None):
        return self.connection.call_sync(
            SERVICE, path, interface, method, args, None,
            Gio.DBusCallFlags.NONE, 8000, None)

    def request(self, method, args, options):
        token = 'linuxbr_' + uuid.uuid4().hex
        options['handle_token'] = GLib.Variant('s', token)
        request_path = f'/org/freedesktop/portal/desktop/request/{self.sender}/{token}'
        loop = GLib.MainLoop()
        reply = None

        def response(_connection, _sender, _path, _interface, _signal, parameters, *_rest):
            nonlocal reply
            reply = parameters.unpack()
            loop.quit()

        subscription = self.connection.signal_subscribe(
            SERVICE, REQUEST, 'Response', request_path, None, Gio.DBusSignalFlags.NONE, response)
        timer = None
        try:
            result = self.call(DESKTOP, SCREENCAST, method,
                               GLib.Variant(args[0], (*args[1:], options)))
            if result.unpack()[0] != request_path:
                raise RuntimeError('O portal devolveu um identificador de solicitação inesperado.')

            def expire():
                nonlocal timer
                timer = None
                loop.quit()
                return GLib.SOURCE_REMOVE

            timer = GLib.timeout_add_seconds(60, expire)
            if reply is None:
                loop.run()
            if reply is None:
                self.call(request_path, REQUEST, 'Close')
                raise RuntimeError('A seleção de tela terminou por tempo excedido.')
            code, values = reply
            if code == 1:
                raise RuntimeError('Seleção cancelada. Abra o teste novamente para escolher uma tela.')
            if code != 0:
                raise RuntimeError('O portal recusou a operação nesta sessão.')
            return values
        finally:
            if timer is not None:
                GLib.source_remove(timer)
            self.connection.signal_unsubscribe(subscription)

    def check(self):
        types, = self.call(DESKTOP, 'org.freedesktop.DBus.Properties', 'Get',
                           GLib.Variant('(ss)', (SCREENCAST, 'AvailableSourceTypes'))).unpack()
        if not types & 1:
            raise RuntimeError('O portal desta sessão não oferece captura de monitor inteiro.')
        session = self.request('CreateSession', ('(a{sv})',), {
            'session_handle_token': GLib.Variant('s', 'linuxbr_' + uuid.uuid4().hex),
        })['session_handle']
        try:
            self.request('SelectSources', ('(oa{sv})', session), {'types': GLib.Variant('u', 1)})
            streams = self.request('Start', ('(osa{sv})', session, ''), {}).get('streams', [])
            if not streams:
                raise RuntimeError('A janela de seleção abriu, mas o portal não retornou uma fonte PipeWire.')
            reply, descriptors = self.connection.call_with_unix_fd_list_sync(
                SERVICE, DESKTOP, SCREENCAST, 'OpenPipeWireRemote', GLib.Variant('(oa{sv})', (session, {})),
                None, Gio.DBusCallFlags.NONE, 8000, None, None)
            if descriptors is None or reply.unpack()[0] >= descriptors.get_length():
                raise RuntimeError('A seleção foi aceita, mas a conexão PipeWire não está disponível.')
            print('A seleção de tela e a conexão PipeWire funcionaram nesta sessão.')
            print('Se a falha ocorrer somente em um aplicativo, confira a permissão de captura e as opções de compartilhamento nele.')
        finally:
            try:
                self.call(session, SESSION, 'Close')
            except GLib.Error:
                pass


def main():
    from support_diagnostics import collect

    status = collect('graphics')
    print('Sessão gráfica ' + status['sessão'], flush=True)
    print('Portal ' + status['xdg-desktop-portal'] + ' · PipeWire ' + status['pipewire'], flush=True)
    if status['pipewire'] == 'failed':
        print('O serviço PipeWire falhou. Consulte o diagnóstico da sessão gráfica.', file=sys.stderr)
        return 1
    try:
        Portal().check()
    except GLib.Error as error:
        name = Gio.DBusError.get_remote_error(error)
        print('O portal não concluiu a captura' + (' (' + name + ').' if name else '.'), file=sys.stderr)
        return 1
    except (KeyError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
