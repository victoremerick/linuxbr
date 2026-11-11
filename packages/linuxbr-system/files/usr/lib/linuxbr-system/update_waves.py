"""Authorize managed APT archive batches against a signed wave manifest."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from http.client import HTTPSConnection, HTTPException
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import ssl
import stat
import subprocess
import sys
from urllib.parse import urlsplit


DIRECTORY = Path('/etc/linuxbr')
CONFIG = DIRECTORY / 'update-waves.json'
MANIFEST = DIRECTORY / 'update-wave.gpg'
KEYRING = DIRECTORY / 'update-wave-keyring.gpg'
MAX_MANIFEST = 1024 * 1024
SHA256 = re.compile(r'[0-9a-f]{64}')
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
TOKEN = re.compile(r'[A-Za-z0-9_-]{43}')
CLIENT_ROUTES = {
    ('POST', '/v1/manifest'), ('POST', '/v1/inventory'), ('POST', '/v1/result'),
    ('GET', '/v1/diagnostic'), ('POST', '/v1/diagnostic'), ('POST', '/v1/policy'),
}


def trusted_file(path, private=False):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                info.st_mode & (0o077 if private else 0o022) or info.st_size > MAX_MANIFEST):
            raise ValueError('Arquivo de atualização gerenciada inválido.')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            data = stream.read(MAX_MANIFEST + 1)
        if len(data) > MAX_MANIFEST:
            raise ValueError('Arquivo de atualização gerenciada grande demais.')
        return data
    finally:
        os.close(descriptor)


def verify_manifest(manifest, organization, wave, archives, now):
    if (not isinstance(manifest, dict) or type(manifest.get('schema')) is not int
            or manifest['schema'] != 1):
        raise ValueError('Formato de autorização de atualização inválido.')
    revision = manifest.get('revision')
    if not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', revision):
        raise ValueError('Revisão de atualização inválida.')
    if manifest.get('organization') != organization:
        raise ValueError('A autorização pertence a outra organização.')
    try:
        issued = datetime.fromisoformat(manifest['issued_at'])
        expires = datetime.fromisoformat(manifest['expires_at'])
        if issued.tzinfo is None or expires.tzinfo is None:
            raise ValueError('Fuso horário obrigatório.')
    except (KeyError, ValueError, TypeError, OverflowError) as error:
        raise ValueError('Validade da autorização inválida.') from error
    if not issued <= now < expires or expires - issued > timedelta(hours=24):
        raise ValueError('Autorização de atualização vencida ou fora da janela.')
    waves = manifest.get('waves')
    if not isinstance(waves, dict) or waves.get(wave) != 'approved':
        raise ValueError('A revisão está pendente ou pausada para esta onda.')
    expected = manifest.get('archives')
    if (not isinstance(expected, list) or not expected or
            any(not isinstance(item, str) or not SHA256.fullmatch(item) for item in expected) or
            len(set(expected)) != len(expected) or sorted(expected) != sorted(archives)):
        raise ValueError('Os pacotes da transação diferem da revisão aprovada.')
    return revision


def read_config():
    try:
        CONFIG.lstat()
    except FileNotFoundError:
        return None
    config = json.loads(trusted_file(CONFIG))
    if not isinstance(config, dict) or type(config.get('schema')) is not int or config['schema'] != 1:
        raise ValueError('Configuração das ondas inválida.')
    if config.get('wave') not in ('pilot', 'general') or not config.get('organization'):
        raise ValueError('Onda ou organização inválida.')
    if not isinstance(config['organization'], str):
        raise ValueError('Organização inválida.')
    if 'endpoint' in config:
        if not IDENTIFIER.fullmatch(config['organization']):
            raise ValueError('Organização inválida.')
        device = config.get('device')
        if not isinstance(device, str) or not IDENTIFIER.fullmatch(device):
            raise ValueError('Dispositivo gerenciado inválido.')
        endpoint(config)
    return config


def endpoint(config):
    value = config.get('endpoint')
    if not isinstance(value, str) or len(value) > 256 or any(c.isspace() for c in value):
        raise ValueError('Endereço de atualização inválido.')
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username is not None or url.password is not None
            or url.path not in ('', '/') or url.query or url.fragment):
        raise ValueError('Use o endereço HTTPS do serviço de atualização.')
    port = url.port
    if port == 0:
        raise ValueError('Porta HTTPS inválida.')
    return url.hostname, 443 if port is None else port


def config_path(config, field, default=None):
    value = config.get(field, default)
    if not isinstance(value, str):
        raise ValueError('Caminho de configuração inválido.')
    path = Path(value)
    if path.parent != DIRECTORY or path.name in ('', '.', '..'):
        raise ValueError('O arquivo de cadastro deve estar em /etc/linuxbr.')
    return path


def request(config, method, path, payload=None):
    if (method, path) not in CLIENT_ROUTES:
        raise ValueError('Operação do serviço de atualização inválida.')
    host, port = endpoint(config)
    token_path = config_path(config, 'token_file', str(DIRECTORY / 'update-wave-token'))
    token = trusted_file(token_path, private=True).decode('ascii').strip()
    if not TOKEN.fullmatch(token):
        raise ValueError('Credencial do dispositivo inválida.')
    if 'ca_file' in config:
        ca = trusted_file(config_path(config, 'ca_file')).decode('ascii')
        context = ssl.create_default_context(cadata=ca)
    else:
        context = ssl.create_default_context()
    body = json.dumps(payload, allow_nan=False).encode('utf-8') if payload is not None else None
    if body is not None and len(body) > 16384:
        raise ValueError('Relatório excede o limite do serviço.')
    connection = HTTPSConnection(host, port, context=context, timeout=8)
    try:
        connection.request(method, path, body=body,
                           headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Serviço da organização recusou a operação (HTTP %d).' % response.status)
        result = response.read(MAX_MANIFEST + 1)
        if len(result) > MAX_MANIFEST:
            raise ValueError('Resposta do serviço de atualização grande demais.')
        return result
    except (OSError, HTTPException) as error:
        raise ValueError('Não foi possível contactar o serviço da organização por HTTPS.') from error
    finally:
        connection.close()


def request_json(config, method, path, payload=None):
    result = json.loads(request(config, method, path, payload))
    if not isinstance(result, dict):
        raise ValueError('Resposta do serviço de atualização inválida.')
    return result


def inventory():
    try:
        release = subprocess.check_output(['/usr/bin/dpkg-query', '-W', '-f=${Version}', 'linuxbr-release'],
                                          stderr=subprocess.DEVNULL, timeout=3, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        release = ''
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+~:-]{0,79}', release):
        release = None
    return {'release': release, 'free_bytes': shutil.disk_usage('/').free,
            'reboot_pending': Path('/run/reboot-required').exists()}


def decode_manifest(signed):
    trusted_file(KEYRING)
    verified = subprocess.run(['/usr/bin/gpgv', '--keyring', str(KEYRING), '--output', '-', '-'],
                              input=signed, capture_output=True, timeout=10)
    if verified.returncode or len(verified.stdout) > MAX_MANIFEST:
        raise ValueError('A assinatura da revisão de atualização é inválida.')
    return json.loads(verified.stdout)


def archive_digest(archive):
    """Keep the checked archive protected until APT opens it for dpkg."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    folder = os.open('/', flags | os.O_DIRECTORY)
    try:
        for name in archive.parts[1:-1]:
            if name == '..':
                raise ValueError('Caminho de pacote gerenciado inválido.')
            current = os.open(name, flags | os.O_DIRECTORY, dir_fd=folder)
            os.close(folder)
            folder = current
            info = os.fstat(folder)
            if info.st_uid != 0 or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
                raise ValueError('Use um diretório protegido pela administração para o pacote gerenciado.')
        descriptor = os.open(archive.name, flags | os.O_NONBLOCK, dir_fd=folder)
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError('O pacote gerenciado deve pertencer à administração e estar protegido contra escrita.')
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    finally:
        os.close(folder)


