"""Prepare a browser bookmark export for review and import."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
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
