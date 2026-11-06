"""Check and unlock the desktop secret store without reading saved credentials."""
import argparse
import json
import secrets
import threading
import uuid


MESSAGES = {
    'ready': 'O cofre de credenciais está desbloqueado.',
    'locked': 'O cofre está bloqueado. Desbloqueie-o antes de entrar nos aplicativos.',
    'missing': 'Esta conta ainda não tem um cofre padrão. Prepare o cofre antes de entrar nos aplicativos.',
    'unavailable': 'O armazenamento seguro não está disponível. Confira o serviço e o cofre em Credenciais e senhas.',
}


def response(state, verified=False):
    return dict(state=state, text=MESSAGES[state], write_verified=verified)


def libraries():
    import gi
    gi.require_version('Secret', '1')
    from gi.repository import Gio, Secret
    return Gio, Secret


def storage_probe(secret, collection, cancel):
    """Only read and remove the unique temporary item created by this check."""
    schema = secret.Schema.new('org.linuxbr.CredentialCheck', secret.SchemaFlags.NONE,
                               {'probe': secret.SchemaAttributeType.STRING})
    attributes = {'probe': uuid.uuid4().hex}
    value = secrets.token_urlsafe(24)
    try:
        if not secret.password_store_sync(schema, attributes, collection,
                'Verificação temporária do cofre Linux BR', value, cancel):
            return False
        return secret.password_lookup_sync(schema, attributes, cancel) == value
    finally:
        # A failed cleanup is a failed check too; never leave a test secret behind silently.
        gio, _ = libraries()
        cleanup = gio.Cancellable()
        deadline = threading.Timer(3, cleanup.cancel)
        deadline.daemon = True
        deadline.start()
        try:
            if not secret.password_clear_sync(schema, attributes, cleanup):
                raise RuntimeError('Não foi possível remover a entrada temporária.')
        finally:
            deadline.cancel()


def inspect_store(unlock=False, probe=False):
    gio, secret = libraries()
    cancel = gio.Cancellable()
    timer = threading.Timer(120 if unlock else 3, cancel.cancel)
    timer.daemon = True
    timer.start()
    try:
        flags = secret.ServiceFlags.OPEN_SESSION
        if unlock:
            flags |= secret.ServiceFlags.LOAD_COLLECTIONS
        service = secret.Service.get_sync(flags, cancel)
        collection = secret.Collection.for_alias_sync(service, 'default',
                                                      secret.CollectionFlags.NONE, cancel)
        if collection is None and unlock:
            collection = next((item for item in service.get_collections()
                               if item.get_object_path() == '/org/freedesktop/secrets/collection/login'), None)
            if collection is None:
                # The provider presents its own protected password prompt.
                collection = secret.Collection.create_sync(service, 'Senhas do Linux BR',
                                'default', secret.CollectionCreateFlags.NONE, cancel)
            else:
                service.set_alias_sync('default', collection, cancel)
        if collection is None:
            return response('missing')
        if collection.get_locked() and unlock:
            service.unlock_sync([collection], cancel)
            collection = secret.Collection.for_alias_sync(service, 'default',
                                                          secret.CollectionFlags.NONE, cancel)
        if collection is None:
            return response('missing')
        if collection.get_locked():
            return response('locked')
        if probe and not storage_probe(secret, collection.get_object_path(), cancel):
            return response('unavailable')
        return response('ready', verified=probe)
    finally:
        timer.cancel()


def status(unlock=False, probe=False):
    try:
        return inspect_store(unlock=unlock, probe=probe)
    except Exception:
        # Provider exceptions may contain private collection labels or application data.
        return response('unavailable')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verificar o cofre de credenciais da sessão.')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--check', action='store_true', help='Consultar o estado sem solicitar senhas.')
    actions.add_argument('--unlock', action='store_true', help='Solicitar o desbloqueio pelo provedor seguro.')
    actions.add_argument('--prepare-session', action='store_true', help='Preparar o cofre no início da sessão.')
    parser.add_argument('--probe', action='store_true', help='Testar uma entrada temporária no cofre desbloqueado.')
    args = parser.parse_args(argv)
    result = status(unlock=args.unlock or args.prepare_session, probe=args.probe)
    print(json.dumps(result, ensure_ascii=False))
    # A cancelled unlock must never prevent the desktop from starting.
    return 0 if args.prepare_session or result['state'] == 'ready' else 1


if __name__ == '__main__':
    raise SystemExit(main())
