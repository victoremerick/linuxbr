"""Read-only previews of package transactions and data ownership."""
import os
from pathlib import Path
import re
import subprocess

from store_backend import format_size


INSTALL = re.compile(r'^Inst ([a-z0-9.+-]+(?::[a-z0-9]+)?) (?:\[[^\]]+\] )?\(([^ )]+)', re.M)
PACKAGE = re.compile(r'[a-z0-9][a-z0-9.+-]*(?::[a-z0-9]+)?')
FLATPAK = re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}(?:/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?')
DATA_FIELDS = {'config': 'Configuração', 'data': 'Dados', 'cache': 'Cache'}


def read(argv, timeout=15):
    result = subprocess.run(argv, capture_output=True, text=True, errors='replace',
                            timeout=timeout, env={**os.environ, 'LC_ALL': 'C', 'TERM': 'dumb'})
    if result.returncode:
        raise ValueError('A fonte configurada não conseguiu simular esta operação.')
    return result.stdout


def deb_preview(package, action):
    if not PACKAGE.fullmatch(package) or action not in ('install', 'remove'):
        raise ValueError('Pacote inválido para a prévia.')
    options = ['--no-remove'] if action == 'install' else []
    simulation = read(['/usr/bin/apt-get', '-s', *options, action, '--', package])
    if action == 'remove':
        removed = [line.split()[1] for line in simulation.splitlines() if line.startswith('Remv ')]
        conffiles = read(['/usr/bin/dpkg-query', '-W', '-f=${Conffiles}', '--', package])
        config = [line.split()[0] for line in conffiles.splitlines()
                  if line.lstrip().startswith('/')]
        return ('Pacotes que o APT prevê remover\n' + ('\n'.join(removed) or 'Nenhum') +
                '\n\nArquivos de configuração registrados e preservados por esta remoção\n' +
                ('\n'.join(config) or 'Nenhum registrado') +
                '\n\nDados, cache e prefixos do usuário permanecem na conta.')
    changes = INSTALL.findall(simulation)
    download = installed = 0
    unknown = 0
    records = {}
    if changes:
        names = [name + '=' + version for name, version in changes[:100]]
        try:
            output = read(['/usr/bin/apt-cache', 'show', '--no-all-versions', *names])
        except ValueError:
            output = ''
        for paragraph in re.split(r'\n\s*\n', output):
            fields = dict(re.findall(r'^(Package|Version|Architecture|Size|Installed-Size): (\S+)$',
                                     paragraph, re.M))
            package_id, version = fields.get('Package'), fields.get('Version')
            if package_id and version:
                records.setdefault((package_id, version), fields)
                if fields.get('Architecture'):
                    records[(package_id + ':' + fields['Architecture'], version)] = fields
    for name, version in changes[:100]:
        fields = records.get((name, version), {})
        size, on_disk = fields.get('Size', ''), fields.get('Installed-Size', '')
        if not (size.isdecimal() and on_disk.isdecimal()):
            unknown += 1
        download += int(size) if size.isdecimal() else 0
        installed += int(on_disk) * 1024 if on_disk.isdecimal() else 0
    partial = bool(unknown or len(changes) > 100)
    title = 'Estimativa parcial' if partial else 'Estimativa'
    return (f'{title} de downloads · {format_size(download)}\n'
            f'Tamanho bruto instalado dos pacotes consultados · {format_size(installed)}\n\n'
            'Pacotes selecionados na simulação\n' +
            ('\n'.join(f'{name} · {version}' for name, version in changes[:150]) or 'Nenhum') +
            '\n\nPacotes DEB podem criar serviços ou executar scripts administrativos. '
            'O APT não declara todas essas ações no resultado da simulação.')


def flatpak_preview(target, action):
    identity, scope = target['target'], target['scope']
    if not FLATPAK.fullmatch(identity) or scope not in ('system', 'user'):
        raise ValueError('Referência Flatpak inválida.')
    if action == 'remove':
        rows = [f'{DATA_FIELDS[field]} · {folder}' for field, folder in data_directories(identity).items()]
        return ('Pastas desta conta preservadas pela remoção padrão\n' +
                ('\n'.join(rows) or 'Nenhuma encontrada nesta conta.'))
    origin = target['origin']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', origin):
        raise ValueError('Fonte Flatpak inválida.')
    argv = ['/usr/bin/flatpak', '--' + scope, 'remote-info', origin, identity]
    info = read(argv)
    metadata = read([*argv[:3], '--show-metadata', *argv[3:]])
    context = re.search(r'^\[Context\]\n((?:[^\[].*\n)*)', metadata, re.M)
    return (info.strip()[:5000] + '\n\nPermissões declaradas pelo pacote\n' +
            (context[1].strip() if context else 'Nenhuma lista fornecida.') +
            '\n\nO gerenciador confirma o espaço total incluindo o runtime e as dependências.')


def data_directories(identity):
    if not FLATPAK.fullmatch(identity):
        raise ValueError('Referência Flatpak inválida.')
    name = identity.split('/')[0]
    root = Path.home()
    for part in ('.var', 'app', name):
        root /= part
        if root.is_symlink() or not root.is_dir():
            return {}
    return {field: root / field for field in DATA_FIELDS
            if not (root / field).is_symlink() and (root / field).is_dir()}


def trash_removed_data(target):
    identity = target['target'].split('/')[0]
    # Flatpak uses the same user directory for both scopes and all branches.
    for arguments in (('--user', 'list', '--app'), ('--system', 'list', '--app'), ('ps',)):
        apps = read(['/usr/bin/flatpak', *arguments, '--columns=application'])
        if identity in apps.splitlines():
            raise ValueError('Outra instalação ou execução ainda usa os dados do aplicativo.')
    paths = data_directories(identity)
    for field in target['trash_data']:
        if field in paths:
            read(['/usr/bin/gio', 'trash', '--', str(paths[field])])


def preview(target, action):
    if target['manager'] == 'deb':
        return deb_preview(target['target'], action)
    if target['manager'] == 'flatpak':
        return flatpak_preview(target, action)
    raise ValueError('Esta fonte apresenta a confirmação no gerenciador original.')
