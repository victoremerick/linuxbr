"""Keep compatibility claims scoped to the tested application and release."""
from datetime import date
import json
from pathlib import Path
import re

RELEASE = Path('/usr/share/linuxbr/release-info.json')
RESULTS = {'passed': 'Testado nesta versão', 'partial': 'Parcial nesta versão',
           'failed': 'Falhou nesta versão'}


def current_version():
    try:
        value = json.loads(RELEASE.read_text(encoding='utf-8')).get('version', '')
        return value if isinstance(value, str) else ''
    except (OSError, ValueError, AttributeError):
        return ''


def checked_records(item):
    records = item.get('test_records', [])
    if not isinstance(records, list) or len(records) > 100:
        raise ValueError('Lista de testes de compatibilidade inválida.')
    for row in records:
        if (not isinstance(row, dict) or row.get('result') not in RESULTS
                or not re.fullmatch(r'\d+\.\d+\.\d+(?:~(?:alpha|beta|rc)[1-9]\d*)?', row.get('release', ''))
                or not isinstance(row.get('application_version'), str)
                or row['application_version'] != item.get('application_version')
                or not isinstance(row.get('checks'), list) or not row['checks']
                or any(not isinstance(check, str) or not check.strip() for check in row['checks'])
                or not isinstance(row.get('evidence'), str) or not row['evidence'].strip()):
            raise ValueError('Registro de compatibilidade sem versão, cenário ou evidência.')
        if row.get('date') is not None:
            try:date.fromisoformat(row['date'])
            except (TypeError, ValueError):raise ValueError('Data de teste inválida.') from None
    return records


def assessment(item, release=None):
    release = current_version() if release is None else release
    records = checked_records(item)
    matching = [row for row in records if row['release'] == release]
    if matching:
        result = matching[-1]['result']
        return dict(status=result, label=RESULTS[result], current=True)
    if records or item.get('status') in ('tested', 'partial'):
        return dict(status='historical', label='Histórico; conferir nesta versão', current=False)
    return dict(status='untested', label='Não testado nesta versão', current=False)


def details(item, release=None):
    decision = assessment(item, release)
    text = [decision['label']]
    for row in checked_records(item):
        runner = row.get('runner') or 'não registrado'
        when = row.get('date') or 'não registrada'
        text.append('Linux BR '+row['release']+' · aplicativo '+row['application_version']+
                    ' · resultado: '+RESULTS[row['result']].replace(' nesta versão', '')+
                    '\nWine / Proton: '+runner+' · data: '+when+
                    '\nCenários: '+', '.join(row['checks'])+'\nEvidência: '+row['evidence'])
    if not decision['current']:
        text.append('Nenhum resultado aprova este aplicativo na versão instalada do Linux BR.')
    return '\n\n'.join(text)
