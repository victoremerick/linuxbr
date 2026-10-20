"""Conservative partition plans from a complete UDisks snapshot (no disk writes)."""
import hashlib
import json
from core import PREFIX, decode

MIB = 1024**2
FORMATS = ('ext4', 'ntfs', 'exfat', 'vfat')
DATA_TYPES = {'gpt': {'0fc63daf-8483-4772-8e79-3d69d8477de4', 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'},
              'dos': {'0x83', '0x07', '0x0b', '0x0c', '0x06', '0x0e'}}


def describe(objects, disk_path):
    interfaces = objects.get(disk_path, {})
    disk = interfaces.get(PREFIX+'Block', {})
    table = interfaces.get(PREFIX+'PartitionTable', {})
    scheme = str(table.get('Type', ''))
    drive = objects.get(str(disk.get('Drive', '/')), {}).get(PREFIX+'Drive', {})
    parts = []
    reason = ''
    if scheme not in ('gpt', 'dos'): reason = 'Tabela de partições não suportada; use um disco GPT ou MBR básico.'
    for path, values in objects.items():
        part = values.get(PREFIX+'Partition', {})
        if str(part.get('Table', '')) != disk_path: continue
        block = values.get(PREFIX+'Block', {})
        fs = values.get(PREFIX+'Filesystem', {})
        parts.append(dict(path=str(path), start=int(part.get('Offset', 0)), size=int(part.get('Size', block.get('Size', 0))),
                          uuid=str(part.get('UUID', '')), type=str(part.get('Type', '')).lower(),
                          flags=int(part.get('Flags', 0)), device=decode(block.get('Device', b'')),
                          fs=str(block.get('IdType', '')), fsuuid=str(block.get('IdUUID', '')),
                          number=int(part.get('Number', 0))))
        if part.get('IsContainer') or part.get('IsContained'):
            reason = 'Partições MBR estendidas/lógicas não são suportadas nesta tela.'
        if fs.get('MountPoints') or values.get(PREFIX+'Swapspace', {}).get('Active'):
            reason = 'Desmonte todos os volumes deste disco antes de alterar partições. O disco do sistema em uso fica protegido.'
        if block.get('ReadOnly'):
            reason = 'Há um volume somente leitura neste disco.'
        if block.get('Configuration'):
            reason = 'Disco com volumes configurados no sistema (fstab/crypttab); alterações bloqueadas.'
        if (PREFIX+'Encrypted' in values or block.get('IdUsage', '') not in ('', 'filesystem') or
                str(block.get('CryptoBackingDevice', '/')) != '/' or str(block.get('MDRaidMember', '/')) != '/'):
            reason = 'Discos com criptografia, swap, RAID ou LVM não são editáveis nesta tela.'
    parts.sort(key=lambda p: p['start'])
    listed = {str(p) for p in table.get('Partitions', [])}
    if listed != {p['path'] for p in parts}: reason = 'Inventário incompleto; atualize antes de continuar.'
    if disk.get('ReadOnly') or interfaces.get(PREFIX+'Filesystem', {}).get('MountPoints'):
        reason = 'Disco somente leitura ou em uso.'
    if (disk.get('Configuration') or str(disk.get('CryptoBackingDevice', '/')) != '/' or
            str(disk.get('MDRaid', '/')) != '/' or str(disk.get('MDRaidMember', '/')) != '/' or
            PREFIX+'Encrypted' in interfaces or PREFIX+'Partition' in interfaces):
        reason = 'Dispositivo composto ou configurado no sistema; alterações bloqueadas.'
    if not drive and PREFIX+'Loop' not in interfaces:
        reason = 'Identidade do disco físico indisponível.'
    # Reserve a full MiB at either edge for alignment and partition-table metadata.
    end = (int(disk.get('Size', 0)) // MIB - 1) * MIB
    cursor = MIB
    gaps = []
    geometry_ok = scheme in ('gpt', 'dos') and listed == {p['path'] for p in parts}
    for part in parts:
        if part['start'] < cursor or part['size'] <= 0 or part['start'] + part['size'] > int(disk.get('Size', 0)):
            geometry_ok = False
        gap_end = part['start'] // MIB * MIB
        if gap_end > cursor: gaps.append(dict(start=cursor, size=gap_end-cursor))
        cursor = ((part['start'] + part['size'] + MIB - 1)//MIB)*MIB
    if end > cursor: gaps.append(dict(start=cursor, size=end-cursor))
    if not geometry_ok:
        gaps = []; reason = reason or 'Geometria complexa ou incompleta; alterações bloqueadas.'
    identity = dict(path=disk_path, device=decode(disk.get('Device', b'')), size=int(disk.get('Size', 0)),
                    devnum=int(disk.get('DeviceNumber', 0)), drive=str(disk.get('Drive', '')),
                    serial=str(drive.get('Serial', '')), wwn=str(drive.get('WWN', '')),
                    detected=int(drive.get('TimeDetected', 0)), media=int(drive.get('TimeMediaDetected', 0)),
                    loop=str(interfaces.get(PREFIX+'Loop', {}).get('BackingFile', '')), scheme=scheme, parts=parts)
    token = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return dict(path=disk_path, device=identity['device'], size=identity['size'], scheme=scheme,
                parts=parts, gaps=gaps, end=end, reason=reason, token=token, identity=identity)


def annotate(rows, objects):
    disks = {str(path): describe(objects, str(path)) for path, value in objects.items() if PREFIX+'PartitionTable' in value}
    for row in rows:
        disk = disks.get(row.get('parent') or row.get('path'))
        if disk:
            row['partition_disk'] = disk
    return rows


def plan(snapshot, request):
    if snapshot['token'] != request.get('token'): raise ValueError('O disco ou suas partições mudaram. Atualize e confirme novamente.')
    if snapshot['reason']: raise ValueError(snapshot['reason'])
    action = request.get('action')
    if action not in ('create', 'delete', 'format', 'resize'): raise ValueError('Operação inválida.')
    target = next((p for p in snapshot['parts'] if p['path'] == request.get('path')), None)
    size = request.get('size', 0)
    if type(size) is not int or size < 0: raise ValueError('Tamanho inválido.')
    if action == 'create':
        gap = next((g for g in snapshot['gaps'] if g['start'] == request.get('start')), None)
        if not gap or size < MIB or size % MIB or size > gap['size']: raise ValueError('A partição não cabe no espaço não alocado selecionado.')
        if snapshot['scheme'] == 'dos' and len(snapshot['parts']) >= 4: raise ValueError('MBR permite no máximo quatro partições primárias.')
    else:
        if not target: raise ValueError('Partição desconectada ou indisponível.')
        if target['type'] not in DATA_TYPES[snapshot['scheme']] or target['flags']:
            raise ValueError('Partição de sistema, inicialização ou tipo especial protegida.')
    if action in ('create', 'format') and request.get('format') not in FORMATS:
        raise ValueError('Formato não suportado.')
    if action == 'resize':
        if target['fs'] != 'ext4': raise ValueError('Redimensionamento integrado disponível para ext4 desmontado.')
        limit = min([p['start'] for p in snapshot['parts'] if p['start'] > target['start']] + [snapshot['end']])
        if size < 32*MIB or size % MIB or target['start'] + size > limit or size == target['size']:
            raise ValueError('Tamanho inválido ou sem espaço contíguo à direita. Mínimo: 32 MiB.')
    return target
