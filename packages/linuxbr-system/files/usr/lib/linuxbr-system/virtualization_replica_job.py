"""Create scheduled generations of an offline VM replica."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

from administration_backend import create_task
from virtualization_backend import Manager, checked_name, checked_uri


def parameters(origin, identifier, destination, pool, name, network):
    origin = checked_uri(origin)
    destination = checked_uri(destination)
    identifier = str(UUID(identifier))
    if not destination.startswith('qemu+ssh://') or destination == origin or origin == 'test:///default':
        raise ValueError('Escolha outro hospedeiro cadastrado por SSH.')
    for value in (pool, name, network):
        checked_name(value)
    if len(name) > 56 or len(name.encode('utf-8')) > 150:
        raise ValueError('Use até 56 caracteres e 150 bytes no nome para acrescentar a geração.')
    return origin, identifier, destination, pool, name, network


def schedule(origin, identifier, destination, pool, name, network, calendar):
    if os.geteuid() == 0:
        raise ValueError('Agende a réplica na sua conta normal com acesso aos dois hospedeiros.')
    args = parameters(origin, identifier, destination, pool, name, network)
    argv = ['/usr/bin/python3', str(Path(__file__).resolve()), *args]
    return create_task('user', 'Réplica de VM: ' + name, argv, calendar)


def execute(origin, identifier, destination, pool, name, network):
    origin, identifier, destination, pool, name, network = parameters(
        origin, identifier, destination, pool, name, network
    )
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    generation = f'{name}-{stamp}-{uuid4().hex[:5]}'
    manager = Manager(origin)
    try:
        result = manager.replicate_offline(identifier, destination, pool, generation, network)
        print(f'Réplica {generation} criada, desligada e na rede isolada {network}. Identificador {result["id"]}.')
    finally:
        manager.close()


if __name__ == '__main__':
    try:
        if len(sys.argv) != 7:
            raise ValueError('Informe a origem, a VM, o destino, o local dos discos, o nome e a rede.')
        execute(*sys.argv[1:])
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
