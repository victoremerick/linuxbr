"""Portable application selections resolved against enabled sources."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

import store_optional as optional


MAX_BYTES = 256 * 1024
MAX_APPS = 200
REF = re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
REMOTE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}')
FLATPAK_FIELDS = {'ref', 'scope', 'origin', 'origin_sha256', 'commit'}
COMMON_FIELDS = {'manager', 'ref', 'scope', 'origin', 'origin_sha256', 'version'}
MANUAL = {
    'deb': ('DEB do sistema', 'system', 'Confira o pacote e sua origem nas fontes APT da Loja.'),
    'web': ('Aplicativo web', 'user', 'Localize o serviço no catálogo e crie os perfis desejados.'),
    'windows': ('Wine', 'user', 'Localize o programa na Loja e confira o instalador oficial e a compatibilidade.'),
}
EXTRA_FIELDS = {'flatpak': {'commit'}, 'snap': {'confinement', 'channel', 'revision'}, 'brew': set(),
                **{manager: {'name'} for manager in MANUAL}}
INSTALLABLE = 'Pode consultar e instalar'


def public_url(value):
    if not isinstance(value, str) or len(value) > 500 or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and bool(url.hostname) and url.username is None
                and url.password is None and not url.query and not url.fragment)
    except ValueError:
        return False


def flatpak(scope, *args):
    try:
        result = subprocess.run(['/usr/bin/flatpak', '--' + scope, *args],
                                capture_output=True, text=True, errors='replace', timeout=8)
        return result.stdout if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def remotes(scope):
    result = {}
    for line in flatpak(scope, 'remotes', '--columns=name,url,options').splitlines():
        fields = line.split('\t')
        if len(fields) < 2:
            continue
        name, url = fields[:2]
        options = {item.strip() for item in fields[2].split(',')} if len(fields) > 2 else set()
        if (REMOTE.fullmatch(name) and public_url(url) and
                not options.intersection({'no-gpg-verify', 'disabled'})):
            result[name] = url
    return result


def installed(scope):
    for line in flatpak(scope, 'list', '--app', '--columns=application,arch,branch,origin,active').splitlines():
        fields = line.split('\t')
        if len(fields) != 5:
            continue
        ref = '/'.join(fields[:3])
        if REF.fullmatch(ref):
            yield ref, fields[3], fields[4]


def exportable():
    rows = []
    for scope in ('user', 'system'):
        origins = remotes(scope)
        versions = {}
        for line in flatpak(scope, 'list', '--app', '--columns=application,arch,branch,version').splitlines():
            fields = line.split('\t')
            if len(fields) == 4:
                versions['/'.join(fields[:3])] = version_text(fields[3])
        for ref, origin, commit in installed(scope):
            if origin in origins:
                rows.append(dict(manager='flatpak', ref=ref, scope=scope, origin=origin,
                                 origin_sha256=fingerprint(origins[origin]),
                                 version=versions.get(ref, ''),
                                 commit=commit if re.fullmatch(r'[a-f0-9]{64}', commit) else ''))
    entries, _ = optional.inventory()
    for item in entries:
        target = item['optional_target']
        manager = target['manager']
        origin, scope, source = optional.PROVIDERS[manager]
        row = dict(manager=manager, ref=target['target'], scope=scope, origin=origin,
                   origin_sha256=fingerprint(source), version=version_text(item['version']))
        if manager == 'snap':
            row.update(confinement=target['confinement'], channel=version_text(item['channel']),
                       revision=version_text(item['revision']))
        rows.append(row)
    rows.extend(manual_entries())
    return sorted(rows, key=lambda row: (row['ref'], row['manager'], row['scope']))


def version_text(value):
    return ''.join(character for character in value if character.isprintable())[:160]


def application_name(value):
    if not isinstance(value, str):
        return ''
    name = ' '.join(value.split())
    if (0 < len(name) <= 100 and name[0].isalnum() and all(
            char.isalnum() or char in " ._+-&()[]!®™–—'’" for char in name)):
        return name
    return ''


def manual_entries():
    from store_backend import desktop_applications, package_targets, query_local
    from webapps_backend import installed as webapps, service_for
    from windows_runner import programs

    rows = {}

    def add(manager, name, *, package='', version=''):
        name = application_name(name)
        if not name:
            return
        origin, scope, _ = MANUAL[manager]
        ref = package or fingerprint(name.casefold())[:32]
        row = dict(manager=manager, ref=ref, name=name, scope=scope, origin=origin,
                   origin_sha256='', version=version_text(version))
        if valid_row(row, 2):
            rows[manager, ref] = row

    for item in desktop_applications():
        if item.get('flatpak_id') or item.get('provider_hint') == 'snap':
            continue
        for target in package_targets(item):
            if target['manager'] == 'deb' and target['installed']:
                package = target['target']
                if ('deb', package) not in rows:
                    version = query_local(['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', package])
                    add('deb', item['name'], package=package, version=version)
    for item in webapps():
        try:
            service = service_for(item['url'])
        except (OSError, ValueError, KeyError):
            service = None
        add('web', (service or item)['name'])
    for item in programs():
        add('windows', item['name'])
    return list(rows.values())


def valid_row(row, schema):
    if not isinstance(row, dict) or any(not isinstance(item, str) for item in row.values()):
        return False
    manager = row.get('manager') if schema == 2 else 'flatpak'
    if manager not in EXTRA_FIELDS:
        return False
    fields = FLATPAK_FIELDS if schema == 1 else COMMON_FIELDS | EXTRA_FIELDS[manager]
    if row.keys() != fields or any(version_text(row[key]) != row[key]
                                  for key in fields.intersection({'version', 'channel', 'revision'})):
        return False
    if manager == 'flatpak':
        return (row['scope'] in ('user', 'system') and len(row['ref']) <= 300 and REF.fullmatch(row['ref'])
                and REMOTE.fullmatch(row['origin']) and re.fullmatch(r'[a-f0-9]{64}', row['origin_sha256'])
                and re.fullmatch(r'(?:[a-f0-9]{64})?', row['commit']))
    if manager in MANUAL:
        from store_transactions import DEB_NAME

        origin, scope, _ = MANUAL[manager]
        name = row['name']
        ref = row['ref']
        identifier_ok = len(ref) <= 160 and DEB_NAME.fullmatch(ref) if manager == 'deb' else (
            ref == fingerprint(name.casefold())[:32])
        return (row['scope'] == scope and row['origin'] == origin and not row['origin_sha256']
                and bool(name) and name == application_name(name) and identifier_ok)
    origin, scope, source = optional.PROVIDERS[manager]
    return (row['scope'] == scope and row['origin'] == origin and row['origin_sha256'] == fingerprint(source)
            and optional.NAMES[manager].fullmatch(row['ref'])
            and (manager != 'snap' or row['confinement'] in ('strict', 'classic')))


def load(path):
    with Path(path).open('rb') as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('A lista excede o tamanho permitido.')
    value = json.loads(content)
    schema = value.get('schema') if isinstance(value, dict) else None
    if type(schema) is not int or schema not in (1, 2) or (
            schema == 1 and (value.keys() != {'schema', 'manager', 'apps'} or value['manager'] != 'flatpak')) or (
            schema == 2 and value.keys() != {'schema', 'apps'}):
        raise ValueError('Formato de lista de aplicativos desconhecido.')
    rows = value.get('apps')
    if not isinstance(rows, list) or len(rows) > MAX_APPS:
        raise ValueError('A lista deve conter até 200 aplicativos.')
    unique = set()
    for row in rows:
        if not valid_row(row, schema):
            raise ValueError('A lista contém um aplicativo inválido.')
        key = row.get('manager', 'flatpak'), row['scope'], row['ref']
        if key in unique:
            raise ValueError('A lista contém aplicativos duplicados no mesmo escopo.')
        unique.add(key)
    return rows


def fingerprint(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest() if url else ''


def review(rows):
    scopes = {row['scope'] for row in rows if row.get('manager', 'flatpak') == 'flatpak'}
    origins = {scope: remotes(scope) for scope in scopes}
    existing = {scope: {ref for ref, _, _ in installed(scope)} for scope in scopes}
    native = {}
    for manager in {row.get('manager') for row in rows} & optional.PROVIDERS.keys():
        if not optional.enabled(manager):
            native[manager] = 'Ação manual — habilite a fonte em Fontes se a organização permitir.'
        else:
            try:
                native[manager] = {item['optional_target']['target'] for item in optional.provider_inventory(manager)}
            except (OSError, ValueError) as error:
                native[manager] = 'Ação manual — ' + str(error)

    def state(row):
        manager = row.get('manager', 'flatpak')
        scope, ref = row['scope'], row['ref']
        if manager in MANUAL:
            return 'Ação manual — ' + MANUAL[manager][2]
        if manager in native:
            provider = native[manager]
            if isinstance(provider, str):
                return provider
            if ref in provider:
                return 'Já instalado'
            if manager == 'snap' and row['channel'] not in ('stable', 'latest/stable'):
                return 'Ação manual — o canal registrado exige escolha pelo snapd.'
            try:
                entry = optional.available_entry(manager, ref)
                state = f"{INSTALLABLE} · versão disponível {entry['version']}"
                if manager == 'snap':
                    confinement = entry['optional_target']['confinement']
                    if confinement != row['confinement']:
                        return 'Ação manual — o confinamento mudou. Revise o aplicativo na Loja.'
                    confinement_note = optional.require_snap_support()
                    if confinement_note and confinement == 'strict':
                        state += '\n' + confinement_note
                return state
            except (OSError, ValueError) as error:
                return 'Ação manual — ' + str(error)
        if ref in existing[scope]:
            return 'Já instalado'
        if fingerprint(origins[scope].get(row['origin'])) != row['origin_sha256']:
            return 'Origem não corresponde a uma fonte habilitada'
        return INSTALLABLE

    # Each optional application is looked up by its exact identifier. Keep the
    # review responsive while limiting concurrent requests to the same stores.
    if not native:
        return [(row, state(row)) for row in rows]
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(zip(rows, pool.map(state, rows)))


def install_request(row, *, classic_confirmed=False):
    from store_transactions import checked_request

    manager = row.get('manager', 'flatpak')
    if not valid_row(row, 2 if 'manager' in row else 1):
        raise ValueError('A lista contém um aplicativo inválido.')
    if manager in MANUAL:
        raise ValueError('Este aplicativo exige uma escolha manual na Loja.')
    if manager == 'snap' and row['channel'] not in ('stable', 'latest/stable'):
        raise ValueError('O canal Snap registrado precisa ser reinstalado manualmente.')
    ref = row['ref']
    values = dict(manager=manager, action='install', scope=row['scope'], target=ref,
                  origin=row['origin'], name=ref.split('/')[0])
    if manager == 'flatpak':
        values['expected_origin_sha256'] = row['origin_sha256']
    elif manager == 'snap':
        values.update(confinement=row['confinement'], classic_confirmed=classic_confirmed)
    return checked_request(values)
