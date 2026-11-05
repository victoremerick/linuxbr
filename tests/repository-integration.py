#!/usr/bin/env python3
"""Verify APT signatures and index tamper rejection in an isolated directory."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repository',ROOT/'scripts/build-repository.py')
repository=importlib.util.module_from_spec(spec);spec.loader.exec_module(repository)


with tempfile.TemporaryDirectory(prefix='linuxbr-repository-') as directory:
    root=Path(directory);root.chmod(0o755)
    home=root/'gnupg';home.mkdir(mode=0o700);os.environ['GNUPGHOME']=str(home)
    subprocess.run(['gpg','--batch','--pinentry-mode','loopback','--passphrase','',
                    '--quick-generate-key','Linux BR teste local','ed25519','sign','1d'],check=True,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    listing=subprocess.check_output(['gpg','--batch','--with-colons','--list-secret-keys'],text=True)
    fingerprint=next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
    output=root/'repository'
    count=repository.build(Path(sys.argv[1]),output,fingerprint,'https://updates.example.org/linuxbr')
    assert count>0
    subprocess.run(['gpgv','--keyring',str(output/'linuxbr-archive-keyring.gpg'),
                    str(output/'dists/trixie/InRelease')],check=True)
    apt=root/'apt';apt.mkdir()
    (apt/'lists/partial').mkdir(parents=True);(apt/'cache/archives/partial').mkdir(parents=True)
    (apt/'sources.list').write_text(f'deb [signed-by={output}/linuxbr-archive-keyring.gpg] file:{output} trixie main\n')
    (apt/'status').touch();(apt/'parts').mkdir()
    command=['apt-get','-o','Debug::NoLocking=true','-o','APT::Sandbox::User=root',
             '-o','APT::Architecture=amd64','-o',f'Dir::Etc::sourcelist={apt}/sources.list',
             '-o',f'Dir::Etc::sourceparts={apt}/parts','-o',f'Dir::State::lists={apt}/lists',
             '-o',f'Dir::State::status={apt}/status','-o',f'Dir::Cache={apt}/cache','update']
    subprocess.run(command,check=True)
    print('PASS: APT aceitou o repositório com a chave vinculada à fonte.',flush=True)
    for path in (output/'dists/trixie/main/binary-amd64').iterdir():path.write_bytes(b'alterado\n')
    for path in (apt/'lists').iterdir():
        if path.is_file():path.unlink()
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode!=0, 'APT aceitou índices alterados'
    print('PASS: APT rejeitou índices alterados após a assinatura.',flush=True)
    try:repository.build(Path(sys.argv[1]),output,fingerprint)
    except ValueError:pass
    else:raise AssertionError('Sobrescrita do repositório existente foi permitida')
    print('PASS: publicação anterior preservada; chave privada temporária descartada ao finalizar.')
