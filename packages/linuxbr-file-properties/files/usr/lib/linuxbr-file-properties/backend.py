#!/usr/bin/python3
"""Read-only property queries and explicit hand-offs to native desktop services."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def command(argv, timeout=8):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)


def local_path(value):
    path = Path(value)
    if not path.is_absolute() or '\0' in value:
        raise ValueError('Selecione um caminho local absoluto.')
    return path


def mount_for(path, mountinfo='/proc/self/mountinfo'):
    best = {}
    try:
        lines = Path(mountinfo).read_text().splitlines()
    except OSError:
        return best
    def decode(value):
        return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)
    for line in lines:
        fields = line.split()
        try:
            divider = fields.index('-')
            target = decode(fields[4])
            if (str(path) == target or str(path).startswith(target.rstrip('/') + '/')) and len(target) > len(best.get('target', '')):
                best = dict(target=target, filesystem=fields[divider + 1],
                            source=decode(fields[divider + 2]), readonly='ro' in fields[5].split(','))
        except (ValueError, IndexError):
            continue
    return best


def familiar_path(path):
    try:
        sys.path.insert(0, '/usr/lib/linuxbr-drive-manager')
        from terminal import display
        return display(str(path))
    except (ImportError, OSError, ValueError):
        return str(path)


def inspect(path):
    path = local_path(str(path))
    info = path.lstat()
    link = stat.S_ISLNK(info.st_mode)
    result = dict(path=str(path), familiar=familiar_path(path), link=link,
                  target=os.readlink(path) if link else '', bytes=info.st_size,
                  allocated=getattr(info, 'st_blocks', 0) * 512,
                  modified=info.st_mtime, accessed=info.st_atime,
                  created=getattr(info, 'st_birthtime', None), mount=mount_for(path),
                  signature='Não verificada. Nenhum verificador e cadeia de confiança foram selecionados.')
    if path.suffix.lower() == '.lnk':
        result['shortcut'] = 'Atalho Windows (.lnk). Os campos não são convertidos automaticamente em um lançador Linux.'
    elif link:
        result['shortcut'] = 'Link simbólico. O destino acima pertence ao link; as informações adicionais usam lstat, sem alterar o alvo.'
    if path.suffix.lower() == '.exe' and stat.S_ISREG(info.st_mode) and not link:
        result['declared'] = pe_version_strings(path)
    return result


def pe_version_strings(path):
    """Read bounded PE version resources; values are declarations, not signatures."""
    fields = {'CompanyName': 'Fabricante declarado', 'FileDescription': 'Descrição declarada',
              'FileVersion': 'Versão declarada do arquivo', 'ProductName': 'Produto declarado',
              'ProductVersion': 'Versão declarada do produto'}
    found = {}
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            total = os.fstat(stream.fileno()).st_size
            def read(offset, size):
                if offset < 0 or size < 0 or size > 2 * 1024 * 1024 or offset + size > total:
                    raise ValueError('Recurso fora do arquivo.')
                stream.seek(offset)
                value = stream.read(size)
                if len(value) != size:
                    raise ValueError('Recurso incompleto.')
                return value
            dos = read(0, 64)
            if dos[:2] != b'MZ': return found
            pe_offset = struct.unpack_from('<I', dos, 60)[0]
            pe = read(pe_offset, 24)
            if pe[:4] != b'PE\0\0': return found
            sections, optional_size = struct.unpack_from('<H', pe, 6)[0], struct.unpack_from('<H', pe, 20)[0]
            if not 0 < sections <= 96 or not 128 <= optional_size <= 512: return found
            optional = read(pe_offset + 24, optional_size)
            magic = struct.unpack_from('<H', optional)[0]
            directory = 96 if magic == 0x10b else 112 if magic == 0x20b else -1
            if directory < 0 or directory + 24 > len(optional): return found
            resource_rva, resource_size = struct.unpack_from('<II', optional, directory + 16)
            if not resource_rva or not resource_size: return found
            section_data = read(pe_offset + 24 + optional_size, sections * 40)
            def address(rva):
                for index in range(sections):
                    _virtual_size, virtual, raw_size, raw_offset = struct.unpack_from('<IIII', section_data, index * 40 + 8)
                    if virtual <= rva < virtual + raw_size:
                        return raw_offset + rva - virtual
                raise ValueError('Endereço de recurso não mapeado.')
            root = address(resource_rva)
            def entries(offset):
                if offset < 0 or offset + 16 > resource_size: return []
                header = read(root + offset, 16)
                named, numbered = struct.unpack_from('<HH', header, 12)
                count = named + numbered
                if count > 128 or offset + 16 + count * 8 > resource_size: return []
                data = read(root + offset + 16, count * 8)
                return [struct.unpack_from('<II', data, index * 8) for index in range(count)]
            resources = []
            def walk(offset, depth):
                if depth > 3 or len(resources) >= 8: return
                for _name, child in entries(offset):
                    if len(resources) >= 8: return
                    if child & 0x80000000:
                        walk(child & 0x7fffffff, depth + 1)
                    elif child + 16 <= resource_size:
                        rva, size = struct.unpack_from('<II', read(root + child, 16))
                        if 0 < size <= 2 * 1024 * 1024:
                            resources.append(read(address(rva), size))
            for kind, child in entries(0):
                if kind == 16 and child & 0x80000000:
                    walk(child & 0x7fffffff, 1)
            def parse(data, start, end, depth=0):
                if depth > 8 or start + 6 > end: return
                length, value_length, value_type = struct.unpack_from('<HHH', data, start)
                finish = start + length
                if length < 8 or finish > end: return
                position = start + 6
                key_end = position
                while key_end + 2 <= finish and data[key_end:key_end + 2] != b'\0\0' and key_end - position < 256:
                    key_end += 2
                key = data[position:key_end].decode('utf-16le', errors='replace')
                value_start = (key_end + 2 + 3) & ~3
                value_size = value_length * (2 if value_type == 1 else 1)
                if value_start + value_size > finish: return
                if key in fields and value_type == 1:
                    value = data[value_start:value_start + min(value_size, 1000)].decode('utf-16le', errors='replace').rstrip('\0')
                    found[fields[key]] = ''.join(char if ord(char) >= 32 else ' ' for char in value)
                position = (value_start + value_size + 3) & ~3
                while position + 6 <= finish:
                    child_length = struct.unpack_from('<H', data, position)[0]
                    if child_length < 8: break
                    parse(data, position, finish, depth + 1)
                    position = (position + child_length + 3) & ~3
            for resource in resources:
                parse(resource, 0, len(resource))
    except (OSError, ValueError, struct.error):
        return found
    return found


def security(path):
    path = local_path(str(path))
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return dict(text='Link simbólico: o editor nativo distingue o link e o alvo. O acesso efetivo ao alvo não foi consultado.', recursive=False)
    rights = []
    for label, mode in [('leitura', os.R_OK), ('alteração', os.W_OK),
                        ('acesso à pasta' if stat.S_ISDIR(info.st_mode) else 'execução', os.X_OK)]:
        try:
            allowed = os.access(path, mode, effective_ids=True)
        except (TypeError, NotImplementedError):
            allowed = os.access(path, mode)
        rights.append(label + ': ' + ('permitida' if allowed else 'não permitida'))
    mount = mount_for(path)
    lines = ['Acesso efetivo para a conta atual: ' + '; '.join(rights) + '.',
             'Montagem: ' + (mount.get('filesystem') or 'não identificada') +
             ('; somente leitura.' if mount.get('readonly') else '.'),
             'O editor avançado nativo preserva proprietário, grupo e a máscara de acesso da ACL.']
    if mount.get('filesystem', '').lower() in ('ntfs', 'ntfs3', 'fuseblk', 'vfat', 'exfat', 'cifs'):
        lines.append('As permissões dependem do driver e das opções de montagem. Esta página não representa uma ACL Windows.')
    if shutil.which('getfacl'):
        reply = command(['getfacl', '--absolute-names', '--all-effective', '--', str(path)])
        lines.extend(['', reply.stdout.strip() if reply.returncode == 0 else
                      'ACL não consultada: ' + reply.stderr.strip()])
    else:
        lines.append('A consulta getfacl não está disponível; use o editor nativo se o sistema oferecer ACL.')
    return dict(text='\n'.join(lines), recursive=stat.S_ISDIR(info.st_mode) and not mount.get('readonly'))


def recursive_preview(path):
    """Count one device, skipping directory links and nested mount points."""
    path = local_path(str(path))
    root = path.lstat()
    if not stat.S_ISDIR(root.st_mode) or stat.S_ISLNK(root.st_mode):
        raise ValueError('A prévia exige uma pasta local que não seja um link.')
    result = dict(files=0, folders=1, links=0, mounts=0, errors=[], bytes=0)
    try:
        mounts = {re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), line.split()[4])
                  for line in Path('/proc/self/mountinfo').read_text().splitlines() if len(line.split()) > 4}
    except OSError:
        mounts = set()
    stack = [path]
    last = 0
    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                for item in entries:
                    try:
                        info = item.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            result['links'] += 1
                        elif info.st_dev != root.st_dev or (item.is_dir(follow_symlinks=False) and (item.path in mounts or os.path.ismount(item.path))):
                            result['mounts'] += 1
                        elif stat.S_ISDIR(info.st_mode):
                            result['folders'] += 1
                            stack.append(Path(item.path))
                        elif stat.S_ISREG(info.st_mode):
                            result['files'] += 1
                            result['bytes'] += info.st_size
                    except OSError as error:
                        if len(result['errors']) < 20:
                            result['errors'].append(str(error))
        except OSError as error:
            if len(result['errors']) < 20:
                result['errors'].append(str(error))
        if time.monotonic() - last > .25:
            emit(dict(progress=True, files=result['files'], folders=result['folders']))
            last = time.monotonic()
    result['safe_recursive'] = not result['mounts'] and not result['errors']
    return result


def hash_file(path, algorithm, progress=emit):
    if algorithm not in ('sha256', 'sha512'):
        raise ValueError('Escolha SHA-256 ou SHA-512.')
    path = local_path(str(path))
    if path.is_symlink():
        raise ValueError('Selecione o arquivo de destino para calcular seu hash; links não são seguidos.')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0) |
                         getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('O cálculo exige um arquivo regular local.')
        digest = hashlib.new(algorithm)
        total = 0
        last = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            total += len(block)
            if time.monotonic() - last > .15:
                progress(dict(progress=True, done=total, total=before.st_size))
                last = time.monotonic()
        after = os.fstat(descriptor)
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        current = path.lstat()
        if signature(before) != signature(after) or signature(after) != signature(current) or total != after.st_size:
            raise ValueError('O arquivo mudou durante a leitura. Calcule novamente; o resultado foi descartado.')
        return dict(hash=digest.hexdigest(), algorithm=algorithm, bytes=total)
    finally:
        os.close(descriptor)


def runner():
    sys.path.insert(0, '/usr/lib/linuxbr-system')
    import windows_runner
    return windows_runner


def compatibility(path):
    module = runner()
    try:
        _path, kind = module.inspect_windows_file(path)
        error = ''
    except (OSError, ValueError) as failure:
        kind, error = 'Não identificada', str(failure)
    if kind == 'MSI':
        kind = 'MSI — arquitetura não informada'
        if shutil.which('msiinfo'):
            reply = command(['msiinfo', 'suminfo', str(path)])
            template = next((line.split(':', 1)[1].strip().split(';')[0] for line in reply.stdout.splitlines()
                             if line.startswith('Template:')), '')
            if reply.returncode == 0 and template:
                kind = 'MSI — ' + {'Intel': 'x86', 'x64': 'x64', 'Intel64': 'Itanium', 'Arm64': 'ARM64'}.get(template, template[:80]) + ' (declarada pelo instalador)'
    choices = []
    for identifier, name in module.environments():
        item = module.read_environment(identifier)
        choices.append(dict(id=identifier, name=name, architecture=item['architecture']))
    return dict(architecture=kind, error=error, environments=choices,
                default=module.default_environment(), wine=bool(shutil.which('wine')))


def wine_action(path, environment, action):
    if os.geteuid() == 0:
        raise ValueError('Use esta ação na sua sessão normal, sem sudo.')
    module = runner()
    module.read_environment(environment)
    if action == 'diagnose':
        return dict(text=module.diagnose_program(environment, path))
    if action not in ('configure', 'run'):
        raise ValueError('Ação não disponível.')
    job = module.start_job(environment, action, path if action == 'run' else None)
    try:
        subprocess.Popen(['/usr/bin/linuxbr-windows', '--watch-job', job, '--environment', environment,
                          '--watch-action', action, str(path)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        monitor = True
    except OSError:
        monitor = False
    return dict(job=job, monitor=monitor, text='A operação foi iniciada no ambiente selecionado. ' +
                ('A janela Programas Windows e jogos acompanha o resultado e pode permanecer aberta após fechar estas propriedades.' if monitor else
                 'Não foi possível abrir o acompanhamento. Consulte os registros da operação ' + job + ' em Programas Windows e jogos.'))


def kconfig_list(value):
    values, word, escaped = [], '', False
    translations = {'n': '\n', 'r': '\r', 't': '\t', 's': ' '}
    for char in value:
        if escaped:
            word += translations.get(char, char)
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == ',':
            values.append(word)
            word = ''
        else:
            word += char
    values.append(word + ('\\' if escaped else ''))
    return [value for value in values if value]


def contains_path(parent, child):
    try:
        return Path(child).is_relative_to(Path(parent))
    except (ValueError, TypeError):
        return False


def kup_plans(path, config=None):
    config = Path(config) if config else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'kuprc'
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    try:
        parser.read_string(config.read_text())
    except (OSError, configparser.Error):
        return []
    result = []
    for section in parser.sections():
        if not re.fullmatch(r'Plan(?:/|\]\[)\d+', section):
            continue
        fields = {key.removesuffix('[$e]'): value for key, value in parser.items(section)}
        included = kconfig_list(fields.get('Paths included', str(Path.home())))
        excluded = kconfig_list(fields.get('Paths excluded', ''))
        if not any(contains_path(os.path.expandvars(root), path) for root in included) or any(contains_path(os.path.expandvars(root), path) for root in excluded):
            continue
        raw = fields.get('Filesystem destination path', '')
        parsed = urlsplit(raw)
        destination = unquote(parsed.path) if parsed.scheme == 'file' and not parsed.netloc else raw if not parsed.scheme else ''
        destination = os.path.expandvars(os.path.expanduser(destination))
        external = fields.get('Destination type', '1') != '0'
        if external:
            destination = ''
            device = fields.get('External drive UUID', '')
            if device and shutil.which('findmnt'):
                reply = command(['findmnt', '--noheadings', '--raw', '--source', 'UUID=' + device, '--output', 'TARGET'])
                mounts = reply.stdout.strip().splitlines()
                if reply.returncode == 0 and len(mounts) == 1:
                    relative = fields.get('External drive destination path', 'Backups')
                    candidate = Path(mounts[0]) / relative
                    if contains_path(mounts[0], candidate) and '..' not in Path(relative).parts:
                        destination = str(candidate)
        result.append(dict(id=section, name=fields.get('Description', 'Cópia pessoal'),
                           repository=destination, versioned=fields.get('Backup type', '0') == '0',
                           last=fields.get('Last complete backup', ''), external=external,
                           patterns=fields.get('Exclude patterns', 'false') == 'true'))
    return result


def versions(path):
    path = local_path(str(path))
    plans = kup_plans(path)
    rows, notes = [], []
    deadline = time.monotonic() + 20
    if not shutil.which('bup'):
        return dict(rows=[], notes=['A ferramenta bup não está disponível para consultar as versões pessoais.'])
    for plan in plans:
        repo = Path(plan['repository']) if plan['repository'] else None
        if not plan['versioned']:
            notes.append(plan['name'] + ': cópia sincronizada, sem histórico de versões.')
            continue
        if repo is None or not repo.is_dir():
            notes.append(plan['name'] + ': destino desconectado ou indisponível.')
            continue
        if not (repo / 'objects').is_dir() or not (repo / 'HEAD').is_file():
            notes.append(plan['name'] + ': não foi encontrado um repositório de versões neste destino.')
            continue
        try:
            reply = command(['bup', '-d', str(repo), 'ls', 'kup/'])
        except subprocess.TimeoutExpired:
            notes.append(plan['name'] + ': destino demorou para responder; a consulta deste plano foi interrompida.')
            continue
        if reply.returncode:
            notes.append(plan['name'] + ': não foi possível ler o histórico. ' + reply.stderr.strip()[:600])
            continue
        stamps = [word.rstrip('/') for word in reply.stdout.splitlines() if re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{6}/?', word)]
        for stamp in sorted(set(stamps), reverse=True)[:100]:
            if time.monotonic() >= deadline:
                notes.append('Consulta parcial: limite de tempo atingido. O explorador de versões permite consultar o restante.')
                break
            archive_path = 'kup/' + stamp + '/' + str(path).lstrip('/')
            try:
                reply = command(['bup', '-d', str(repo), 'ls', '--directory', '--', archive_path], timeout=5)
            except subprocess.TimeoutExpired:
                notes.append(plan['name'] + ': consulta parcial; o destino demorou para responder.')
                break
            if reply.returncode == 0 and reply.stdout.strip():
                rows.append(dict(plan=plan['name'], date=stamp, repository=str(repo), path=str(path)))
        emit(dict(progress=True, plans=len(plans), found=len(rows)))
    if not plans:
        notes.append('Nenhum plano de cópia pessoal inclui este caminho. Configure o backup para guardar versões futuras.')
    elif not rows and not notes:
        notes.append('Nenhuma versão deste item foi encontrada nos destinos disponíveis.')
    return dict(rows=rows, notes=notes)


def sharing(path, authorize_firewall=False):
    path = local_path(str(path))
    states = []
    shares = []
    shares_complete = False
    partial = False
    try:
        reply = command(['net', 'usershare', 'info', '--long']) if shutil.which('net') else None
    except (OSError, subprocess.TimeoutExpired):
        reply = None
    if not reply or reply.returncode:
        states.append('Publicações: não foi possível consultar o registro de pastas compartilhadas.')
        partial = True
    if reply and reply.returncode == 0:
        parser = configparser.RawConfigParser(strict=False)
        try:
            parser.read_string(reply.stdout)
            shares_complete = True
            for name in parser.sections():
                if parser.get(name, 'path', fallback='').rstrip('/') == str(path).rstrip('/'):
                    shares.append(dict(name=name, smb='smb://' + socket.gethostname() + '/' + name,
                                       unc='\\\\' + socket.gethostname() + '\\' + name,
                                       guest=parser.get(name, 'guest_ok', fallback='desconhecido'),
                                       acl=parser.get(name, 'usershare_acl', fallback='não consultada')))
        except configparser.Error:
            states.append('Publicações: o registro retornou dados não reconhecidos.')
            partial = True
    if shutil.which('systemctl'):
        for service in ('smbd.service', 'nmbd.service'):
            try:
                reply = command(['systemctl', 'is-active', service], timeout=3)
                states.append(service + ': ' + (reply.stdout.strip() or 'não consultado'))
            except (OSError, subprocess.TimeoutExpired):
                states.append(service + ': não foi possível consultar; os demais dados foram preservados.')
                partial = True
    zones = []
    if shutil.which('firewall-cmd'):
        timeout = 120 if authorize_firewall else 3
        try:
            reply = command(['firewall-cmd', '--get-active-zones'], timeout=timeout)
            if reply.returncode == 0:
                zones = [line.split()[0] for line in reply.stdout.splitlines()
                         if line and not line[0].isspace() and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', line.split()[0])]
            else:
                partial = True
        except (OSError, subprocess.TimeoutExpired):
            partial = True
        for zone in zones:
            try:
                reply = command(['firewall-cmd', '--zone=' + zone, '--query-service=samba'], timeout=timeout)
                state = ('liberado' if reply.returncode == 0 else 'não liberado'
                         if reply.returncode == 1 else 'não foi possível consultar')
                partial = partial or reply.returncode not in (0, 1)
            except (OSError, subprocess.TimeoutExpired):
                state = 'consulta não concluída; autorização recusada ou prazo esgotado'
                partial = True
            states.append('Firewall (zona ' + zone + ', serviço Samba): ' + state)
        if not zones:
            states.append('Firewall: nenhuma zona ativa pôde ser consultada; acesso externo não verificado.')
    else:
        states.append('Firewall: gerenciador não disponível para consulta; acesso externo não verificado.')
    return dict(shares=shares, states=states, zones=zones, shares_complete=shares_complete, partial=partial)


def start_sharing_service(persist=False):
    argv = ['systemctl', 'enable', '--now', 'smbd.service'] if persist else ['systemctl', 'start', 'smbd.service']
    reply = command(argv, timeout=120)
    if reply.returncode:
        raise ValueError('O serviço não foi ativado: ' + reply.stderr.strip()[:1500])
    reply = command(['systemctl', 'is-active', 'smbd.service'])
    if reply.returncode or reply.stdout.strip() != 'active':
        raise ValueError('A solicitação terminou, mas o serviço SMB não está ativo. Consulte o registro do serviço.')
    return dict(text='Serviço SMB ativo.' + (' A inicialização após reiniciar foi habilitada.' if persist else ' Esta ação não altera a inicialização após reiniciar.'))


def allow_sharing_firewall(zone, persist=False):
    if not isinstance(zone, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', zone):
        raise ValueError('Escolha uma zona de rede ativa.')
    active = command(['firewall-cmd', '--get-active-zones'], timeout=120)
    zones = [line.split()[0] for line in active.stdout.splitlines() if line and not line[0].isspace()]
    if active.returncode or zone not in zones:
        raise ValueError('A zona selecionada não está ativa. Consulte o estado da rede novamente.')
    argv = ['firewall-cmd', '--zone=' + zone, '--add-service=samba']
    reply = command(argv, timeout=120)
    if reply.returncode:
        raise ValueError('O firewall não foi alterado: ' + reply.stderr.strip()[:1500])
    if persist:
        reply = command(argv + ['--permanent'], timeout=120)
        if reply.returncode:
            raise ValueError('Samba foi liberado nesta sessão, mas a configuração permanente falhou: ' + reply.stderr.strip()[:1500])
    check = command(['firewall-cmd', '--zone=' + zone, '--query-service=samba'], timeout=120)
    if check.returncode:
        raise ValueError('A liberação de Samba não foi confirmada nesta zona. Consulte o estado do firewall novamente.')
    return dict(text='Samba liberado na zona ' + zone + (', incluindo a configuração permanente.' if persist else ' até reiniciar ou recarregar o firewall.'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inspect', 'security', 'preview', 'hash', 'compatibility', 'diagnose', 'configure', 'run', 'versions', 'sharing', 'sharing-service', 'sharing-firewall'])
    parser.add_argument('path')
    parser.add_argument('--algorithm', choices=['sha256', 'sha512'], default='sha256')
    parser.add_argument('--environment')
    parser.add_argument('--zone')
    parser.add_argument('--persist', action='store_true')
    parser.add_argument('--authorize-firewall', action='store_true')
    args = parser.parse_args()
    actions = {'inspect': inspect, 'security': security, 'preview': recursive_preview,
               'compatibility': compatibility, 'versions': versions, 'sharing': sharing}
    try:
        if args.action == 'hash':
            result = hash_file(args.path, args.algorithm)
        elif args.action in ('diagnose', 'configure', 'run'):
            result = wine_action(args.path, args.environment, args.action)
        elif args.action == 'sharing-service':
            result = start_sharing_service(args.persist)
        elif args.action == 'sharing-firewall':
            result = allow_sharing_firewall(args.zone, args.persist)
        elif args.action == 'sharing':
            result = sharing(args.path, authorize_firewall=args.authorize_firewall)
        else:
            result = actions[args.action](args.path)
        emit(result)
        return 0
    except (OSError, ValueError, ImportError, subprocess.TimeoutExpired) as error:
        emit(dict(error=str(error)))
        return 1


if __name__ == '__main__':
    sys.exit(main())
