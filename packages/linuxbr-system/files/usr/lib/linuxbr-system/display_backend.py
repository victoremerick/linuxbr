"""Read and apply Plasma display outputs through the KScreen command interface."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

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


def _profile_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'linuxbr/display-profiles.json'


def load_profiles():
    try:
        with _profile_path().open(encoding='utf-8') as stream:
            profiles = json.load(stream)
    except FileNotFoundError:
        profiles = {}
    if not isinstance(profiles, dict):
        raise ValueError('O arquivo de perfis de telas é inválido.')
    return profiles


def save_profiles(profiles):
    destination = _profile_path()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, path = tempfile.mkstemp(prefix='.display-profiles-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(profiles, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, destination)
    finally:
        Path(path).unlink(missing_ok=True)


def output_name(output):
    name = output.get('name')
    if not isinstance(name, str) or not name or len(name) > 150:
        raise ValueError('O conector da tela não foi identificado.')
    return name


def mode_identity(mode):
    size = mode.get('size', {})
    return [size.get('width'), size.get('height'), mode.get('refreshRate', mode.get('refresh'))]


def hardware_identity(output):
    raw_edid = output.get('edid')
    edid = raw_edid if isinstance(raw_edid, dict) else {}
    return [str(output.get(key) or edid.get(key) or '') for key in ('hash', 'vendor', 'model', 'serial')]


def snapshot(displays):
    entries = {}
    for output in displays:
        state = settings(output)
        name = output_name(output)
        if name in entries:
            raise ValueError('Mais de uma tela usa o mesmo identificador.')
        mode = next((item for item in output.get('modes', []) if str(item['id']) == state['mode']), {})
        entries[name] = {**state, 'hardware': hardware_identity(output), 'mode_spec': mode_identity(mode),
                         'priority': int(output.get('priority') or (1 if output.get('primary') else 0))}
    if not any(item['enabled'] for item in entries.values()):
        raise ValueError('O perfil precisa manter pelo menos uma tela em uso.')
    return entries


def profile_arguments(profile, displays):
    current = {output_name(output): output for output in displays}
    if len(current) != len(displays) or not isinstance(profile, dict) or set(profile) != set(current):
        raise ValueError('Conecte os mesmos monitores deste perfil.')
    if not any(item['enabled'] for item in profile.values()):
        raise ValueError('O perfil precisa manter pelo menos uma tela em uso.')

    command = []
    order = []
    for name, item in profile.items():
        output = current[name]
        if item.get('hardware') != hardware_identity(output):
            raise ValueError(f'A identidade da tela {name} mudou.')
        modes = output.get('modes', [])
        identifiers = {str(mode['id']) for mode in modes}
        values = {**item, 'id': int(output['id'])}
        if item['enabled']:
            matching = [mode for mode in modes if mode_identity(mode) == item.get('mode_spec')]
            if not matching:
                raise ValueError(f'A resolução ou frequência salva não está disponível em {name}.')
            values['mode'] = str(next((mode for mode in matching if str(mode['id']) == item['mode']), matching[0])['id'])
            order.append((int(item.get('priority') or 101), name, values['id']))
        command.extend(arguments(values, identifiers))
    for priority, (_, _, identity) in enumerate(sorted(order), 1):
        command.append(f'output.{identity}.priority.{priority}')
    return command


def apply_profile(profile, displays):
    return subprocess.run(['kscreen-doctor', *profile_arguments(profile, displays)],
                          check=True, capture_output=True, text=True, timeout=12)
