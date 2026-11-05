#!/usr/bin/env python3
"""Prepare a signed local publication and TLS files without changing the system."""
import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile


def run(*args):
    return subprocess.check_output(args, stderr=subprocess.PIPE)


def host_name(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError:
        pass
    if (len(value) > 253 or not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', value)
            or any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-')
                   for part in value.split('.'))):
        raise ValueError('Use um nome DNS ou IPv4 válido para o endereço do cliente.')
    return value.lower()


def prepare_tls(directory, hostname, addresses, reuse=False):
    directory = directory.resolve()
    try:
        ipaddress.ip_address(hostname)
        identity_check = '-verify_ip'
    except ValueError:
        identity_check = '-verify_hostname'
    if reuse:
        for name in ('ca.crt', 'server.crt', 'server.key'):
            path = directory / name
            if not path.is_file() or path.is_symlink():
                raise ValueError('Arquivos TLS ausentes ou com links. Não foi criado um certificado novo.')
        if (directory / 'server.key').stat().st_mode & 0o077:
            raise ValueError('A chave TLS existente precisa de permissão 0600.')
        run('openssl', 'verify', '-CAfile', str(directory / 'ca.crt'), '-purpose', 'sslserver',
            identity_check, hostname, str(directory / 'server.crt'))
        cert_key = run('openssl', 'x509', '-in', str(directory / 'server.crt'), '-pubkey', '-noout')
        private_key = run('openssl', 'pkey', '-in', str(directory / 'server.key'), '-pubout')
        if cert_key != private_key:
            raise ValueError('O certificado existente não corresponde à chave TLS.')
        return
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    dns = {'localhost'}
    ips = {'127.0.0.1'}
    try:
        ips.add(str(ipaddress.ip_address(hostname)))
    except ValueError:
        dns.add(hostname)
    for address in addresses:
        ips.add(str(ipaddress.ip_address(address)))
    alternatives = [f'DNS.{number} = {name}' for number, name in enumerate(sorted(dns), 1)]
    alternatives += [f'IP.{number} = {name}' for number, name in enumerate(sorted(ips), 1)]
    config = ('[req]\ndistinguished_name = dn\nprompt = no\n[dn]\nCN = Linux BR Local Repository\n'
              '[v3_ca]\nbasicConstraints = critical,CA:TRUE,pathlen:0\nkeyUsage = critical,keyCertSign,cRLSign\n'
              'subjectKeyIdentifier = hash\nauthorityKeyIdentifier = keyid:always\n'
              '[server_cert]\nbasicConstraints = critical,CA:FALSE\nkeyUsage = critical,digitalSignature,keyEncipherment\n'
              'extendedKeyUsage = serverAuth\nsubjectAltName = @names\nsubjectKeyIdentifier = hash\nauthorityKeyIdentifier = keyid,issuer\n'
              '[names]\n' + '\n'.join(alternatives) + '\n')
    with tempfile.TemporaryDirectory(prefix='linuxbr-tls-') as temporary:
        settings = Path(temporary) / 'openssl.cnf'
        settings.write_text(config, encoding='utf-8')
        run('openssl', 'req', '-new', '-x509', '-nodes', '-newkey', 'rsa:3072', '-sha256', '-days', '1825',
            '-config', str(settings), '-extensions', 'v3_ca', '-subj', '/CN=Linux BR Local Authority',
            '-keyout', str(directory / 'ca.key'), '-out', str(directory / 'ca.crt'))
        run('openssl', 'req', '-new', '-nodes', '-newkey', 'rsa:3072', '-sha256', '-config', str(settings),
            '-keyout', str(directory / 'server.key'), '-out', str(Path(temporary) / 'server.csr'))
        run('openssl', 'x509', '-req', '-in', str(Path(temporary) / 'server.csr'), '-CA', str(directory / 'ca.crt'),
            '-CAkey', str(directory / 'ca.key'), '-set_serial', str(int.from_bytes(os.urandom(16), 'big')),
            '-days', '397', '-sha256', '-extfile', str(settings), '-extensions', 'server_cert',
            '-out', str(directory / 'server.crt'))
    for name in ('ca.key', 'server.key'):
        (directory / name).chmod(0o600)
    run('openssl', 'verify', '-CAfile', str(directory / 'ca.crt'), '-purpose', 'sslserver',
        identity_check, hostname, str(directory / 'server.crt'))


