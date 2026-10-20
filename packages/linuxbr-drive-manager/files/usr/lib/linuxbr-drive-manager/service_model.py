"""Session service model: persistent identities and Dolphin places."""
import json
import subprocess
import sys
from pathlib import Path
from core import Store


def query(args):
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('backend.py')), *args],
                            capture_output=True, text=True, timeout=140)
    try: payload = json.loads(result.stdout)
    except ValueError: raise RuntimeError('Falha na consulta ao UDisks2: ' + result.stderr[-600:])
    if result.returncode or 'error' in payload: raise RuntimeError(payload.get('error', 'Operação não concluída.'))
    return payload['result']


def places_for(rows, data):
    places = [dict(key='system', name='Sistema (C:)', url='linuxbr:/C', icon='drive-harddisk', group='Discos locais')]
    for row in rows:
        key=row['key']; letter=data['letters'].get(key)
        if key != 'system' and key and letter and not row.get('protected'):
            places.append(dict(key=key, name=f"{row['name']} ({letter}:)", url='linuxbr:/' + letter,
                               icon='drive-removable-media' if row['kind']=='Removível' else 'drive-harddisk',
                               group='Dispositivos removíveis' if row['kind']=='Removível' else 'Discos locais'))
    for url, name in data['shares'].items():
        key='smb:' + url; letter=data['letters'].get(key)
        if letter: places.append(dict(key=key, name=f'{name} ({letter}:)', url='linuxbr:/' + letter, icon='folder-network', group='Unidades de rede'))
    indexed = {row['key']: row for row in rows}
    for place in places:
        row = indexed.get(place['key'], {})
        usage = row.get('usage')
        place['card'] = dict(title=place['name'], icon=place['icon'], usage=usage or {}, capacityText='Capacidade indisponível')
        if usage and usage.get('total', 0) > 0:
            percent = max(0, min(100, round(100 * usage['used'] / usage['total'])))
            kind = 'usb' if row.get('kind') == 'Removível' else 'disk'
            place['icon'] = f'/usr/share/linuxbr/drive-capacity/{kind}-{percent:03d}.svg'
            def amount(value):
                return f'{value / 1024**3:.1f} GiB' if value >= 1024**3 else f'{value / 1024**2:.1f} MiB'
            place['card']['capacityText'] = f"{amount(usage['free'])} livres de {amount(usage['total'])}"
            place['name'] += ' · ' + place['card']['capacityText']
        elif place['key'].startswith('smb:'):
            place['name'] += ' · Capacidade indisponível'
        elif row and not row.get('mounts'):
            place['card']['capacityText'] = 'Monte para consultar espaço'
            place['name'] += ' · Monte para consultar espaço'
    return sorted(places, key=lambda p:p['url'])


def resolve(letter, store=None, backend=query):
    store=store or Store()
    if letter == 'C': return Path('/').as_uri()
    if len(letter) != 1 or letter not in 'DEFGHIJKLMNOPQRSTUVWXYZ': raise ValueError('Letra inválida.')
    data=store.update()
    key=next((k for k,v in data['letters'].items() if v==letter), None)
    if key is None: raise ValueError('Letra não atribuída.')
    if key.startswith('smb:'):
        url=key[4:]
        if url not in data['shares']: raise ValueError('Compartilhamento removido.')
        return url
    rows=backend(['list'])
    row=next((r for r in rows if r['key']==key), None)
    if not row: raise ValueError('Unidade desconectada ou identificador duplicado.')
    if row['mounts']: target=row['mounts'][0]
    else:
        if not row.get('mountable') or row.get('protected'): raise ValueError('Este volume não pode ser montado pelo serviço.')
        target=backend(['mount', row['path'], key, row['device']])
    if not isinstance(target,str) or not target.startswith('/'): raise ValueError('Ponto de montagem inválido.')
    return Path(target).as_uri()


def computer_bookmark():
    return [dict(key='computer',name='Este computador',url='linuxbr:/',icon='computer')]
