#!/usr/bin/python3
"""Create disposable property and personal-backup fixtures without system changes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    if not root.is_absolute() or root.exists():
        raise SystemExit('Escolha uma pasta nova; os arquivos existentes não serão substituídos.')
    os.umask(0o077)
    root.mkdir(parents=True)
    documents = root / 'Documentos'
    documents.mkdir()
    (documents / 'pasta vazia').mkdir()
    filename = documents / 'ação com espaços.txt'
    original = 'Versão anterior para conferir integridade.\n'.encode()
    current = 'Versão atual que deve ser preservada na restauração.\n'.encode()
    filename.write_bytes(original)
    config = root / 'config'
    config.mkdir()
    repository = root / 'backup-pessoal'
    (config / 'kuprc').write_text('[Plan][1]\nDescription=Propriedades 0.8 — teste\nPaths included=' + str(documents) +
        '\nDestination type=0\nFilesystem destination path=' + str(repository) + '\nBackup type=0\n')
    environment = {**os.environ, 'HOME': str(root), 'XDG_CONFIG_HOME': str(config)}
    with (root / 'bup-prepare.log').open('w') as log:
        def bup(*arguments):
            result = subprocess.run(['bup', '-d', str(repository), *arguments], env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            log.write(' '.join(arguments) + '\n' + result.stdout + result.stderr + '\n')
            result.check_returncode()
        timestamp = int(time.time()) - 20
        bup('init')
        bup('index', '-u', str(documents))
        bup('save', '-n', 'kup', '--date=' + str(timestamp), str(documents))
        filename.write_bytes(current)
        bup('index', '-u', str(documents))
        bup('save', '-n', 'kup', '--date=' + str(timestamp + 2), str(documents))
    security = root / 'Segurança'
    (security / 'subpasta').mkdir(parents=True)
    (security / 'subpasta' / 'arquivo.txt').write_text('Permissões e ACL somente nesta árvore de teste.\n')
    outside = root / 'fora-da-arvore'
    outside.mkdir()
    (outside / 'preservar.txt').write_text('A recursão não deve alterar este alvo de link.\n')
    (security / 'link-externo').symlink_to(outside, target_is_directory=True)
    (root / 'link-do-documento').symlink_to(filename)
    sharing = root / 'Compartilhamento'
    sharing.mkdir()
    (sharing / 'leitura.txt').write_text('Conteúdo descartável para leitura SMB autenticada.\n')
    (sharing / 'gravacao').mkdir()
    shortcut = root / 'Atalho de teste.desktop'
    marker = root / 'execucao-explicita.txt'
    shortcut.write_text('[Desktop Entry]\nType=Application\nName=Atalho de teste\nIcon=document-edit\nExec=/usr/bin/touch -- "' + str(marker) + '"\nPath=' + str(documents) + '\nTerminal=false\n')
    (root / 'atalho-windows.lnk').write_bytes(bytes.fromhex('4c0000000114020000000000c000000000000046') + b'\0' * 56)
    large = root / 'hash-cancelamento.bin'
    with large.open('wb') as stream:
        stream.truncate(1024 * 1024 * 1024)
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), root=str(root), config=str(config),
        file=str(filename), repository=str(repository), restore_to=str(root / 'restaurado'),
        original_sha256=hashlib.sha256(original).hexdigest(), current_sha256=hashlib.sha256(current).hexdigest(),
        security=str(security), untouched_link_target=str(outside), sharing=str(sharing), shortcut=str(shortcut),
        execution_marker=str(marker), hash_cancel=str(large), note='ACL, contas, compartilhamentos e serviços ainda não foram alterados.')
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