def prepare(packages, output, fingerprint, tls_dir, hostname='localhost', port=8443, addresses=(), reuse_tls=False, acceptance_report=None):
    hostname = host_name(hostname)
    if not 1 <= port <= 65535:
        raise ValueError('Use uma porta entre 1 e 65535.')
    output, tls_dir = output.resolve(), tls_dir.resolve()
    if output.exists():
        raise ValueError('A publicação já existe. Use uma saída nova para preservar a anterior.')
    if output == tls_dir or output.is_relative_to(tls_dir) or tls_dir.is_relative_to(output):
        raise ValueError('Separe o diretório público dos arquivos TLS privados.')
    for name in ('openssl', 'gpg', 'dpkg-deb', 'dpkg-scanpackages', 'php'):
        if not shutil.which(name):
            raise ValueError('Dependência ausente: ' + name)
    # Package and signature checks happen before creating TLS files.
    if not re.fullmatch(r'[A-Fa-f0-9]{40,64}', fingerprint):
        raise ValueError('Informe a impressão digital completa da chave de assinatura externa.')
    if not run('gpg', '--batch', '--with-colons', '--list-secret-keys', fingerprint):
        raise ValueError('A chave privada de assinatura não está disponível no GnuPG externo.')
    if not packages.is_dir() or not list(packages.glob('*.deb')):
        raise ValueError('Escolha uma pasta com os pacotes DEB revisados.')
    prepare_tls(tls_dir, hostname, addresses, reuse_tls)
    spec = importlib.util.spec_from_file_location('local_repository_build', Path(__file__).with_name('build-repository.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base_url = f'https://{hostname}:{port}'
    count = module.build(packages, output, fingerprint, base_url, acceptance_report=acceptance_report)
    shutil.copyfile(tls_dir / 'ca.crt', output / 'linuxbr-local-ca.crt')
    shutil.copyfile(output / 'linuxbr-archive-keyring.gpg', output / 'client-archive-keyring.gpg')
    (output / 'client.sources').write_text('Types: deb\nURIs: ' + base_url + '\nSuites: trixie\nComponents: main\n'
        'Architectures: amd64\nSigned-By: /usr/share/keyrings/linuxbr-local-archive-keyring.gpg\n', encoding='utf-8')
    shutil.copyfile(output / 'client.sources', output / 'linuxbr.sources')
    # APT's per-host syntax keeps this CA scoped to the selected mirror.
    (output / 'client-https.conf').write_text(
        f'Acquire::https::{hostname}::CaInfo "/etc/apt/certs/linuxbr-local-ca.crt";\n'
        f'Acquire::https::{hostname}::Verify-Peer "true";\n'
        f'Acquire::https::{hostname}::Verify-Host "true";\n', encoding='utf-8')
    shutil.copyfile(output / 'linuxbr.pref', output / 'client.pref')
    ca_hash = hashlib.sha256((output / 'linuxbr-local-ca.crt').read_bytes()).hexdigest()
    archive_hash = hashlib.sha256((output / 'client-archive-keyring.gpg').read_bytes()).hexdigest()
    (output / 'client-readme.txt').write_text(
        f'Repositório local Linux BR: {base_url}\nPacotes: {count}\n'
        f'Chave APT (impressão digital): {fingerprint.upper()}\n'
        f'SHA256 linuxbr-local-ca.crt: {ca_hash}\nSHA256 client-archive-keyring.gpg: {archive_hash}\n\n'
        'Transfira a CA e a chave por um canal já confiável e confira estas impressões digitais.\n'
        'Não obtenha a confiança inicial aceitando um certificado desconhecido no navegador.\n'
        'Os arquivos client.* são exemplos para revisão e instalação explícita. Nada foi ativado no cliente.\n'
        'Use a documentação REPOSITORIO-LOCAL-PHP.md para instalar os arquivos e validar com apt-get update.\n', encoding='utf-8')
    return {'status': 'prepared', 'packages': count, 'base_url': base_url, 'ca_sha256': ca_hash,
            'archive_keyring_sha256': archive_hash, 'client_activated': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preparar repositório APT HTTPS local com servidor PHP, sem ativar serviços nem fontes APT.')
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fingerprint', required=True)
    parser.add_argument('--tls-dir', type=Path, required=True)
    parser.add_argument('--hostname', default='localhost')
    parser.add_argument('--port', type=int, default=8443)
    parser.add_argument('--address', action='append', default=[])
    parser.add_argument('--reuse-tls', action='store_true')
    parser.add_argument('--acceptance-report', type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.packages, args.output, args.fingerprint, args.tls_dir, args.hostname,
                         args.port, args.address, args.reuse_tls, args.acceptance_report)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print('Iniciar somente neste computador:')
        print(shlex.join(['php', str(Path(__file__).with_name('repository-server.php').resolve()),
            '--root', str(args.output.resolve()), '--cert', str(args.tls_dir.resolve() / 'server.crt'),
            '--key', str(args.tls_dir.resolve() / 'server.key'), '--port', str(args.port)]))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, ('Falha em uma ferramenta externa. Confira as dependências e a chave de assinatura.'
                        if isinstance(error, subprocess.CalledProcessError) else str(error)) + '\n')
