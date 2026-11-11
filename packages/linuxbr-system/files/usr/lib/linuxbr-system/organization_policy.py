#!/usr/bin/python3
"""Fetch an authenticated device profile and prepare optional account defaults."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile


MACHINE_RULES = {'store-snap', 'store-brew'}


def validate(profile, config, nonce, now):
    if (not isinstance(profile, dict) or profile.get('schema') != 1
            or profile.get('kind') != 'organization-policy'
            or profile.get('organization') != config['organization']
            or profile.get('device') != config['device'] or profile.get('nonce') != nonce):
        raise ValueError('O perfil não corresponde a este computador e a esta solicitação.')
    if not isinstance(profile.get('revision'), str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', profile['revision']):
        raise ValueError('Revisão do perfil inválida.')
    try:
        issued = datetime.fromisoformat(profile['issued_at'])
        expires = datetime.fromisoformat(profile['expires_at'])
        if issued.tzinfo is None or expires.tzinfo is None:
            raise ValueError()
        if not issued <= now < expires or expires - issued > timedelta(minutes=2):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise ValueError('Validade do perfil inválida.') from None
    rules = profile.get('rules')
    if not isinstance(rules, list) or len(rules) > 30:
        raise ValueError('Lista de regras inválida.')
    seen = set()
    for rule in rules:
        if (not isinstance(rule, dict) or set(rule) != {'id', 'required', 'value'}
                or not isinstance(rule['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,60}', rule['id'])
                or type(rule['required']) is not bool or rule['id'] in seen):
            raise ValueError('Regra de perfil inválida ou duplicada.')
        seen.add(rule['id'])
        if rule['id'] == 'work-folder':
            folder = rule['value']
            if (not isinstance(folder, str) or not 1 <= len(folder) <= 80
                    or folder[0] == '.' or folder.strip() != folder
                    or any(not (c.isalnum() or c in ' _-') for c in folder)):
                raise ValueError('Nome da pasta de trabalho inválido.')
        if rule['id'] == 'store-search':
            terms = rule['value']
            if (not isinstance(terms, list) or not 1 <= len(terms) <= 12
                    or any(not isinstance(term, str) or not 1 <= len(term) <= 80
                           or any(ord(c) < 32 for c in term) for term in terms)):
                raise ValueError('Sugestões de aplicativos inválidas.')
        if rule['id'] in MACHINE_RULES and type(rule['value']) is not bool:
            raise ValueError('A permissão de fonte deve ser ativada ou desativada.')
    return profile


def fetch():
    from update_waves import read_config, request, decode_manifest
    if os.geteuid() != 0:
        raise ValueError('A consulta requer autorização local.')
    config = read_config()
    if not config or not config.get('endpoint'):
        raise ValueError('O serviço da organização ainda não foi cadastrado pela TI.')
    nonce = secrets.token_hex(32)
    profile = decode_manifest(request(config, 'POST', '/v1/policy', {'nonce': nonce}))
    return validate(profile, config, nonce, datetime.now(timezone.utc))


def apply_preferences(profile, home, state, *, completed_machine=None):
    """Use only account-scoped actions; mandatory controls must be implemented first."""
    validate(profile, profile, profile['nonce'], datetime.now(timezone.utc))
    completed_machine = completed_machine or {}
    if any(rule['required'] and (rule['id'] not in MACHINE_RULES
            or completed_machine.get(rule['id']) is not rule['value']) for rule in profile['rules']):
        raise ValueError('O perfil contém controles obrigatórios sem implementação nesta etapa.')
    home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    results = []
    try:
        for rule in profile['rules']:
            name = rule['id']
            if name in MACHINE_RULES and rule['required']:
                results.append({'id': name, 'state': 'Gerenciado pela organização'})
            elif name == 'work-folder':
                folder = rule['value']
                try:
                    os.mkdir(folder, mode=0o700, dir_fd=home_fd)
                except FileExistsError:
                    pass
                descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home_fd)
                try:
                    info = os.fstat(descriptor)
                    if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode):
                        raise ValueError('A pasta de trabalho pertence a outra conta.')
                finally:
                    os.close(descriptor)
                results.append({'id': name, 'state': 'Concluído'})
            elif name == 'store-search':
                results.append({'id': name, 'state': 'Ação necessária', 'terms': rule['value']})
            else:
                results.append({'id': name, 'state': 'Regra opcional sem suporte'})
    finally:
        os.close(home_fd)
    state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.organization-', dir=state.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump({'schema': 1, 'organization': profile['organization'],
                       'revision': profile['revision'], 'results': results}, output, ensure_ascii=False)
        os.replace(temporary, state)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return results


if __name__ == '__main__':
    try:
        print(json.dumps(fetch(), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError):
        print('Não foi possível consultar um perfil válido da organização.', file=sys.stderr)
        sys.exit(1)
