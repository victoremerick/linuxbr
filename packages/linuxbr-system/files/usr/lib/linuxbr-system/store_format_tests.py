"""Show local release evidence only for the artifact actually selected."""
import json
from pathlib import Path
import platform
import re
import sys


RECORDS = Path('/usr/share/linuxbr/store/format-tests.json')
DIGEST = re.compile(r'[a-f0-9]{64}')
RESULTS = {
    'pass': 'Testado',
    'limited': 'Testado com limitações',
    'fail': 'Falhou no teste',
}
UNKNOWN = 'Sem teste para esta versão'


def records():
    try:
        value = json.loads(RECORDS.read_text(encoding='utf-8'))
        if value.get('schema') == 1 and isinstance(value.get('tests'), list):
            return [row for row in value['tests'] if isinstance(row, dict)
                    and all(isinstance(row.get(key), str) and row[key] for key in
                            ('manager', 'target', 'origin', 'artifact', 'linuxbr', 'version',
                             'architecture', 'date', 'checks', 'evidence', 'result'))
                    and DIGEST.fullmatch(row['artifact']) and row['result'] in RESULTS
                    and row.get('environment', 'release') in ('release', 'laboratory')]
    except (OSError, ValueError, AttributeError):
        pass
    return []


def assessment(rows, *, manager, target, origin, linuxbr, artifact):
    architecture = platform.machine().lower()
    if architecture == 'amd64':
        architecture = 'x86_64'
    candidates = [row for row in rows if all(row[key] == value for key, value in
                  [('manager', manager), ('target', target), ('origin', origin)])]
    exact = [row for row in candidates if row.get('environment') != 'laboratory'
             and row['linuxbr'] == linuxbr and row['artifact'] == artifact
             and row['architecture'] == architecture]
    if len(exact) != 1:
        laboratory = next((row for row in candidates if row.get('environment') == 'laboratory'
                           and row['architecture'] == architecture), None)
        if laboratory:
            return (f"{UNKNOWN}\nEnsaio de laboratório · {laboratory['version']} · "
                    f"{laboratory['architecture']} · {laboratory['date']}\n"
                    f"Verificações: {laboratory['checks']}\nEvidência: {laboratory['evidence']}\n"
                    f"SHA-256 do pacote: {laboratory['artifact']}")
        return UNKNOWN + (' · há ensaios históricos' if candidates and not exact else '')
    row = exact[0]
    detail = (f"{RESULTS[row['result']]} · {row['version']} · {row['architecture']} · {row['date']}\n"
              f"Linux BR {row['linuxbr']}\nVerificações: {row['checks']}\nEvidência: {row['evidence']}")
    if isinstance(row.get('limitations'), str) and row['limitations']:
        detail += '\nLimitações: ' + row['limitations']
    return detail


def target_assessment(target):
    from store_backend import query_local
    from store_portable import flatpak, installed, remotes

    rows = records()
    manager, name = target['manager'], target['target']
    if not any(row['manager'] == manager and row['target'] == name for row in rows):
        return UNKNOWN
    release = query_local(['/usr/bin/dpkg-query', '-W', '-f=${Version}', 'linuxbr-release']).strip()
    origin, artifact = '', ''
    if manager == 'flatpak' and name.count('/') == 2:
        scope = target['scope']
        origin = remotes(scope).get(target['origin'], '')
        if origin and target['installed']:
            artifact = next((commit for ref, remote, commit in installed(scope)
                             if ref == name and remote == target['origin']), '')
        elif origin:
            artifact = flatpak(scope, 'remote-info', '--app', '--show-commit',
                               target['origin'], name).strip()
    elif manager == 'brew':
        from store_optional import PROVIDERS
        if target['origin'] == PROVIDERS['brew'][0] and target['scope'] == PROVIDERS['brew'][1]:
            origin = PROVIDERS['brew'][2]
    # Only a resolved artifact may inherit an approval. APT source/byte
    # resolution will be added together with its source-specific install target.
    return assessment(rows, manager=manager, target=name, origin=origin,
                      linuxbr=release, artifact=artifact)


if __name__ == '__main__':
    print(target_assessment(json.loads(sys.argv[1])))