def authorize(lines):
    config = read_config()
    if config is None:
        return None
    wave, organization = config['wave'], config['organization']
    archives = []
    for line in lines:
        archive = Path(line.strip())
        if not archive.is_absolute() or archive.suffix != '.deb':
            raise ValueError('O APT enviou uma operação não reconhecida para a atualização gerenciada.')
        archives.append(archive_digest(archive))
    if 'endpoint' in config:
        nonce = secrets.token_hex(32)
        manifest = decode_manifest(request(config, 'POST', '/v1/manifest',
                                           {'nonce': nonce, 'inventory': inventory()}))
        if not isinstance(manifest, dict) or (manifest.get('nonce'), manifest.get('device'),
                manifest.get('wave')) != (nonce, config['device'], wave):
            raise ValueError('A autorização recebida pertence a outra solicitação ou dispositivo.')
    else:
        manifest = decode_manifest(trusted_file(MANIFEST))
    return verify_manifest(manifest, organization, wave, archives, datetime.now(timezone.utc))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Consultar o serviço de ondas do Linux BR')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('heartbeat')
    result = commands.add_parser('result')
    result.add_argument('revision')
    result.add_argument('state', choices=('completed', 'failed', 'restored'))
    args = parser.parse_args(argv)
    try:
        config = read_config()
        if args.action == 'heartbeat':
            if config and 'endpoint' in config:
                request_json(config, 'POST', '/v1/inventory', inventory())
        else:
            if not config or 'endpoint' not in config or not IDENTIFIER.fullmatch(args.revision):
                raise ValueError('Revise o cadastro e o identificador da revisão.')
            request_json(config, 'POST', '/v1/result',
                         {'revision': args.revision, 'state': args.state})
    except (OSError, ValueError) as error:
        print('Linux BR: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
