"""Resolve store links to records in catalogs already trusted by the user."""
import re
from urllib.parse import urlsplit


def parse_link(value):
    if not isinstance(value, str) or len(value) > 300 or any(ord(c) < 32 for c in value):
        raise ValueError('Link da Loja inválido.')
    link = urlsplit(value)
    parts = link.path.split('/')
    if (link.scheme != 'linuxbr-store' or link.netloc != 'app' or link.query or link.fragment
            or len(parts) != 3 or parts[0] != ''
            or any(not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,79}', p) for p in parts[1:])):
        raise ValueError('Link da Loja inválido.')
    return tuple(parts[1:])


def find_entry(entries, source, identifier):
    matches = [entry for entry in entries if
               (source == 'builtin' and entry.get('id') == identifier and not entry.get('signed_source'))
               or (source != 'builtin' and entry.get('signed_source_id') == source
                   and entry.get('signed_app') == identifier)]
    if len(matches) > 1:
        raise ValueError('Mais de uma fonte corresponde ao link. Confira as fontes da Loja.')
    return matches[0] if matches else None
