"""Portable web app launchers, separate from Chromium profile data."""
import base64
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit

import webapps_backend as backend


SCHEMA = 'linuxbr-webapp-shortcuts-2'
LIMIT = 16 * 1024 * 1024
ICON_LIMIT = 48 * 1024
MAX_SHORTCUTS = 200


def public_start(address):
    url = backend.clean_url(address)
    service = backend.service_for(url)
    return backend.clean_url(service['url']) if service else 'https://' + urlsplit(url).hostname + '/'


def raster_icon(data):
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PyQt6.QtGui import QImage, QImageReader, QPainter

    if not data or len(data) > ICON_LIMIT:
        raise ValueError('O ícone do atalho excede o tamanho permitido.')
    source = QBuffer()
    source.setData(QByteArray(data))
    source.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(source, b'png')
    size = reader.size()
    if not size.isValid() or size.width() > 256 or size.height() > 256:
        raise ValueError('Use um ícone PNG de até 256 × 256 pixels.')
    image = reader.read()
    if image.isNull():
        raise ValueError('Ícone PNG inválido.')
    image = image.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    flattened = QImage(image.size(), QImage.Format.Format_ARGB32)
    flattened.fill(Qt.GlobalColor.transparent)
    with QPainter(flattened) as painter:
        painter.drawImage(0, 0, image)
    result = QBuffer()
    result.open(QIODevice.OpenModeFlag.WriteOnly)
    if not flattened.save(result, 'PNG') or result.size() > ICON_LIMIT:
        raise ValueError('Não foi possível preparar o ícone do atalho.')
    return bytes(result.data())


def archive_icon(url):
    from webapp_icons import cached

    icon = cached(url)
    if not icon:
        return ''
    try:
        with icon.open('rb') as source:
            data = source.read(ICON_LIMIT + 1)
        return base64.b64encode(raster_icon(data)).decode('ascii')
    except (OSError, ValueError):
        # The destination can retrieve a fresh favicon or use the default.
        return ''


def export_file(path):
    items = backend.installed()
    if len(items) > MAX_SHORTCUTS:
        raise ValueError('O arquivo aceita até 200 atalhos.')
    rows = []
    icons = {}
    for item in items:
        origin, label = public_start(item['url']), item['session']
        options = backend.profile_options(item['id'])
        preferred = backend.preferred_profile(item['url']) == item['id']
        rows.append(dict(url=origin, name=item['name'], session=label, options=options, preferred=preferred))
        if origin not in icons and (icon := archive_icon(item['url'])):
            icons[origin] = icon
    payload = json.dumps(dict(schema=SCHEMA, shortcuts=rows, icons=icons), ensure_ascii=False) + '\n'
    if len(payload.encode('utf-8')) > LIMIT:
        raise ValueError('O arquivo de atalhos excede o tamanho permitido.')
    backend.atomic_write(Path(path), payload)


def read_file(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError('Escolha um arquivo regular de atalhos.')
        raw = source.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('O arquivo de atalhos é muito grande.')
    return json.loads(raw), len(raw)


def load_records(document):
    if set(document) != {'schema', 'shortcuts', 'icons'}:
        raise ValueError('Arquivo de atalhos inválido.')
    rows, icons = document['shortcuts'], document['icons']
    if not isinstance(rows, list) or len(rows) > MAX_SHORTCUTS or not isinstance(icons, dict) or len(icons) > MAX_SHORTCUTS:
        raise ValueError('Lista de atalhos inválida.')
    icon_data = {}
    for url, data in icons.items():
        if (url != public_start(url) or not isinstance(data, str)
                or len(data) > ((ICON_LIMIT + 2) // 3) * 4):
            raise ValueError('Ícone de atalho inválido.')
        icon_data[url] = raster_icon(base64.b64decode(data, validate=True))
    seen = set()
    valid = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'url', 'name', 'session', 'options', 'preferred'}:
            raise ValueError('Atalho inválido.')
        options = row['options']
        if (not isinstance(options, dict) or set(options) != {'external_links', 'session_start'}
                or options['external_links'] not in ('profile', 'default-browser')
                or type(options['session_start']) is not bool or type(row['preferred']) is not bool):
            raise ValueError('Preferências de atalho inválidas.')
        url, name, session = public_start(row['url']), backend.clean_name(row['name']), backend.clean_name(row['session'])
        key = (url, session.casefold())
        if key not in seen:
            seen.add(key)
            valid.append(dict(url=url, name=name, session=session, options=options,
                              preferred=row['preferred'], icon=icon_data.get(url)))
    return valid


def pending(rows):
    installed = backend.installed(include_hidden=True)
    sites = {public_start(item['url']) for item in installed}
    profiles = {(public_start(item['url']), item['session'].casefold()) for item in installed}
    for row in rows:
        if 'session' in row:
            if (row['url'], row['session'].casefold()) in profiles:
                continue
        elif public_start(row['url']) in sites:
            continue
        yield row


def restore(rows, restore_startup=False):
    from webapp_icons import cache_path, cached, store_image

    created = 0
    notices = []
    for row in pending(rows):
        if 'session' not in row:
            backend.install(row)
            created += 1
            continue
        url = row['url']
        if row['icon'] and not cached(url):
            destination = cache_path(url)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            store_image(row['icon'], destination)
        identifier = backend.install(dict(url=url, name=row['name'], session=row['session'],
                                          new_session=bool(backend.sessions(url, include_hidden=True))))
        item = backend.read_record(identifier)
        if item['name'] != row['name']:
            item['name'] = row['name']
            backend.save_record(identifier, item)
        options = row['options']
        start = restore_startup and options['session_start']
        mode = options['external_links']
        if mode == 'default-browser':
            try:
                backend.default_browser()
            except (ValueError, OSError):
                mode = 'profile'
                notices.append(backend.display_name(item))
        backend.save_profile_options(identifier, external_links=mode, session_start=start)
        if row['preferred'] and not backend.preferred_profile(url):
            backend.set_preferred_profile(identifier)
        created += 1
    return created, notices
