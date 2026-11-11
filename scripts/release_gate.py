"""Validate release artifacts and evidence before a stable publication."""
import argparse
import hashlib
import json
from pathlib import Path
import re

REQUIRED = {
    'packages', 'live-uefi', 'live-bios', 'install-desktop-uefi',
    'install-desktop-bios', 'install-server-uefi', 'upgrade-0.9',
    'restore-upgrade', 'restricted-boot', 'desktop-flows', 'store',
    'webapp-profiles', 'administration', 'virtualization', 'signatures',
    'accessibility', 'regressions', 'physical-hardware',
}
SHA = re.compile(r'[0-9a-f]{64}')
SCREEN_SHARING_CHECKS = {
    'screen-sharing-first-login',
    'screen-sharing-after-output-change',
    'screen-sharing-after-relogin',
}
VERSION_11_CHECKS = SCREEN_SHARING_CHECKS | {
    'managed-update-waves', 'support-diagnostic-consent', 'managed-update-recovery',
    'organization-preparation', 'store-snap', 'store-homebrew', 'store-portable-list',
    'store-format-evidence', 'migration-resume',
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local_file(base, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('Use um arquivo relativo à pasta do relatório.')
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError('Arquivo ausente ou fora da pasta de liberação: '+value)
    return path


def verify(manifest, version=None):
    manifest = Path(manifest).resolve()
    value = json.loads(manifest.read_text(encoding='utf-8'))
    if value.get('schema') != 1 or not re.fullmatch(r'\d+\.\d+\.\d+(?:~(?:alpha|beta|rc)[1-9]\d*)?', value.get('version', '')):
        raise ValueError('Identificação de liberação inválida.')
    if version is not None and value['version'] != version:
        raise ValueError('O relatório pertence a outra versão.')
    major_minor = tuple(map(int, value['version'].split('.')[:2]))
    required = REQUIRED | VERSION_11_CHECKS if major_minor >= (1, 1) else REQUIRED
    base = manifest.parent
    artifacts = value.get('artifacts', {})
    if not isinstance(artifacts, dict) or not {'iso', 'source', 'packages'} <= artifacts.keys():
        raise ValueError('Informe ISO, fontes e manifesto dos pacotes.')
    for name, item in artifacts.items():
        if not isinstance(item, dict) or not SHA.fullmatch(item.get('sha256', '')):
            raise ValueError('Checksum inválido: '+name)
        path = local_file(base, item.get('file'))
        if path.stat().st_size != item.get('bytes') or digest(path) != item['sha256']:
            raise ValueError('Artefato alterado: '+name)
    checks = value.get('checks', [])
    if not isinstance(checks, list):
        raise ValueError('Lista de evidências inválida.')
    seen = set()
    for check in checks:
        name = check.get('id')
        if name in seen or name not in required:
            raise ValueError('Cenário duplicado ou desconhecido: '+str(name))
        seen.add(name)
        if check.get('status') != 'PASS' or check.get('version') != value['version']:
            raise ValueError('Cenário sem aprovação nesta versão: '+str(name))
        target = check.get('artifact')
        if target not in artifacts or check.get('artifact_sha256') != artifacts[target]['sha256']:
            raise ValueError('Evidência pertence a outro artefato: '+str(name))
        if name.startswith(('live-', 'install-')) and target != 'iso':
            raise ValueError('Boot e instalação precisam identificar a ISO: '+name)
        if name in SCREEN_SHARING_CHECKS and target != 'iso':
            raise ValueError('Compartilhamento de tela precisa identificar a ISO: '+name)
        evidence = local_file(base, check.get('evidence'))
        if not SHA.fullmatch(check.get('evidence_sha256', '')) or digest(evidence) != check['evidence_sha256']:
            raise ValueError('Evidência alterada: '+str(name))
    missing = required - seen
    if missing:
        raise ValueError('Cenários pendentes: '+', '.join(sorted(missing)))
    policy = value.get('support', {})
    if (not isinstance(policy, dict) or not policy.get('maintainer')
            or not policy.get('maintenance_policy') or not policy.get('supported_hardware')):
        raise ValueError('Defina responsável, manutenção e equipamentos suportados.')
    return {'status': 'PASS', 'version': value['version'], 'artifacts': len(artifacts),
            'scenarios': len(seen), 'manifest_sha256': digest(manifest)}


def publication_acceptance(manifest, version, inputs):
    """Bind a stable acceptance report to the actual DEB archives being signed."""
    if not manifest:
        raise ValueError('A publicação estável exige um relatório de aceitação: --acceptance-report.')
    manifest = Path(manifest).resolve()
    verify(manifest, version)
    value = json.loads(manifest.read_text(encoding='utf-8'))
    path = local_file(manifest.parent, value['artifacts']['packages']['file'])
    rows = json.loads(path.read_text(encoding='utf-8'))
    expected = {(row['Package'], row['Version'], row['Architecture']): row['sha256'] for row in rows}
    if len(expected) != len(rows):
        raise ValueError('O manifesto contém pacotes duplicados.')
    actual = {(name, ver, arch): digest(Path(deb)) for deb, name, ver, arch in inputs}
    if actual != expected:
        raise ValueError('Os pacotes a publicar diferem dos pacotes aceitos.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Conferir artefatos e evidências de liberação.')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--version')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.manifest, args.version), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.exit(1, 'Liberação pendente: '+str(error)+'\n')
