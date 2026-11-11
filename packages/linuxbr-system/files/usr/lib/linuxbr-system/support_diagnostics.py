"""Collect bounded, structured support data without exporting raw logs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from snapshot_service import status as recovery_status


CATEGORIES = {
    'system': 'Sistema e espaço',
    'network': 'Rede',
    'updates': 'Atualização e recuperação',
    'graphics': 'Sessão gráfica e captura',
}
GRAPHICS_EVENTS = {
    'avisos do portal KDE nas últimas 24 h': 'plasma-xdg-desktop-portal-kde',
    'avisos do KWin nas últimas 24 h': 'plasma-kwin_wayland',
}


def query(argv, unavailable=''):
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                errors='replace', timeout=3)
        return result.stdout.strip() if result.returncode == 0 else unavailable
    except (OSError, subprocess.TimeoutExpired):
        return unavailable


def choice(value, allowed):
    return value if isinstance(value, str) and value in allowed else 'indisponível'


def collect(category):
    if category == 'system':
        version = query(['/usr/bin/dpkg-query', '-W', '-f=${Version}', 'linuxbr-release'])
        return {
            'versão': version if re.fullmatch(r'[0-9][0-9.a-z+~:-]{0,79}', version) else 'indisponível',
            'kernel': os.uname().release,
            'espaço livre no sistema (bytes)': shutil.disk_usage('/').free,
        }
    if category == 'network':
        return {'conectividade': choice(
            query(['/usr/bin/nmcli', '-t', '-f', 'CONNECTIVITY', 'general']),
            {'none', 'portal', 'limited', 'full', 'unknown'})}
    if category == 'updates':
        recovery = recovery_status()
        data = {
            'reinício solicitado pelo sistema': Path('/run/reboot-required').exists(),
            'destino de recuperação configurado': recovery['configured'],
            'última proteção': choice(recovery['last'].get('status'), {
                'created', 'failed', 'disabled', 'not-configured'}),
        }
        revision = recovery['last'].get('revision')
        if isinstance(revision, str) and re.fullmatch(r'[A-Za-z0-9._-]{1,80}', revision):
            data['revisão associada à proteção'] = revision
        code = recovery['last'].get('code')
        if type(code) is int and -255 <= code <= 255:
            data['código da última proteção'] = code
        config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
        try:
            with (config / 'linuxbr/organization.json').open('rb') as state:
                revision = json.loads(state.read(16385)).get('revision')
            if isinstance(revision, str) and re.fullmatch(r'[A-Za-z0-9._-]{1,80}', revision):
                data['revisão preparada nesta conta'] = revision
        except (OSError, ValueError, AttributeError):
            pass
        return data
    if category == 'graphics':
        data = {'sessão': choice(os.environ.get('XDG_SESSION_TYPE'), {'wayland', 'x11'})}
        for service in ('xdg-desktop-portal', 'plasma-xdg-desktop-portal-kde',
                        'plasma-kwin_wayland', 'pipewire', 'wireplumber'):
            data[service] = choice(query(['/usr/bin/systemctl', '--user', 'show',
                                          '-p', 'ActiveState', '--value', service]),
                                   {'active', 'inactive', 'failed', 'activating', 'deactivating'})
        for label, unit in GRAPHICS_EVENTS.items():
            events = query(['/usr/bin/journalctl', '--user', '--unit', unit, '--since=-24h',
                            '--priority=warning', '--lines=30', '--output=json',
                            '--output-fields=PRIORITY', '--quiet', '--no-pager'], unavailable=None)
            data[label] = 'indisponível' if events is None else min(30, len(events.splitlines()))
        return data
    raise ValueError('Categoria de diagnóstico inválida.')


def render(sections, selected):
    return json.dumps({'schema': 1, 'diagnóstico': {
        CATEGORIES[key]: sections[key] for key in CATEGORIES if key in selected
    }}, ensure_ascii=False, indent=2) + '\n'


def summary(sections, selected):
    labels = {'active': 'Ativo', 'inactive': 'Inativo', 'failed': 'Falhou',
              'activating': 'Iniciando', 'deactivating': 'Encerrando',
              'created': 'Ponto criado', 'disabled': 'Desativada',
              'not-configured': 'Sem configuração', 'none': 'Sem conexão',
              'portal': 'Rede solicita login', 'limited': 'Conexão limitada',
              'full': 'Conectado', 'unknown': 'Desconhecida'}
    blocks = []
    for category in selected:
        rows = [CATEGORIES[category]]
        for name, value in sections[category].items():
            if type(value) is bool:
                value = 'Sim' if value else 'Não'
            elif name.endswith(' (bytes)') and type(value) is int:
                name = name.removesuffix(' (bytes)')
                value = f'{value / 1024**3:.2f} GiB'.replace('.', ',')
            elif isinstance(value, str):
                value = labels.get(value, value)
            rows.append(f'  {name[:1].upper() + name[1:]} · {value}')
        blocks.append('\n'.join(rows))
    return '\n\n'.join(blocks) or 'Selecione uma categoria para conferir o diagnóstico.'


if __name__ == '__main__':
    print(json.dumps({key: collect(key) for key in CATEGORIES}, ensure_ascii=False))
