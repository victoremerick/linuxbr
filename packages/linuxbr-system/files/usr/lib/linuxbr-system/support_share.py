"""Local history of diagnostic requests submitted to KDE Connect."""

from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3


def history_path():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / (
        'linuxbr/diagnostic-sharing.sqlite'
    )


def record_share(device, categories):
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path)) as database, database:
        database.execute('''CREATE TABLE IF NOT EXISTS requests (
                         id INTEGER PRIMARY KEY, submitted TEXT, device TEXT, categories TEXT)''')
        database.execute(
            'INSERT INTO requests (submitted, device, categories) VALUES (?, ?, ?)',
            (datetime.now().astimezone().isoformat(timespec='seconds'), device, json.dumps(categories))
        )
        database.execute('DELETE FROM requests WHERE id <= (SELECT max(id) - 200 FROM requests)')


def recent_shares():
    path = history_path()
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.absolute().as_uri() + '?mode=ro', uri=True)) as database:
        rows = database.execute('SELECT submitted, device, categories FROM requests ORDER BY id DESC')
        return [(stamp, device, json.loads(categories)) for stamp, device, categories in rows]
