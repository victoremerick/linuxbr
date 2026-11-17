"""Search the discovery snapshot bundled with the system package."""
from functools import lru_cache
from datetime import date
import gzip
import json
from pathlib import Path

from store_backend import folded


CATALOG = Path('/usr/share/linuxbr/store/discovery.json.gz')
CATEGORY = 'Catálogo ampliado'
LIMIT_PER_KIND = 24
LINUX_ICONS = {
    'Debian': 'package-x-generic',
    'Flathub': 'system-software-install',
    'Snap': 'application-x-snap',
    'Homebrew': 'utilities-terminal',
}

def snapshot_date():
    try:
        info = json.loads(CATALOG.with_name('discovery-info.json').read_text(encoding='utf-8'))
        reviewed = date.fromisoformat(info['reviewed'])
        return reviewed.strftime('%d/%m/%Y') if index() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


@lru_cache(maxsize=1)
def index():
    try:
        with gzip.open(CATALOG, 'rt', encoding='utf-8') as source:
            return [
                (kind, provider, identity, name, category, reference,
                 folded(f'{name} {identity} {provider} {category}'), folded(name))
                for kind, provider, identity, name, category, reference in json.load(source)
            ]
    except (OSError, ValueError):
        return []


@lru_cache(maxsize=48)
def search(query, kind=''):
    value = folded(query.strip())
    if not 2 <= len(value) <= 100 or not any(char.isalnum() for char in value):
        return ()
    words = value.split()
    groups = {}
    for row in index():
        platform, _, _, _, _, _, searchable, _ = row
        if (not kind or platform == kind) and all(word in searchable for word in words):
            groups.setdefault(platform, []).append(row)

    results = []
    for matches in groups.values():
        matches.sort(key=lambda row: (row[7] != value, not row[7].startswith(value), row[7]))
        results.extend(entry(row) for row in matches[:LIMIT_PER_KIND])
    return tuple(results)


def entry(row):
    platform, provider, identity, name, category, reference, _, _ = row
    description = {
        'linux': 'Consulte o pacote na fonte de origem.',
        'windows': 'Programa Windows encontrado no índice WinGet.',
        'web': 'Use o serviço em uma janela própria do Chromium.',
    }[platform]
    note = {
        'linux': 'Pesquise também em Fontes configuradas para instalar com um gerenciador do sistema.',
        'windows': 'Consulte o manifesto para identificar o fornecedor. A execução pelo Wine ainda não foi testada.',
        'web': 'O acesso exige internet. Login, assinatura e recursos variam por serviço.',
    }[platform]
    item = dict(id=f'discovery:{provider}:{identity}', name=name,
                kind=platform, category=CATEGORY, discovery_provider=provider,
                discovery_id=identity, description=description, source=reference, note=note,
                keywords=f'{identity} {provider} {category}')
    if platform == 'web':
        item['url'] = reference
    elif platform == 'linux':
        item['icon'] = LINUX_ICONS[provider]
    return item


def merge(entries, discovery_entries):
    available = set()
    for item in entries:
        if item.get('repository_package'):
            available.add(('Debian', item['repository_package']))
        if item.get('flatpak_id'):
            available.add(('Flathub', item['flatpak_id']))
        target = item.get('optional_target')
        if target:
            provider = {'snap': 'Snap', 'brew': 'Homebrew'}.get(target['manager'])
            available.add((provider, target['target']))
    return entries + [item for item in discovery_entries
                      if (item['discovery_provider'], item['discovery_id']) not in available]
