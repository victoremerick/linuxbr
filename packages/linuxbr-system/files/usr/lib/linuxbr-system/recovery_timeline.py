"""Correlate bounded APT, boot, USB and error records visible to the user."""

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import subprocess

APT = Path('/var/log/apt/history.log')
USB = re.compile(r'USB disconnect|new (?:full|high|super|low)[- ]speed USB device|New USB device found', re.I)
EVENTS = {'updates': 'Atualizações de pacotes', 'boots': 'Inicializações',
          'peripherals': 'Periféricos USB', 'errors': 'Falhas do sistema'}
LIMIT = 150


def date(value):
    return datetime.fromisoformat(' '.join(value.split())).astimezone(timezone.utc)


def updates(path=APT):
    events = []
    readable = False
    for source in (path, path.with_name(path.name + '.1.gz')):
        try:
            opener = gzip.open if source.suffix == '.gz' else open
            with opener(source, 'rt', encoding='utf-8', errors='replace') as stream:
                raw = stream.read(2 * 1024 * 1024 + 1)
            readable = True
        except (OSError, EOFError):
            continue
        for block in raw[:2 * 1024 * 1024].split('\n\n'):
            fields = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line)
            changes = [f'{name} {len(re.findall(r"(?:^|, )[^(),]+ \(", fields[key]))}'
                       for key, name in (('Upgrade', 'atualizados'), ('Install', 'instalados'),
                                         ('Remove', 'removidos'), ('Purge', 'purgados'))
                       if key in fields]
            if not changes:
                continue
            try:
                events.append((date(fields['Start-Date']), 'updates',
                               ', '.join(changes) + ('' if fields.get('End-Date') else ' · término ausente')))
            except (KeyError, ValueError):
                continue
    return events, readable


def journal(*arguments):
    try:
        run = subprocess.run(['/usr/bin/journalctl', '--no-pager', '--quiet', *arguments],
                             timeout=6, capture_output=True, text=True, errors='replace',
                             env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}, check=False)
        return run.stdout.splitlines(), run.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return [], False


def boots():
    rows, readable = journal('--list-boots', '--utc', '-o', 'json')
    try:
        records = json.loads('\n'.join(rows))
        return [(datetime.fromtimestamp(int(row['first_entry']) / 10**6, timezone.utc), 'boots',
                 'Inicialização atual' if row['index'] == 0 else 'Inicialização anterior')
                for row in records[-25:]], readable
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        return [], False


def log_events(kind):
    flags = ('-k', '--grep', USB.pattern, '--case-sensitive=no') if kind == 'peripherals' else ('-p', '0..3')
    events = []
    visibility = []
    for boot in ('0', '-1'):
        rows, readable = journal('--boot', boot, '-n', '120', '-o', 'json',
                                 '--output-fields', 'MESSAGE,SYSLOG_IDENTIFIER', *flags)
        visibility.append(readable)
        for row in rows:
            try:
                record = json.loads(row)
                message = record['MESSAGE']
                if not isinstance(message, str):
                    continue
                when = datetime.fromtimestamp(int(record['__REALTIME_TIMESTAMP']) / 10**6, timezone.utc)
                message = ''.join(char if char.isprintable() else ' ' for char in message)
                events.append((when, kind, message[:350]))
            except (KeyError, TypeError, ValueError, OSError, OverflowError):
                continue
    return events, any(visibility)


def render(kind='all'):
    unique = set()
    unavailable = []
    for source, check in (('updates', updates), ('boots', boots),
                          ('peripherals', lambda: log_events('peripherals')),
                          ('errors', lambda: log_events('errors'))):
        if kind not in ('all', source):
            continue
        events, readable = check()
        if not readable:
            unavailable.append(EVENTS[source])
        unique.update(events)
    lines = [f'{when.astimezone():%d/%m/%Y %H:%M:%S}  ·  {EVENTS[source]}  ·  {message}'
             for when, source, message in sorted(unique, reverse=True)[:LIMIT]]
    if unavailable:
        lines.append('Registros indisponíveis para esta conta: ' + ', '.join(unavailable) + '.')
    return '\n'.join(lines or ['Nenhum evento encontrado nos registros acessíveis.'])
