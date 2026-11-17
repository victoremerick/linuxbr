"""Transfer application pins in the Plasma Start menu between user accounts."""

from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3

import dbus
from gi.repository import Gio

from store_sources import atomic_write


AGENT = 'org.kde.plasma.favorites.applications'
SERVICE = 'org.kde.ActivityManager'
SCHEMA = 'linuxbr-start-favorites-1'
ENTRY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\.desktop')


def activity_manager(path, interface, introspect=True):
    bus = dbus.SessionBus()
    return dbus.Interface(bus.get_object(SERVICE, path, introspect=introspect), SERVICE + interface)


def pinned_apps(database, activity):
    with closing(sqlite3.connect(database.absolute().as_uri() + '?mode=ro', uri=True, timeout=2)) as connection:
        rows = connection.execute(
            'SELECT DISTINCT targettedResource FROM ResourceLink WHERE initiatingAgent = ? AND usedActivity IN (?, ?) LIMIT 200',
            (AGENT, ':global', activity)
        )
        identifiers = [row[0].removeprefix('applications:') for row in rows]
    return sorted({identifier for identifier in identifiers if ENTRY.fullmatch(identifier)}, key=str.casefold)[:100]


def export_favorites(path):
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    database = data / 'kactivitymanagerd/resources/database'
    activities = activity_manager('/ActivityManager/Activities', '.Activities')
    apps = pinned_apps(database, str(activities.CurrentActivity(timeout=5))) if database.is_file() else []
    atomic_write(Path(path), (json.dumps(dict(schema=SCHEMA, applications=apps), indent=2) + '\n').encode(), 0o600)


def load_favorites(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(32769)
    if len(raw) > 32768:
        raise ValueError('O arquivo de favoritos excede o tamanho permitido.')
    data = json.loads(raw)
    if not isinstance(data, dict) or data.keys() != {'schema', 'applications'} or data['schema'] != SCHEMA:
        raise ValueError('Escolha um arquivo de favoritos exportado pelo Linux BR.')
    apps = data['applications']
    if (not isinstance(apps, list) or len(apps) > 100
            or not all(isinstance(item, str) and ENTRY.fullmatch(item) for item in apps)):
        raise ValueError('A lista contém identificadores de aplicativos inválidos.')
    return dict.fromkeys(apps)


def installed_apps(ids):
    apps = {}
    for identifier in ids:
        app = Gio.DesktopAppInfo.new(identifier)
        if app is not None and app.should_show() and app.get_string('Type') == 'Application':
            apps[identifier] = app.get_display_name()
    return apps


def import_favorites(ids):
    linking = activity_manager('/ActivityManager/Resources/Linking', '.ResourcesLinking', introspect=False)
    for identifier in ids:
        resource = 'applications:' + identifier
        linking.LinkResourceToActivity(AGENT, resource, ':global', timeout=5)
        if not linking.IsResourceLinkedToActivity(AGENT, resource, ':global', timeout=5):
            raise ValueError('O menu Iniciar não confirmou o favorito ' + identifier + '.')
