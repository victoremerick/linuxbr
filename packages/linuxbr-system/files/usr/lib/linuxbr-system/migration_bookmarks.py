"""Prepare a browser bookmark export for review and import."""
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit


MAX_FILE = 8 * 1024 * 1024
MAX_LINKS = 5000


def web_link(value):
    if not isinstance(value, str) or len(value) > 4096 or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme in ('https', 'http') and parts.hostname and parts.username is None
    except ValueError:
        return False


class Bookmarks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}
        self.current = None
        self.title = ''

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        href = dict(attrs).get('href')
        self.current = href if web_link(href) else None
        self.title = ''

    def handle_data(self, data):
        if self.current and len(self.title) < 200:
            self.title += data[:200 - len(self.title)]

    def handle_endtag(self, tag):
        if tag == 'a' and self.current:
            self.links.setdefault(self.current, ' '.join(self.title.split()) or self.current)
            self.current = None
            if len(self.links) > MAX_LINKS:
                raise ValueError('Selecione uma lista com até 5.000 favoritos.')


def load_bookmarks(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError('O arquivo de favoritos excede o tamanho permitido.')
    parser = Bookmarks()
    parser.feed(data.decode('utf-8-sig'))
    parser.close()
    if not parser.links:
        raise ValueError('O arquivo não contém favoritos HTTP ou HTTPS.')
    return parser.links


def browser_file(links):
    rows = ['<!DOCTYPE NETSCAPE-Bookmark-file-1>',
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            '<TITLE>Favoritos importados</TITLE>', '<H1>Favoritos importados</H1>', '<DL><p>']
    rows.extend(f'    <DT><A HREF="{escape(url, quote=True)}">{escape(title)}</A>'
                for url, title in links.items())
    return '\n'.join([*rows, '</DL><p>', ''])


def collect_links(rows):
    links = {}
    for url, title in rows:
        if web_link(url):
            label = ' '.join(title.split())[:200] if isinstance(title, str) else ''
            links.setdefault(url, label or url)
            if len(links) > MAX_LINKS:
                raise ValueError('Selecione um perfil com até 5.000 favoritos.')
    if not links:
        raise ValueError('O perfil não contém favoritos HTTP ou HTTPS.')
    return links


def chromium_bookmarks(path):
    with path.open('rb') as handle:
        raw = handle.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise ValueError('O arquivo de favoritos excede o tamanho permitido.')
    try:
        roots = json.loads(raw).get('roots')
        if not isinstance(roots, dict):
            raise ValueError()
    except (ValueError, AttributeError, RecursionError):
        raise ValueError('O arquivo Bookmarks não contém um perfil do Chrome ou Edge.') from None
    queue = list(roots.values())
    rows = []
    while queue:
        node = queue.pop()
        if not isinstance(node, dict):
            continue
        if node.get('type') == 'url':
            rows.append((node.get('url'), node.get('name')))
        children = node.get('children')
        if isinstance(children, list):
            queue.extend(reversed(children))
    return collect_links(rows)


def firefox_bookmarks(path):
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('O banco de favoritos do Firefox excede 512 MiB.')
    if path.with_name(path.name + '-wal').exists():
        raise ValueError('Feche o Firefox antes de copiar o arquivo places.sqlite ou use uma exportação HTML.')
    try:
        connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            connection.execute('PRAGMA trusted_schema=OFF')
            rows = connection.execute(
                'SELECT p.url, b.title FROM moz_bookmarks AS b '
                'JOIN moz_places AS p ON p.id = b.fk WHERE b.type = 1 ORDER BY b.id LIMIT ?',
                (MAX_LINKS * 2,)).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        raise ValueError('O banco de favoritos do Firefox não pôde ser lido.') from None
    return collect_links(rows)


def load_bookmark_source(filename):
    path = Path(filename).expanduser().absolute()
    if path.name == 'Bookmarks':
        return chromium_bookmarks(path)
    if path.name == 'places.sqlite':
        return firefox_bookmarks(path)
    return load_bookmarks(path)
