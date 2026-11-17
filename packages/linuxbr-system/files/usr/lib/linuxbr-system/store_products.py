"""Relationships reviewed by product identity, independent of search labels."""
from functools import lru_cache

import store_discovery


PRODUCTS = {
    'libreoffice': {
        'name': 'LibreOffice', 'base': ('libreoffice',), 'deb': 'libreoffice',
        'flatpak': 'org.libreoffice.LibreOffice', 'snap': 'libreoffice',
        'winget': 'TheDocumentFoundation.LibreOffice',
    },
    'vlc': {
        'name': 'VLC', 'base': ('vlc',), 'deb': 'vlc', 'flatpak': 'org.videolan.VLC',
        'snap': 'vlc', 'winget': 'VideoLAN.VLC',
    },
    'spotify': {
        'name': 'Spotify', 'base': ('spotify', 'web:open.spotify.com'),
        'flatpak': 'com.spotify.Client', 'snap': 'spotify', 'winget': 'Spotify.Spotify',
    },
    'discord': {
        'name': 'Discord', 'base': ('discord', 'web:discord.com'),
        'flatpak': 'com.discordapp.Discord', 'snap': 'discord', 'winget': 'Discord.Discord',
    },
    'supertux': {
        'name': 'SuperTux', 'base': ('supertux', 'supertux-wine'), 'deb': 'supertux',
        'winget': 'SuperTux.SuperTux',
    },
    'inkscape': {
        'name': 'Inkscape', 'base': ('inkscape',), 'deb': 'inkscape',
        'flatpak': 'org.inkscape.Inkscape', 'snap': 'inkscape', 'brew': 'inkscape',
        'winget': 'Inkscape.Inkscape',
    },
}
PROVIDERS = {'deb': 'Debian', 'flatpak': 'Flathub', 'snap': 'Snap',
             'brew': 'Homebrew', 'winget': 'WinGet'}
FORMATS = {'deb': 'DEB', 'flatpak': 'Flatpak', 'snap': 'Snap',
           'brew': 'Homebrew', 'winget': 'Windows'}
REVIEWED = {
    'libreoffice': ('MPL 2.0 e licenças de componentes', 'Português (Brasil) com pacote de idioma',
                    'Aplicativo de desktop', 'Edição de arquivos locais', 'ODF, DOCX, XLSX, PPTX, exportação PDF'),
    'vlc': ('GPL 2.0 ou posterior', 'Português disponível', 'Decodificação por software ou GPU',
            'Reprodução de arquivos locais', 'MP4, MKV, MP3, FLAC e outros'),
}


def comparison(item, metadata):
    verified = REVIEWED.get(key(item)) if item['kind'] == 'linux' else None
    license_name, language, requirements, offline, formats = verified or ('', '', '', '', '')
    if item['kind'] == 'web':
        requirements = 'Chromium e conexão com o serviço'
        offline = 'Depende do serviço'
    elif item['kind'] == 'windows':
        requirements = 'Ver requisitos do fornecedor e testes com Wine'
    return tuple(value or 'A consultar na fonte' for value in (
        item.get('license') or metadata.get('license') or license_name,
        language, requirements, offline, formats,
    ))


@lru_cache(maxsize=1)
def discovered():
    keys = {(provider, spec[manager]) for spec in PRODUCTS.values()
            for manager, provider in PROVIDERS.items() if manager in spec}
    return {(row[1], row[2]): store_discovery.entry(row)
            for row in store_discovery.index() if (row[1], row[2]) in keys}


def key(item):
    if not item:
        return None
    optional = item.get('optional_target') or {}
    origin = item.get('discovery_provider') or PROVIDERS.get(optional.get('manager'))
    identity = item.get('discovery_id') or optional.get('target')
    for product, spec in PRODUCTS.items():
        if item['id'] in spec['base']:
            return product
        for manager, provider in PROVIDERS.items():
            identifier = spec.get(manager)
            if identifier and ((origin, identity) == (provider, identifier)
                               or (manager == 'deb' and item.get('repository_package') == identifier)
                               or (manager == 'flatpak' and item.get('flatpak_id') == identifier)):
                return product
    return None


def variants(product, entries):
    spec = PRODUCTS[product]
    base = next((item for item in entries if item['id'] == product), None)
    for manager, provider in PROVIDERS.items():
        identifier = spec.get(manager)
        if identifier:
            source = discovered().get((provider, identifier))
            if not source and base and manager in ('deb', 'flatpak'):
                reference = ('https://packages.debian.org/trixie/' if manager == 'deb'
                             else 'https://flathub.org/apps/') + identifier
                source = dict(base, source=reference, discovery_provider=provider,
                              discovery_id=identifier)
            if source:
                yield FORMATS[manager], source
    for item in entries:
        if item['id'] in spec['base'] and item['kind'] != 'linux':
            yield 'Web' if item['kind'] == 'web' else 'Windows', item
