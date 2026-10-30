"""Read and apply Plasma display outputs through the KScreen command interface."""
import json
import re
import subprocess

ROTATIONS = {1: 'none', 2: 'left', 4: 'inverted', 8: 'right'}
SAFE_MODE = re.compile(r'[A-Za-z0-9_.@-]{1,40}\Z')


def outputs():
    data = json.loads(subprocess.check_output(['kscreen-doctor', '--json'], text=True, timeout=8))
    return [item for item in data['outputs'] if item.get('connected')]


def settings(output):
    return {'id': int(output['id']), 'enabled': bool(output.get('enabled')),
            'mode': str(output.get('currentModeId', '')),
            'scale': float(output.get('scale', 1)),
            'rotation': ROTATIONS.get(output.get('rotation'), 'none'),
            'x': int(output.get('pos', {}).get('x', 0)),
            'y': int(output.get('pos', {}).get('y', 0))}


def arguments(values, modes):
    identity = values['id']
    if not isinstance(identity, int) or identity < 0 or identity > 9999:
        raise ValueError('Tela inválida.')
    prefix = f'output.{identity}.'
    if not values['enabled']:
        return [prefix + 'disable']
    mode = str(values['mode'])
    if mode not in modes or not SAFE_MODE.fullmatch(mode):
        raise ValueError('Resolução indisponível para esta tela.')
    scale = float(values['scale'])
    if not 0.5 <= scale <= 4:
        raise ValueError('Escala fora do intervalo permitido.')
    rotation = values['rotation']
    if rotation not in ROTATIONS.values():
        raise ValueError('Orientação inválida.')
    x, y = int(values['x']), int(values['y'])
    if not (-10000 <= x <= 10000 and -10000 <= y <= 10000):
        raise ValueError('Posição inválida.')
    return [prefix + 'enable', prefix + 'mode.' + mode,
            prefix + 'scale.' + str(scale), prefix + 'rotation.' + rotation,
            prefix + f'position.{x},{y}']


def apply(values, modes):
    return subprocess.run(['kscreen-doctor', *arguments(values, modes)],
                          check=True, capture_output=True, text=True, timeout=12)
