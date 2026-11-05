#!/usr/bin/env python3
"""Actual APT/TLS integration in temporary directories, with no installed source."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_setup', ROOT / 'scripts/setup-local-repository.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


def command(*args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


with tempfile.TemporaryDirectory(prefix='linuxbr-local-apt-') as directory:
    root = Path(directory); root.chmod(0o755)
    home = root / 'gnupg'; home.mkdir(mode=0o700)
    previous = os.environ.get('GNUPGHOME'); os.environ['GNUPGHOME'] = str(home)
    server = None
    try:
        result = command('gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                         '--quick-generate-key', 'Linux BR teste local HTTPS', 'ed25519', 'sign', '1d')
        assert result.returncode == 0, result.stderr
        listing = command('gpg', '--batch', '--with-colons', '--list-secret-keys').stdout
        fingerprint = next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
        package = root / 'package'; (package / 'DEBIAN').mkdir(parents=True)
        (package / 'DEBIAN/control').write_text('Package: linuxbr-local-fixture\nVersion: 0.7.0~beta1\nArchitecture: all\nMaintainer: Test <test@example.invalid>\nDescription: Local HTTPS integration fixture\n')
        packages = root / 'packages'; packages.mkdir()
        assert command('dpkg-deb', '--build', str(package), str(packages / 'fixture.deb')).returncode == 0
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0)); port = reservation.getsockname()[1]
        public = root / 'public'; tls = root / 'tls'
        prepared = setup.prepare(packages, public, fingerprint, tls, port=port)
        assert prepared['packages'] == 1 and not prepared['client_activated']
        assert (tls / 'server.key').stat().st_mode & 0o777 == 0o600
        assert not list(public.rglob('*.key'))
        assert 'Signed-By: /usr/share/keyrings/linuxbr-local-archive-keyring.gpg' in (public / 'client.sources').read_text()
        assert 'Acquire::https::localhost::CaInfo' in (public / 'client-https.conf').read_text()
        setup.prepare_tls(tls, 'localhost', (), reuse=True)
        try: setup.prepare_tls(tls, 'wrong.invalid', (), reuse=True)
        except subprocess.CalledProcessError: pass
        else: raise AssertionError('Reutilização aceitou um certificado para outro nome.')
        print('PASS: preparação, SAN localhost/127.0.0.1, chave externa, TLS reutilizável e cliente não ativado.', flush=True)
        log = root / 'server.log'
        with log.open('w') as output:
            server = subprocess.Popen(['php', str(ROOT / 'scripts/repository-server.php'), '--root', str(public),
                '--cert', str(tls / 'server.crt'), '--key', str(tls / 'server.key'), '--port', str(port)],
                stdout=output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and '"ready"' not in log.read_text():
            assert server.poll() is None, log.read_text(); time.sleep(.05)
        assert '"ready"' in log.read_text(), log.read_text()
        apt = root / 'apt'; apt.mkdir()
        for folder in ('lists/partial', 'cache/archives/partial', 'parts', 'config-parts', 'downloads'):
            (apt / folder).mkdir(parents=True)
        (apt / 'status').touch(); (apt / 'empty.conf').touch()
        source = (public / 'client.sources').read_text().replace('/usr/share/keyrings/linuxbr-local-archive-keyring.gpg', str(public / 'client-archive-keyring.gpg'))
        (apt / 'linuxbr.sources').write_text(source)
        config = (public / 'client-https.conf').read_text().replace('/etc/apt/certs/linuxbr-local-ca.crt', str(tls / 'ca.crt'))
        config += (f'Dir::Etc::parts "{apt}/config-parts";\nDir::Etc::main "{apt}/empty.conf";\n'
                   f'Dir::Etc::sourcelist "{apt}/linuxbr.sources";\nDir::Etc::sourceparts "{apt}/parts";\n'
                   f'Dir::State::lists "{apt}/lists";\nDir::State::status "{apt}/status";\nDir::Cache "{apt}/cache";\n'
                   'Debug::NoLocking "true";\nAPT::Sandbox::User "root";\nAPT::Architecture "amd64";\n'
                   'APT::Update::Error-Mode "any";\nAcquire::Retries "0";\nAcquire::https::Timeout "10";\n')
        config += 'Acquire::https::Proxy::localhost "DIRECT";\n'
        (apt / 'apt.conf').write_text(config)
        env = dict(os.environ, APT_CONFIG=str(apt / 'apt.conf'), LC_ALL='C')
        def apt_run(*args, folder=None):
            return command('apt-get', *args, env=env, cwd=folder or apt / 'downloads', timeout=60)
        def clear_lists():
            for path in (apt / 'lists').iterdir():
                if path.is_file(): path.unlink()
        result = apt_run('update')
        assert result.returncode == 0 and 'Err:' not in result.stdout, result.stdout + result.stderr
        result = apt_run('download', 'linuxbr-local-fixture')
        assert result.returncode == 0, result.stdout + result.stderr
        downloaded = next((apt / 'downloads').glob('*.deb'))
        assert downloaded.read_bytes() == (packages / 'fixture.deb').read_bytes()
        print('PASS: APT validou TLS e Signed-By e baixou pacote com hash correspondente.', flush=True)
        # A different CA is rejected with peer/host verification left enabled.
        other_tls = root / 'other-tls'; setup.prepare_tls(other_tls, 'localhost', ())
        wrong_config = config.replace(str(tls / 'ca.crt'), str(other_tls / 'ca.crt'))
        (apt / 'apt.conf').write_text(wrong_config); clear_lists()
        result = apt_run('update')
        assert result.returncode != 0, 'APT aceitou uma autoridade TLS desconhecida.'
        (apt / 'apt.conf').write_text(config)
        print('PASS: APT recusou autoridade TLS desconhecida sem desativar verificação.', flush=True)
        signed = public / 'dists/trixie/InRelease'; original = signed.read_bytes()
        signed.write_bytes(original.replace(b'Origin: LinuxBR', b'Origin: Adulterado'))
        clear_lists(); result = apt_run('update')
        assert result.returncode != 0, 'APT aceitou metadados com assinatura adulterada.'
        signed.write_bytes(original)
        print('PASS: APT recusou metadados alterados após a assinatura.', flush=True)
        clear_lists(); result = apt_run('update')
        assert result.returncode == 0, result.stdout + result.stderr
        deb = next((public / 'pool/main').glob('*.deb')); deb.write_bytes(b'conteudo adulterado\n')
        tampered_download = apt / 'tampered-download'; tampered_download.mkdir()
        result = apt_run('download', 'linuxbr-local-fixture', folder=tampered_download)
        assert result.returncode != 0, 'APT aceitou um pacote cujo hash foi adulterado.'
        print('PASS: APT recusou pacote alterado após a indexação.', flush=True)
        try: setup.prepare(packages, public, fingerprint, tls, port=port, reuse_tls=True)
        except ValueError: pass
        else: raise AssertionError('Publicação anterior foi sobrescrita.')
        print(json.dumps({'status':'PASS','tls':True,'signed_by':True,'download':True,
            'unknown_ca_rejected':True,'tampered_metadata_rejected':True,'tampered_package_rejected':True,
            'existing_output_preserved':True,'client_activated':False}), flush=True)
    finally:
        if server is not None:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
        subprocess.run(['gpgconf', '--kill', 'gpg-agent'], capture_output=True)
        if previous is None: os.environ.pop('GNUPGHOME', None)
        else: os.environ['GNUPGHOME'] = previous
