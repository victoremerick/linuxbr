"""Per-user autostart management preserving system entries."""
import base64
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import fcntl
from services_backend import replace_file


def home_config():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))


def directories():
    return [home_config() / 'autostart', *[Path(p) / 'autostart' for p in
            os.environ.get('XDG_CONFIG_DIRS', '/etc/xdg').split(':') if p and Path(p).is_absolute()]]


def identifier(name):
    if not isinstance(name, str) or not name.endswith('.desktop') or name != Path(name).name or '/' in name or '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('Identificador de inicialização inválido.')
    return name


def entry(raw):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(raw.decode('utf-8'))
    return parser['Desktop Entry']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def protected(name):
    return name in {'polkit-kde-authentication-agent-1.desktop', 'org.kde.polkit-kde-authentication-agent-1.desktop',
                    'org.kde.plasmashell.desktop', 'org.kde.kglobalaccel.desktop', 'org.kde.ksmserver.desktop'}


def inventory():
    rows = []
    seen = set()
    desktop = set(os.environ.get('XDG_CURRENT_DESKTOP', 'KDE').split(':'))
    for directory in directories():
        for path in sorted(directory.glob('*.desktop')):
            if path.name in seen:
                continue
            seen.add(path.name)
            try:
                if path.stat().st_size > 262144:
                    raise ValueError('Arquivo muito grande.')
                raw = path.read_bytes()
                data = entry(raw)
                hidden = data.get('Hidden', 'false').lower() == 'true'
                only = set(filter(None, data.get('OnlyShowIn', '').split(';')))
                excluded = set(filter(None, data.get('NotShowIn', '').split(';')))
                reason = ''
                if only and not desktop.intersection(only) or desktop.intersection(excluded):
                    reason = 'Destinado a outro ambiente de trabalho'
                program = data.get('TryExec', '')
                if program and not shutil.which(program):
                    reason = 'Programa necessário não encontrado'
                if data.get('X-systemd-skip', '').lower() == 'true':
                    reason = 'Ignorado pelo gerenciador de sessão'
                if data.get('AutostartCondition') or data.get('X-KDE-autostart-condition'):
                    reason = 'Depende de uma condição do aplicativo'
                rows.append(dict(id=path.name, name=data.get('Name[pt_BR]', data.get('Name', path.stem)),
                                 description=data.get('Comment[pt_BR]',data.get('Comment','')),vendor=data.get('X-Vendor',data.get('X-KDE-Vendor','')),
                                 command=data.get('Exec', ''), path=str(path), hidden=hidden,
                                 status='Desabilitado' if hidden else reason or 'Habilitado',
                                 origin='Minha conta' if directory == directories()[0] else 'Sistema',
                                 sha256=digest(raw), protected=protected(path.name), editable=not path.is_symlink()))
            except (OSError, ValueError, configparser.Error, KeyError) as error:
                rows.append(dict(id=path.name, name=path.stem, status='Não foi possível ler',
                                 path=str(path), command='', origin='Não identificado',
                                 sha256='', hidden=False, protected=False, editable=False, error=str(error)))
    return rows


def hidden_content(raw, hidden):
    entry(raw)
    lines = raw.decode('utf-8').splitlines(keepends=True)
    output = []
    inside = False
    inserted = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if inside and not inserted:
                output.append('Hidden=' + str(hidden).lower() + '\n');inserted = True
            inside = stripped == '[Desktop Entry]'
        if inside and re.match(r'^\s*Hidden\s*=', line):
            output.append('Hidden=' + str(hidden).lower() + '\n');inserted = True
        else:
            output.append(line if line.endswith('\n') else line + '\n')
    if inside and not inserted:
        output.append('Hidden=' + str(hidden).lower() + '\n')
    return ''.join(output).encode('utf-8')


def change(name, expected, enabled=None, restore=False):
    identifier(name)
    if protected(name):
        raise ValueError('Este componente é necessário para a sessão e a autenticação.')
    if not restore and type(enabled) is not bool:
        raise ValueError('Estado de inicialização inválido.')
    destination = home_config() / 'autostart' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    storage = home_config() / 'linuxbr/startup-backups'
    if storage.is_symlink():
        raise ValueError('Diretório de backup inválido.')
    storage.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_fd = os.open(storage / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = next((row for row in inventory() if row['id'] == name), None)
        if not current or not current['editable'] or current['sha256'] != expected:
            raise ValueError('A entrada mudou ou não pode ser editada. Atualize a lista.')
        if destination.is_symlink():
            raise ValueError('A entrada pessoal não pode ser um link simbólico.')
        backup = storage / (name + '.json')
        if restore:
            if backup.is_symlink():
                raise ValueError('Backup inválido.')
            saved = json.loads(backup.read_text())
            if not destination.is_file() or digest(destination.read_bytes()) != saved['written_sha256']:
                raise ValueError('A entrada foi alterada após a última mudança. Restauração cancelada.')
            if saved['previous'] is None:
                destination.unlink()
            else:
                replace_file(destination, base64.b64decode(saved['previous'], validate=True))
            backup.unlink()
            return 'Configuração anterior restaurada. A mudança vale no próximo login.'
        original = Path(current['path']).read_bytes()
        if digest(original) != expected:
            raise ValueError('A entrada mudou durante a leitura.')
        updated = hidden_content(original, not enabled)
        saved = dict(previous=base64.b64encode(destination.read_bytes()).decode() if destination.exists() else None,
                     written_sha256=digest(updated))
        replace_file(backup, json.dumps(saved).encode())
        replace_file(destination, updated)
    return 'Configuração salva para o próximo login. O programa em execução não foi encerrado.'
