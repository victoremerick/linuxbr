#!/usr/bin/python3
"""Review locally verifiable update outcomes before reporting to the organization."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from snapshot_service import (ARCHITECTURE, DPKG_STATUS, LIVE, PACKAGE, REVISION, STATE, VERSION,
                              held_revisions, read_json, restored_revisions)
from update_waves import SHA256, read_config, request_json


@contextmanager
def idle_dpkg():
    descriptors = []
    try:
        for name in ('lock-frontend', 'lock'):
            descriptor = os.open(Path('/var/lib/dpkg') / name, os.O_RDWR | os.O_NOFOLLOW)
            descriptors.append(descriptor)
            fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise ValueError('Aguarde a conclusão do gerenciador de pacotes.') from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def installed_count(targets):
    if not isinstance(targets, list) or not targets or len(targets) > 4096:
        raise ValueError('O registro da atualização não contém o lote conferível.')
    expected = set()
    for target in targets:
        if (not isinstance(target, dict) or set(target) != {'package', 'version', 'architecture'}
                or any(not isinstance(target[field], str) or not pattern.fullmatch(target[field])
                       for field, pattern in (('package', PACKAGE), ('version', VERSION),
                                              ('architecture', ARCHITECTURE)))):
            raise ValueError('O lote registrado tem metadados inválidos.')
        expected.add((target['package'], target['version'], target['architecture']))
    if len(expected) != len(targets):
        raise ValueError('O lote registrado tem pacotes repetidos.')
    rows = subprocess.check_output(['/usr/bin/dpkg-query', '-W',
        '-f=${db:Status-Status}\t${Package}\t${Version}\t${Architecture}\n'], text=True, timeout=15)
    installed = {tuple(row.split('\t')[1:]) for row in rows.splitlines() if row.startswith('installed\t')}
    return len(expected & installed)


def review(transaction, holds, restored, reboot_pending, package_audit, database_sha256):
    outcomes = []
    if not package_audit and not reboot_pending:
        outcomes.extend({'revision': revision, 'state': 'restored'} for revision in holds if revision in restored)
    revision = transaction.get('revision')
    if not isinstance(revision, str) or not REVISION.fullmatch(revision) or revision in holds:
        if outcomes:
            summary = 'Confira o funcionamento do sistema antes de informar a restauração.'
        elif holds:
            summary = 'Há revisões suspensas. Confira o resultado da recuperação e os pacotes do sistema.'
        else:
            summary = 'Nenhuma revisão gerenciada foi registrada neste computador.'
        return {'summary': summary,
                'outcomes': outcomes}
    if transaction.get('status') == 'failed':
        return {'summary': 'A proteção da revisão ' + revision + ' falhou antes da instalação.',
                'outcomes': [*outcomes, {'revision': revision, 'state': 'failed'}]}
    before = transaction.get('dpkg_status_sha256')
    if transaction.get('status') != 'created' or not isinstance(before, str) or not SHA256.fullmatch(before):
        return {'summary': 'O registro desta revisão ainda não permite conferir o resultado.', 'outcomes': outcomes}
    if before == database_sha256:
        return {'summary': 'O banco de pacotes permanece como estava antes da revisão ' + revision + '.',
                'outcomes': outcomes}
    targets = transaction.get('targets')
    count = installed_count(targets)
    summary = f'Revisão {revision} · {count} de {len(targets)} pacotes conferidos.'
    if package_audit or count != len(targets):
        summary += '\nHá pacotes pendentes ou uma instalação incompleta.'
        outcomes.append({'revision': revision, 'state': 'failed'})
    elif reboot_pending:
        summary += '\nReinicie e confira o funcionamento antes de confirmar.'
    else:
        outcomes.append({'revision': revision, 'state': 'completed'})
    return {'summary': summary, 'outcomes': outcomes}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('preview')
    submit = sub.add_parser('submit')
    submit.add_argument('revision')
    submit.add_argument('state', choices=('completed', 'failed', 'restored'))
    args = parser.parse_args()
    if os.geteuid() != 0 or LIVE.exists():
        raise ValueError('Use esta operação administrativa no sistema instalado.')
    config = read_config()
    if not config or 'endpoint' not in config:
        raise ValueError('Cadastre primeiro este computador no serviço da organização.')
    with idle_dpkg():
        audit = subprocess.check_output(['/usr/bin/dpkg', '--audit'], text=True, timeout=15).strip()
        with DPKG_STATUS.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        data = review(read_json(STATE / 'last-managed.json', strict=True), held_revisions(),
                      restored_revisions(), Path('/run/reboot-required').exists(), audit, digest)
        if args.action == 'preview':
            print(json.dumps(data, ensure_ascii=False))
        else:
            payload = {'revision': args.revision, 'state': args.state}
            if payload not in data['outcomes']:
                raise ValueError('O estado da revisão mudou. Confira novamente antes de enviar.')
            request_json(config, 'POST', '/v1/result', payload)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
