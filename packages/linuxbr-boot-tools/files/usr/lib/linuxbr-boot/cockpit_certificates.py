"""Validate and install a versioned TLS certificate for Cockpit."""

import base64
from datetime import datetime, timezone
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from tempfile import NamedTemporaryFile
from uuid import uuid4


FOLDER = Path('/etc/cockpit/ws-certs.d')
ENSURE = '/usr/lib/cockpit/cockpit-certificate-ensure'
PREFIX = '90-linuxbr-'
LIMIT = 65536
CERTIFICATE = rb'-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----'
PRIVATE_KEY = rb'\s*-----BEGIN (RSA PRIVATE KEY|EC PRIVATE KEY|PRIVATE KEY)-----\r?\n[A-Za-z0-9+/=\r\n]+-----END \1-----\s*'


def checked_name(value):
    try:
        return '-checkip', str(ipaddress.ip_address(value))
    except ValueError:
        labels = value.split('.')
        if len(value) <= 253 and all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                                     for label in labels):
            return '-checkhost', value
        raise ValueError('Informe o nome DNS ou endereço IP usado para acessar o Cockpit.') from None


def openssl(data, *argv):
    result = subprocess.run(['/usr/bin/openssl', *argv], input=data, capture_output=True, timeout=12,
                            env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise ValueError('O OpenSSL recusou o certificado ou a chave privada.')
    return result.stdout


def inspect_pair(chain, key, hostname):
    host_option, host = checked_name(hostname)
    if not 0 < len(chain) <= LIMIT or not re.fullmatch(rb'(?:\s*' + CERTIFICATE + rb')+\s*', chain):
        raise ValueError('Escolha uma cadeia PEM com o certificado do servidor seguido das intermediárias.')
    if not 0 < len(key) <= LIMIT or not re.fullmatch(PRIVATE_KEY, key):
        raise ValueError('Escolha uma chave privada PEM sem senha, compatível com o Cockpit.')
    certificates = re.findall(CERTIFICATE, chain)
    leaf = certificates[0]
    now = datetime.now(timezone.utc)
    for certificate in certificates:
        dates = openssl(certificate, 'x509', '-noout', '-dates', '-dateopt', 'iso_8601').decode('ascii')
        start, end = [datetime.fromisoformat(row.split('=', 1)[1].replace('Z', '+00:00'))
                      for row in dates.splitlines()]
        if not start <= now < end:
            raise ValueError('Um dos certificados está vencido ou ainda não entrou em validade.')
    result = openssl(leaf, 'x509', '-noout', host_option, host)
    if b'does match certificate' not in result:
        raise ValueError('O certificado não corresponde ao endereço informado.')
    public = openssl(leaf, 'x509', '-noout', '-pubkey')
    if openssl(key, 'pkey', '-pubout', '-passin', 'pass:') != public:
        raise ValueError('A chave privada não corresponde ao certificado do servidor.')
    return openssl(leaf, 'x509', '-noout', '-subject', '-issuer', '-dates',
                   '-fingerprint', '-sha256').decode('utf-8', errors='replace').strip()


def publish_file(path, data, mode):
    with NamedTemporaryFile(dir=path.parent, delete=False, prefix='.linuxbr-tls-') as stream:
        temp = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def install(chain, key, hostname, folder=FOLDER, ensure=ENSURE):
    if os.geteuid() != 0:
        raise PermissionError('A instalação exige autorização administrativa.')
    if not Path(ensure).is_file():
        raise ValueError('Instale a Central de Administração Remota primeiro.')
    inspect_pair(chain, key, hostname)
    for directory in (folder.parent, folder):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('O diretório de certificados precisa pertencer ao administrador.')
    fd = os.open(folder / '.linuxbr.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        names = {entry.name for entry in folder.iterdir() if entry.suffix in ('.cert', '.crt')}
        managed = re.compile(r'90-linuxbr-([0-9]{8})-[0-9a-f]{12}\.cert')
        revisions = [int(match[1]) for name in names if (match := managed.fullmatch(name))]
        revision = max(revisions, default=0) + 1
        if revision > 99_999_999:
            raise ValueError('O diretório atingiu o limite de revisões.')
        name = f'{PREFIX}{revision:08d}-{uuid4().hex[:12]}'
        cert_path = folder / (name + '.cert')
        key_path = folder / (name + '.key')
        if names and max(names) >= cert_path.name:
            raise ValueError('Já há um certificado com prioridade maior. Revise a configuração administrativa do Cockpit.')
        publish_file(key_path, key, 0o600)
        try:
            publish_file(cert_path, chain, 0o644)
            result = subprocess.run(
                [ensure, '--check'], env={**os.environ, 'XDG_CONFIG_DIRS': str(folder.parent.parent)},
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode or str(cert_path) not in result.stdout + result.stderr:
                raise ValueError('O Cockpit não confirmou a seleção do certificado novo.')
        except Exception:
            cert_path.unlink(missing_ok=True)
            key_path.unlink(missing_ok=True)
            raise
    return cert_path


def payload(chain, key, hostname):
    return json.dumps(dict(chain=base64.b64encode(chain).decode('ascii'),
                           key=base64.b64encode(key).decode('ascii'), hostname=hostname)).encode()


if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(180001)
        if len(raw) > 180000:
            raise ValueError('O pedido de instalação excede o tamanho permitido.')
        request = json.loads(raw)
        chain = base64.b64decode(request['chain'], validate=True)
        key = base64.b64decode(request['key'], validate=True)
        print(install(chain, key, request['hostname']))
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
