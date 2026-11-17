"""Allow one approved ISO attachment by its named operator before expiration."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import sys
import syslog
import tempfile
import time
from uuid import UUID
import xml.etree.ElementTree as ET

MEDIA = Path('/var/lib/linuxbr/vm-approved-media')
GRANTS = Path('/var/lib/linuxbr/vm-media-grants')
ISO = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,159}\.iso', re.I)
SHA256 = re.compile(r'[a-f0-9]{64}')
CODE = re.compile(r'[a-zA-Z0-9_-]{32}')
MAX_ISO = 64 * 1024 ** 3
DENIED = 'Código inválido, usado, expirado ou atribuído a outra conta.'


def protected_directory(path, private=False):
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        mask = 0o077 if private and item == path else 0o022
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & mask:
            raise ValueError('Diretório de delegação sem proteção administrativa.')


@contextmanager
def locked():
    GRANTS.mkdir(parents=True, mode=0o700, exist_ok=True)
    protected_directory(GRANTS, private=True)
    lock = os.open(GRANTS / '.lock', os.O_NOFOLLOW | os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
    finally:
        os.close(lock)


def fingerprint(path):
    if path.parent != MEDIA or not ISO.fullmatch(path.name):
        raise ValueError(f'Coloque a ISO aprovada em {MEDIA} e use somente seu nome.')
    try:
        protected_directory(MEDIA)
        fd = os.open(path, os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY)
    except FileNotFoundError:
        raise ValueError(f'Mídia aprovada ausente em {MEDIA}.') from None
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_mode & 0o022 or
                not 32774 <= before.st_size <= MAX_ISO):
            raise ValueError('A ISO precisa ser um arquivo com propriedade administrativa.')
        stream.seek(16 * 2048 + 1)
        if stream.read(5) != b'CD001':
            raise ValueError('A imagem selecionada não é ISO 9660.')
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = path.lstat()
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(after, key) != getattr(before, key) for key in keys):
            raise ValueError('A imagem mudou durante a conferência.')
        return digest


def path_for(code):
    if not CODE.fullmatch(code):
        raise ValueError(DENIED)
    return GRANTS / (hashlib.sha256(code.encode()).hexdigest() + '.json')


def write(path, grant):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=GRANTS, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(grant, stream)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def audit(action, grant):
    syslog.openlog('linuxbr-vm-media', facility=syslog.LOG_AUTHPRIV)
    syslog.syslog(syslog.LOG_NOTICE, f"{action} uid={grant['uid']} vm={grant['vm']} sha256={grant['sha256']}")


@contextmanager
def connect():
    try:
        import libvirt
    except ImportError:
        raise ValueError('Ative o recurso de virtualização neste hospedeiro.') from None
    libvirt.registerErrorHandler(lambda *_: None, None)
    connection = libvirt.open('qemu:///system')
    if connection is None:
        raise ValueError('O serviço de virtualização do hospedeiro está indisponível.')
    try:
        yield connection
    finally:
        connection.close()


def dvd(domain, device=None):
    if not domain.isPersistent() or domain.isActive() or domain.hasManagedSaveImage(0):
        raise ValueError('Use uma VM persistente e desligada, sem estado salvo.')
    root = ET.fromstring(domain.XMLDesc(2))
    choices = []
    for disk in root.findall("devices/disk[@device='cdrom'][@type='file']"):
        target = disk.find('target')
        if (target is not None and target.get('dev') and disk.find('readonly') is not None
                and (device is None or target.get('dev') == device)):
            choices.append((target.get('dev'), disk))
    if len(choices) != 1:
        raise ValueError('Configure um único leitor de mídia ISO de arquivo nesta VM.')
    return choices[0]


def approvals(iso_name):
    try:
        protected_directory(MEDIA)
        entries = sorted(MEDIA.iterdir())
    except FileNotFoundError:
        raise ValueError(f'Prepare o diretório de imagens autorizadas em {MEDIA}.') from None
    if not iso_name:
        result = []
        for path in entries:
            try:
                mode = path.lstat()
                if (ISO.fullmatch(path.name) and stat.S_ISREG(mode.st_mode) and
                        mode.st_uid == 0 and not mode.st_mode & 0o022):
                    result.append(path.name)
            except OSError:
                continue
        return result[:100]
    return fingerprint(MEDIA / iso_name)


def issue(operator, vm, iso_name, sha256, hours):
    if not 1 <= hours <= 168 or not SHA256.fullmatch(sha256):
        raise ValueError('Informe o SHA-256 e uma validade de 1 a 168 horas.')
    operator = pwd.getpwnam(operator)
    if operator.pw_uid < 1000 or operator.pw_uid >= 65000:
        raise ValueError('Escolha um operador com conta de usuário neste hospedeiro.')
    identifier = str(UUID(vm))
    with connect() as connection:
        domain = connection.lookupByUUIDString(identifier)
        device, _ = dvd(domain)
        name = domain.name()
    if not secrets.compare_digest(approvals(iso_name), sha256):
        raise ValueError('O SHA-256 informado não corresponde à ISO aprovada.')
    code = secrets.token_urlsafe(24)
    expires = int(time.time()) + hours * 3600
    grant = {'uid': operator.pw_uid, 'operator': operator.pw_name, 'vm': identifier, 'name': name,
             'device': device, 'sha256': sha256, 'iso': iso_name, 'expires': expires, 'used': False}
    with locked():
        write(path_for(code), grant)
    audit('emitido', grant)
    return {'code': code, 'expires': datetime.fromtimestamp(expires, timezone.utc).isoformat()}


def authorized(grant, uid, now):
    return (isinstance(grant, dict) and grant.get('uid') == uid and grant.get('used') is False
            and isinstance(grant.get('expires'), int) and now < grant['expires'])


def redeem(code, uid):
    with locked():
        path = path_for(code)
        try:
            grant = json.loads(path.read_text(encoding='utf-8'))
            if not authorized(grant, uid, time.time()) or pwd.getpwuid(uid).pw_name != grant['operator']:
                raise ValueError(DENIED)
        except (OSError, UnicodeError, KeyError, ValueError):
            raise ValueError(DENIED) from None
        image = MEDIA / grant['iso']
        if not secrets.compare_digest(fingerprint(image), grant['sha256']):
            raise ValueError('O conteúdo da ISO aprovada mudou. Solicite uma nova autorização.')
        with connect() as connection:
            domain = connection.lookupByUUIDString(grant['vm'])
            if domain.name() != grant['name']:
                raise ValueError('A identidade da VM mudou. Solicite uma nova autorização.')
            _, disk = dvd(domain, grant['device'])
            if not authorized(grant, uid, time.time()):
                raise ValueError(DENIED)
            for source in disk.findall('source'):
                disk.remove(source)
            disk.insert(1, ET.Element('source', file=str(image)))
            driver = disk.find('driver')
            if driver is not None:
                driver.set('type', 'raw')
            domain.updateDeviceFlags(ET.tostring(disk, encoding='unicode'), 2)
        grant['used'] = True
        write(path, grant)
    audit('utilizado', grant)


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('images')
    grant = actions.add_parser('issue')
    for key in ('operator', 'vm', 'image', 'sha256'):
        grant.add_argument(key)
    grant.add_argument('hours', type=int)
    actions.add_parser('redeem')
    actions.add_parser('revoke')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'Execute a operação de mídia pelo aplicativo Linux BR ou com pkexec.\n')
    try:
        if args.action == 'images':
            print(json.dumps(approvals('')))
        elif args.action == 'issue':
            if not ISO.fullmatch(args.image):
                raise ValueError('Informe o nome de um arquivo ISO aprovado.')
            print(json.dumps(issue(args.operator, args.vm, args.image, args.sha256.lower(), args.hours)))
        else:
            code = sys.stdin.readline(100).strip()
            if args.action == 'redeem':
                uid = int(os.environ.get('PKEXEC_UID', '0'))
                if uid < 1000:
                    raise ValueError('Abra a autorização pela sessão do operador.')
                redeem(code, uid)
                print('ISO autorizada anexada ao leitor da VM.')
            else:
                with locked():
                    path = path_for(code)
                    record = json.loads(path.read_text())
                    path.unlink()
                    audit('revogado', record)
                print('Autorização revogada.')
        return 0
    except (OSError, UnicodeError, KeyError, ValueError) as error:
        message = 'A conta ou a autorização não foi localizada.' if isinstance(error, KeyError) else str(error)
        print(message, file=sys.stderr)
    except Exception:
        print('O serviço de virtualização não confirmou a operação.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
