"""UDisks-authorized disk changes. Never invoke a shell or force a busy device."""
import copy
import fcntl
import os
from pathlib import Path
import dbus
from core import PREFIX
from partitioning import describe, plan


def execute(bus, manager, request):
    # Serialize operations from this user's windows, without privileged filesystem writes.
    directory = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (directory / 'linuxbr-partitions.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Outra operação de particionamento está em andamento.')
        return run(bus, manager, request)


def run(bus, manager, request):
    def interface(path, name):
        return dbus.Interface(bus.get_object('org.freedesktop.UDisks2', path), PREFIX+name)
    def snapshot():
        objects = manager.GetManagedObjects(timeout=30)
        related = {request['disk']} | {str(p) for p, value in objects.items() if str(value.get(PREFIX+'Partition', {}).get('Table', '')) == request['disk']}
        for interfaces in objects.values():
            job = interfaces.get(PREFIX+'Job', {})
            if job and related.intersection(str(p) for p in job.get('Objects', [])):
                raise ValueError('Há uma operação em andamento neste disco.')
        return describe(objects, request['disk'])
    initial = snapshot()
    target = plan(initial, request)
    opts = dbus.Dictionary({}, signature='sv')
    admin = interface('/org/freedesktop/UDisks2/Manager', 'Manager')
    action = request['action']
    if action in ('create', 'format'):
        available, missing = admin.CanFormat(request['format'], timeout=30)
        if not available: raise ValueError('Ferramenta de formatação indisponível: ' + str(missing))
    if action == 'resize':
        available, modes, missing = admin.CanResize(target['fs'], timeout=30)
        shrink = request['size'] < target['size']
        if not available or not (int(modes) & (2 if shrink else 4)):
            raise ValueError('Redimensionamento offline indisponível: ' + str(missing))
        check, missing = admin.CanCheck(target['fs'], timeout=30)
        if not check: raise ValueError('Verificação do sistema de arquivos indisponível: ' + str(missing))
        prepare, missing = admin.CanRepair(target['fs'], timeout=30)
        if not prepare: raise ValueError('Preparação do sistema de arquivos indisponível: ' + str(missing))

    def guard(changed_size=None):
        current = snapshot()
        if current['reason']: raise ValueError(current['reason'])
        expected = copy.deepcopy(initial['identity'])
        if changed_size is not None:
            for p in expected['parts']:
                if p['path'] == target['path']: p['size'] = changed_size
        if current['identity'] != expected:
            raise ValueError('O dispositivo mudou durante a operação; nenhuma outra etapa será executada.')
        return current

    guard()
    if action == 'create':
        kind = ('0fc63daf-8483-4772-8e79-3d69d8477de4' if request['format'] == 'ext4' else 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7') if initial['scheme'] == 'gpt' else ('0x83' if request['format'] == 'ext4' else '0x0c' if request['format'] == 'vfat' else '0x07')
        try:
            interface(request['disk'], 'PartitionTable').CreatePartitionAndFormat(
                dbus.UInt64(request['start']), dbus.UInt64(request['size']), kind, '', opts,
                request['format'], opts, timeout=86400)
        except Exception as error:
            raise ValueError('Criação/formatação interrompida. A partição pode ter sido criada sem formato; atualize antes de repetir. ' + str(error))
    elif action == 'delete':
        interface(target['path'], 'Partition').Delete(opts, timeout=86400)
    elif action == 'format':
        interface(target['path'], 'Block').Format(request['format'], opts, timeout=86400)
    else:
        fs = interface(target['path'], 'Filesystem')
        part = interface(target['path'], 'Partition')
        if not fs.Check(opts, timeout=86400):
            raise ValueError('O sistema de arquivos contém erros. Nenhuma alteração de tamanho foi iniciada.')
        guard()
        size = request['size']
        phase = 'durante a preparação do ext4; os tamanhos ainda não foram alterados'
        try:
            # Check is read-only (e2fsck -fn) and does not record a successful fsck.
            # resize2fs requires that record after the last mount. UDisks Repair
            # records it; invoke ONLY after Check succeeded on this unmounted FS.
            # Never use Repair as a fallback when Check reports existing damage.
            if not fs.Repair(opts, timeout=86400):
                raise ValueError('A preparação do ext4 não foi concluída.')
            guard()
            if not fs.Check(opts, timeout=86400):
                raise ValueError('O ext4 não passou na verificação após a preparação.')
            guard()
            phase = 'após preparar o ext4; os tamanhos ainda não foram alterados'
            if shrink:
                # Never shrink the containing partition until filesystem shrink succeeded.
                fs.Resize(dbus.UInt64(size), opts, timeout=86400)
                phase = 'após reduzir o sistema de arquivos; a partição pode continuar maior'
                guard()
                properties = dbus.Interface(bus.get_object('org.freedesktop.UDisks2', target['path']), 'org.freedesktop.DBus.Properties')
                actual = int(properties.Get(PREFIX+'Filesystem', 'Size', timeout=30))
                if not 0 < actual <= size: raise ValueError('Não foi possível confirmar o novo limite do sistema de arquivos.')
                part.Resize(dbus.UInt64(size), opts, timeout=86400)
            else:
                # Grow container first; a failed FS grow leaves a valid smaller filesystem.
                part.Resize(dbus.UInt64(size), opts, timeout=86400)
                phase = 'após ampliar a partição; o sistema de arquivos pode continuar menor'
                guard(changed_size=size)
                fs.Resize(dbus.UInt64(size), opts, timeout=86400)
        except Exception as error:
            raise ValueError(f'Redimensionamento interrompido {phase}. Não houve reversão automática. Atualize e confira as propriedades. {error}')
    return 'Operação concluída. Atualizando discos…'
