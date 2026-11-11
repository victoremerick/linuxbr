#!/usr/bin/python3
"""Apply only the explicitly supported rules of a signed organization profile."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

from organization_policy import fetch


POLICY = Path('/etc/linuxbr/store-optional-sources.json')
STATE = Path('/var/lib/linuxbr/organization-machine')
OWNER = 0
RULES = {'store-snap': 'snap', 'store-brew': 'brew'}
HISTORY_LIMIT = 24
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
REVISION = re.compile(r'[A-Za-z0-9._-]{1,80}')
SHA256 = re.compile(r'[0-9a-f]{64}')


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def fingerprint(profile):
    return hashlib.sha256(canonical({
        field: profile[field] for field in ('organization', 'device', 'revision', 'rules')
    })).hexdigest()


def supported(profile):
    desired, unsupported = {}, []
    for rule in profile['rules']:
        name = rule['id']
        if name in RULES and type(rule['value']) is not bool:
            raise ValueError('Uma regra de fonte da Loja tem valor inválido.')
        if rule['required']:
            if name in RULES:
                desired[name] = rule['value']
            else:
                unsupported.append(name)
    return desired, unsupported


def validated_flags(value):
    if (value is not None and (not isinstance(value, dict)
            or any(key not in RULES.values() or type(flag) is not bool
                   for key, flag in value.items()))):
        raise ValueError('A configuração local das fontes da Loja é inválida.')
    return value


def empty_state():
    return {'schema': 1, 'organization': None, 'device': None, 'revision': None,
            'rules_sha256': None, 'store_file_existed': None, 'managed': {}, 'history': []}


def validated_state(value):
    if (not isinstance(value, dict) or value.keys() != empty_state().keys()
            or type(value['schema']) is not int or value['schema'] != 1):
        raise ValueError('O registro local de políticas é inválido.')
    managed, history = value['managed'], value['history']
    if (not isinstance(managed, dict) or not isinstance(history, list)
            or len(history) > HISTORY_LIMIT):
        raise ValueError('O registro local de políticas é inválido.')
    if managed:
        if (not matches(IDENTIFIER, value['organization']) or not matches(IDENTIFIER, value['device'])
                or not matches(REVISION, value['revision']) or not matches(SHA256, value['rules_sha256'])
                or type(value['store_file_existed']) is not bool):
            raise ValueError('A identidade da política local é inválida.')
    elif any(value[key] is not None for key in
             ('organization', 'device', 'revision', 'rules_sha256', 'store_file_existed')):
        raise ValueError('A identidade da política local é inválida.')
    for key, entry in managed.items():
        if (key not in RULES or not isinstance(entry, dict) or entry.keys() != {'baseline', 'applied'}
                or (entry['baseline'] is not None and type(entry['baseline']) is not bool)
                or type(entry['applied']) is not bool):
            raise ValueError('O registro local contém uma regra inválida.')
    for entry in history:
        if (not isinstance(entry, dict) or entry.keys() != {'action', 'revision', 'organization', 'at'}
                or entry['action'] not in ('apply', 'restore')
                or not matches(REVISION, entry['revision'])
                or not matches(IDENTIFIER, entry['organization'])
                or not isinstance(entry['at'], str) or len(entry['at']) > 40):
            raise ValueError('O histórico local de políticas é inválido.')
    return value


def trusted_directory(path, private=False):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != OWNER
            or info.st_mode & (0o077 if private else 0o022)):
        raise ValueError('O diretório de políticas precisa ser protegido pelo administrador.')


def trusted_file(info, private):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != OWNER or info.st_nlink != 1
            or info.st_mode & (0o077 if private else 0o022)):
        raise ValueError('O arquivo de políticas precisa ser protegido pelo administrador.')


def read_json(path, missing, private=True, limit=32 * 1024):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return missing
    with os.fdopen(descriptor, 'rb') as stream:
        trusted_file(os.fstat(stream.fileno()), private)
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('O arquivo de políticas é grande demais.')
    return json.loads(raw)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def replace_json(path, value, mode):
    descriptor, temporary = tempfile.mkstemp(prefix='.policy-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(canonical(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def remove(path):
    path.unlink(missing_ok=True)
    sync_directory(path.parent)


@contextmanager
def locked():
    trusted_directory(POLICY.parent)
    trusted_directory(STATE.parent)
    try:
        STATE.mkdir(mode=0o700)
        sync_directory(STATE.parent)
    except FileExistsError:
        pass
    trusted_directory(STATE, private=True)
    descriptor = os.open(STATE / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        trusted_file(os.fstat(descriptor), private=True)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def read_flags():
    absent = object()
    value = read_json(POLICY, absent, private=False, limit=4096)
    if value is absent:
        return None
    if value is None:
        raise ValueError('A configuração local das fontes da Loja é inválida.')
    return validated_flags(value)


def read_state():
    return validated_state(read_json(STATE / 'state.json', empty_state()))


def recover_transaction():
    path = STATE / 'pending.json'
    absent = object()
    pending = read_json(path, absent)
    if pending is absent:
        return
    if (not isinstance(pending, dict)
            or pending.keys() != {'schema', 'old_flags', 'new_flags', 'old_state', 'new_state'}
            or type(pending['schema']) is not int or pending['schema'] != 1):
        raise ValueError('O registro de transação de políticas é inválido.')
    old_flags = validated_flags(pending['old_flags'])
    new_flags = validated_flags(pending['new_flags'])
    old_state = validated_state(pending['old_state'])
    new_state = validated_state(pending['new_state'])
    current_flags, current_state = read_flags(), read_state()
    if current_flags == new_flags and current_state in (old_state, new_state):
        if current_state != new_state:
            replace_json(STATE / 'state.json', new_state, 0o600)
    elif current_flags != old_flags or current_state != old_state:
        raise ValueError('Há um conflito local em uma transação de políticas interrompida.')
    remove(path)


def commit(flags, next_flags, state, next_state):
    if flags == next_flags and state == next_state:
        return
    if read_flags() != flags or read_state() != state:
        raise ValueError('A política local mudou durante a operação. Revise os valores atuais.')
    path = STATE / 'pending.json'
    replace_json(path, {'schema': 1, 'old_flags': flags, 'new_flags': next_flags,
                       'old_state': state, 'new_state': next_state}, 0o600)
    if flags != next_flags:
        if next_flags is None:
            remove(POLICY)
        else:
            replace_json(POLICY, next_flags, 0o644)
    replace_json(STATE / 'state.json', next_state, 0o600)
    remove(path)


def local_conflicts(flags, state):
    return sorted(name for name, entry in state['managed'].items()
                  if (flags or {}).get(RULES[name]) is not entry['applied'])


def public_status(flags, state):
    return {'organization': state['organization'], 'revision': state['revision'],
            'rules_sha256': state['rules_sha256'],
            'managed': {name: entry['applied'] for name, entry in state['managed'].items()},
            'conflicts': local_conflicts(flags, state), 'history': state['history']}


def transition(flags, state, desired):
    """Return the new flags and tracked baselines without writing anything."""
    next_flags, managed = dict(flags or {}), {}
    previous = state['managed']
    for name in set(previous) | set(desired):
        key = RULES[name]
        baseline = previous[name]['baseline'] if name in previous else next_flags.get(key)
        target = desired.get(name, baseline)
        if target is None:
            next_flags.pop(key, None)
        else:
            next_flags[key] = target
        if name in desired:
            managed[name] = {'baseline': baseline, 'applied': desired[name]}
    if not next_flags and not (state['store_file_existed'] if previous else flags is not None):
        next_flags = None
    return next_flags, managed


def preview(profile, flags, state):
    desired, unsupported = supported(profile)
    digest = fingerprint(profile)
    conflicts = local_conflicts(flags, state)
    profile_conflict = (bool(state['managed']) and (
        (state['organization'], state['device']) != (profile['organization'], profile['device'])
        or (state['revision'] == profile['revision'] and state['rules_sha256'] != digest)))
    next_flags, _ = transition(flags, state, desired)
    changes = [{'id': name, 'from': (flags or {}).get(RULES[name]),
                'to': (next_flags or {}).get(RULES[name])}
               for name in sorted(set(desired) | set(state['managed']))
               if (flags or {}).get(RULES[name]) != (next_flags or {}).get(RULES[name])]
    return {'revision': profile['revision'], 'organization': profile['organization'],
            'rules_sha256': digest, 'can_apply': not (unsupported or conflicts or profile_conflict),
            'changes': changes, 'unsupported': sorted(unsupported), 'conflicts': conflicts,
            'profile_conflict': profile_conflict}


def history(state, action, organization, revision):
    entry = {'action': action, 'revision': revision, 'organization': organization,
             'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    return [*state['history'], entry][-HISTORY_LIMIT:]


def apply(profile, flags, state, revision, digest):
    decision = preview(profile, flags, state)
    if profile['revision'] != revision or not hmac.compare_digest(decision['rules_sha256'], digest):
        raise ValueError('O perfil mudou depois da revisão. Consulte a política novamente.')
    if decision['unsupported']:
        raise ValueError('O perfil contém regras obrigatórias sem suporte.')
    if not decision['can_apply']:
        raise ValueError('Há um conflito com a política local. Consulte o estado antes de continuar.')
    desired, _ = supported(profile)
    next_flags, managed = transition(flags, state, desired)
    next_state = {**empty_state(), 'history': state['history']}
    if managed:
        next_state.update(organization=profile['organization'], device=profile['device'],
                          revision=revision, rules_sha256=digest, managed=managed,
                          store_file_existed=(state['store_file_existed'] if state['managed']
                                              else flags is not None))
    if next_state != state:
        next_state['history'] = history(state, 'apply', profile['organization'], revision)
    commit(flags, next_flags, state, next_state)
    return public_status(next_flags, next_state)


def restore(flags, state):
    if local_conflicts(flags, state):
        raise ValueError('Os valores gerenciados foram alterados localmente. A reversão foi interrompida.')
    if not state['managed']:
        return public_status(flags, state)
    next_flags, _ = transition(flags, state, {})
    next_state = empty_state()
    next_state['history'] = history(state, 'restore', state['organization'], state['revision'])
    commit(flags, next_flags, state, next_state)
    return public_status(next_flags, next_state)


def command(arguments):
    if os.geteuid() != 0:
        raise ValueError('A operação requer autorização de administrador.')
    if arguments in (['preview'], ['status'], ['restore']):
        action = arguments[0]
    elif (len(arguments) == 3 and arguments[0] == 'apply'
          and matches(REVISION, arguments[1]) and matches(SHA256, arguments[2])):
        action = 'apply'
    else:
        raise ValueError('Use preview, apply REVISÃO HASH, status ou restore.')
    with locked():
        recover_transaction()
        flags, state = read_flags(), read_state()
        if action == 'status':
            return public_status(flags, state)
        if action == 'restore':
            return restore(flags, state)
        profile = fetch()
        if action == 'preview':
            return preview(profile, flags, state)
        return apply(profile, flags, state, arguments[1], arguments[2])


if __name__ == '__main__':
    try:
        print(json.dumps(command(sys.argv[1:]), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as error:
        message = str(error) if type(error) is ValueError else 'Não foi possível acessar a política da organização.'
        print(message, file=sys.stderr)
        sys.exit(1)
