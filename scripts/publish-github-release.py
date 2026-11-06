#!/usr/bin/python3
"""Publish versioned artifacts and checksums through GitHub Releases."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from release_info import release_info
from release_gate import verify

PART_BYTES = 1900 * 1024 * 1024
REPOSITORY = 'victoremerick/linuxbr'


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stage_artifact(source, destination, limit=PART_BYTES):
    """Keep each upload below GitHub's 2 GiB per-asset limit."""
    if source.stat().st_size <= limit:
        target = destination / source.name
        if target.exists():raise ValueError('Nome de artefato repetido: ' + target.name)
        shutil.copyfile(source, target)
        return [target]
    result = []
    with source.open('rb') as stream:
        while True:
            chunk = stream.read(min(limit, 8 * 1024 * 1024))
            if not chunk:
                break
            target = destination / (source.name + '.part' + str(len(result) + 1).zfill(3))
            if target.exists():raise ValueError('Nome de parte repetido: ' + target.name)
            remaining = limit
            with target.open('wb') as output:
                while chunk:
                    output.write(chunk)
                    remaining -= len(chunk)
                    if not remaining:
                        break
                    chunk = stream.read(min(remaining, 8 * 1024 * 1024))
            result.append(target)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Preparar e publicar uma versão no GitHub Releases.')
    parser.add_argument('--artifact', type=Path, action='append', required=True)
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--acceptance-report', type=Path)
    parser.add_argument('--publish', action='store_true', help='Publicar após concluir todos os uploads; padrão: rascunho.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    info = release_info(root)
    if info['channel'] == 'stable':
        if not args.acceptance_report:
            parser.error('Versão estável exige --acceptance-report.')
        verify(args.acceptance_report, info['version'])
        acceptance = json.loads(args.acceptance_report.read_text())
        accepted = {item['sha256'] for item in acceptance['artifacts'].values()}
        if {checksum(path) for path in args.artifact} != accepted:
            parser.error('Envie todos os artefatos correspondentes ao relatório de aceitação.')
    if not args.notes.is_file() or not args.notes.read_text(encoding='utf-8').strip():
        parser.error('Forneça notas de lançamento preenchidas.')
    names = [p.name for p in args.artifact]
    if len(set(names)) != len(names) or any(not p.is_file() or p.stat().st_size == 0 for p in args.artifact):
        parser.error('Os artefatos devem existir, ser não vazios e ter nomes únicos.')
    if any(not all(c.isalnum() or c in '._-' for c in name) or name.startswith('-') for name in names):
        parser.error('Use nomes de artefato com letras, números, ponto, hífen e sublinhado.')
    if any(name in ('SHA256SUMS', 'ORIGINAL-SHA256SUMS', 'release-notes.md') for name in names):
        parser.error('Nome reservado aos metadados da publicação.')
    tag = 'v' + info['version'].replace('~', '-')
    plan = dict(repository=REPOSITORY, tag=tag, channel=info['channel'],
                draft=not args.publish, artifacts=[dict(name=p.name, bytes=p.stat().st_size,
                parts=(p.stat().st_size + PART_BYTES - 1) // PART_BYTES) for p in args.artifact])
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2));return 0
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root).strip():
        parser.error('Conclua o commit das alterações antes da publicação.')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if shutil.disk_usage(tempfile.gettempdir()).free < sum(p.stat().st_size for p in args.artifact) + 256 * 1024 * 1024:
        parser.error('Espaço insuficiente para preparar os arquivos da publicação.')
    with tempfile.TemporaryDirectory(prefix='linuxbr-release-') as temporary:
        folder = Path(temporary); files = []; originals = []
        notes = args.notes.read_text(encoding='utf-8')
        for artifact in args.artifact:
            staged = stage_artifact(artifact, folder);files.extend(staged)
            originals.append(checksum(artifact) + '  ' + artifact.name)
            if len(staged) > 1:
                notes += ('\n\n### Reunir ' + artifact.name + '\n\nBaixe todas as partes e confira '
                          '`SHA256SUMS`. Depois reúna os arquivos, na ordem, antes de gravar a imagem.\n\n'
                          'Linux:\n```sh\ncat ' + artifact.name + '.part* > ' + artifact.name + '\n```\n'
                          'PowerShell:\n```powershell\n$out = [IO.File]::Create("' + artifact.name + '")\n'
                          'try { Get-ChildItem "' + artifact.name + '.part*" | Sort-Object Name | ForEach-Object {\n'
                          '  $part = [IO.File]::OpenRead($_.FullName)\n  try { $part.CopyTo($out) } finally { $part.Dispose() }\n'
                          '} } finally { $out.Dispose() }\n```\nConfira o arquivo final usando `ORIGINAL-SHA256SUMS`.')
        sums = folder / 'SHA256SUMS';sums.write_text('\n'.join(checksum(p) + '  ' + p.name for p in files) + '\n')
        original = folder / 'ORIGINAL-SHA256SUMS';original.write_text('\n'.join(originals) + '\n')
        notes_file = folder / 'release-notes.md';notes_file.write_text(notes, encoding='utf-8')
        command = ['gh', 'release', 'create', tag, '--repo', REPOSITORY, '--target', commit,
                   '--title', 'Linux BR ' + info['display_version'], '--notes-file', str(notes_file), '--draft']
        if info['channel'] != 'stable':command.append('--prerelease')
        subprocess.run(command, cwd=root, check=True)
        for path in files + [sums, original]:
            subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo', REPOSITORY], cwd=root, check=True)
        if args.publish:
            subprocess.run(['gh', 'release', 'edit', tag, '--repo', REPOSITORY, '--draft=false'], cwd=root, check=True)
    print('https://github.com/' + REPOSITORY + '/releases/tag/' + tag)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
