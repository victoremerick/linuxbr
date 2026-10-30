"""Fetch public site favicons into a bounded local cache, independently of logins."""
import argparse
import fcntl
import http.client
import ipaddress
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from PyQt6.QtCore import QBuffer, QByteArray, QCoreApplication, QIODevice
from PyQt6.QtGui import QImageReader

import webapps_backend as backend

MAX_IMAGE = 1024 * 1024
MAX_PAGE = 256 * 1024
_queued = {}


def cache_path(url):
    canonical = backend.normalize_offer({'url': url})['url']
    return backend.root() / 'icons' / (backend.app_id(canonical) + '.png')


def cached(url):
    path = cache_path(url)
    return path if path.is_file() and not path.is_symlink() else None


def launcher_icon(url):
    path = cache_path(url)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = Path('/usr/share/linuxbr/webapps/icon.png')
        if source.is_file():
            try:
                with path.open('xb') as stream: stream.write(source.read_bytes())
            except FileExistsError:
                pass
    return path if path.is_file() and not path.is_symlink() else Path('/usr/share/linuxbr/webapps/icon.png')


def request_refresh(url):
    canonical = backend.normalize_offer({'url': url})['url']
    now = time.monotonic()
    if now - _queued.get(canonical, -100) < 10: return
    path = cache_path(canonical)
    marker = path.with_suffix('.attempt')
    try:
        if path.is_file() and path.with_suffix('.ready').is_file() and time.time() - path.stat().st_mtime < 7 * 86400: return
        if marker.is_file() and time.time() - marker.stat().st_mtime < 3600: return
        _queued[canonical] = now
        subprocess.Popen(['/usr/bin/python3', str(Path(__file__).resolve()), '--url', canonical],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def public_url(url):
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url) or '\\' in url:
        raise ValueError('Endereço do ícone inválido.')
    parts = urlsplit(url)
    if (parts.scheme != 'https' or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.port not in (None, 443)):
        raise ValueError('O ícone precisa usar HTTPS público.')
    host = parts.hostname.encode('idna').decode('ascii')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
        raise ValueError('O ícone precisa estar em um servidor público.')
    target = quote(parts.path or '/', safe='/%:@!$&\'()*+,;=-._~')
    if parts.query: target += '?' + quote(parts.query, safe='/%?:@!$&\'()*+,;=-._~')
    return host, addresses[0][4][0], target


class PublicHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=4, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Pin the public address checked above; a second DNS answer is not used.
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close(); raise


def fetch(url, limit):
    for _ in range(4):
        host, address, target = public_url(url)
        connection = PublicHTTPS(host, address)
        try:
            connection.request('GET', target, headers={'User-Agent': 'LinuxBR-Webapps/1.0',
                'Accept': 'image/*,text/html;q=0.8', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location: raise ValueError('Redirecionamento sem destino.')
                url = urljoin(url, location); continue
            if response.status != 200: raise ValueError('Ícone indisponível.')
            length = response.getheader('Content-Length')
            if length and int(length) > limit: raise ValueError('Arquivo muito grande.')
            data = response.read(limit + 1)
            if len(data) > limit: raise ValueError('Arquivo muito grande.')
            return data, url
        finally:
            connection.close()
    raise ValueError('Redirecionamentos demais.')


class Icons(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        rel = (values.get('rel') or '').lower().split()
        if tag == 'link' and ('icon' in rel or 'apple-touch-icon' in rel) and values.get('href'):
            if len(self.urls) < 8: self.urls.append(values['href'])


def store_image(data, destination):
    buffer = QBuffer(); buffer.setData(QByteArray(data)); buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    if bytes(reader.format()).lower() not in (b'png', b'ico', b'jpeg', b'webp', b'gif', b'bmp'):
        raise ValueError('Formato de ícone não aceito.')
    size = reader.size()
    if not size.isValid() or size.width() > 2048 or size.height() > 2048:
        raise ValueError('Dimensões do ícone inválidas.')
    image = reader.read()
    if image.isNull(): raise ValueError('Ícone inválido.')
    if image.width() > 256 or image.height() > 256:
        from PyQt6.QtCore import Qt
        image = image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    descriptor, temporary = tempfile.mkstemp(prefix='.favicon-', dir=destination.parent)
    os.close(descriptor)
    try:
        if not image.save(temporary, 'PNG'): raise ValueError('Não foi possível salvar o ícone.')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def refresh(url):
    if os.geteuid() == 0: return
    canonical = backend.normalize_offer({'url': url})['url']
    destination = cache_path(canonical); destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = destination.with_suffix('.lock')
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return
        attempt = destination.with_suffix('.attempt')
        if attempt.is_file() and time.time() - attempt.stat().st_mtime < 3600: return
        backend.atomic_write(attempt, str(time.time()))
        candidates = []
        try:
            document, base = fetch(canonical, MAX_PAGE)
            parser = Icons(); parser.feed(document.decode('utf-8', errors='replace'))
            source_host = urlsplit(canonical).hostname.removeprefix('www.')
            final_host = urlsplit(base).hostname.removeprefix('www.')
            # A redirected sign-in provider must not replace the app's identity.
            if source_host == final_host:
                candidates.extend(urljoin(base, value) for value in reversed(parser.urls))
        except (OSError, ValueError, http.client.HTTPException):
            pass
        origin = urlsplit(canonical)
        candidates.append(urlunsplit((origin.scheme, origin.netloc, '/favicon.ico', '', '')))
        for candidate in dict.fromkeys(candidates):
            try:
                data, _ = fetch(candidate, MAX_IMAGE); store_image(data, destination)
                backend.atomic_write(destination.with_suffix('.ready'), str(time.time()))
                # Refresh menu caches without changing records, names or visibility.
                paths = [backend.apps_dir()/f'linuxbr-webapp-site-{backend.app_id(canonical)}.desktop']
                paths.extend(backend.apps_dir()/f'linuxbr-webapp-{item["id"]}.desktop'
                             for item in backend.sessions(canonical))
                for path in paths:
                    if path.is_file() and not path.is_symlink():
                        try: os.utime(path, None, follow_symlinks=False)
                        except OSError: pass
                return
            except (OSError, ValueError, http.client.HTTPException):
                continue


if __name__ == '__main__':
    app = QCoreApplication(sys.argv)
    parser = argparse.ArgumentParser(); parser.add_argument('--url', required=True)
    args = parser.parse_args()
    try: refresh(args.url)
    except (OSError, ValueError, http.client.HTTPException): sys.exit(1)
