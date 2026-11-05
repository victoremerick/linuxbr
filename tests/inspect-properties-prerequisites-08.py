#!/usr/bin/python3
"""Record read-only prerequisites and disposable-fixture integrity for UI checks."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[1] / 'packages/linuxbr-file-properties/files/usr/lib/linuxbr-file-properties/backend.py'
SPEC = importlib.util.spec_from_file_location('properties_prerequisites_08', SOURCE)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    root = Path(manifest['root'])
    results = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), uid=os.geteuid(), root=str(root), commands=[])
    commands = [
        ['id'],
        ['dpkg-query', '-W', 'kio6', 'libkf6kiowidgets6', 'linuxbr-system', 'linuxbr-file-properties', 'kdenetwork-filesharing', 'kup-backup', 'bup', 'acl', 'samba', 'samba-common-bin', 'firewalld'],
        ['findmnt', '-T', str(root), '-o', 'TARGET,FSTYPE,OPTIONS', '-n'],
        ['getfacl', '--all-effective', '--absolute-names', '--', str(Path(manifest['security']) / 'subpasta/arquivo.txt')],
        ['systemctl', 'is-active', 'smbd.service'],
        ['firewall-cmd', '--get-active-zones'],
        ['net', 'usershare', 'info', '--long'],
        ['xdg-user-dir', 'DESKTOP'],
    ]
    for argv in commands:
        if not shutil.which(argv[0]):
            results['commands'].append(dict(argv=argv, missing=True))
            continue
        try:
            reply = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
            results['commands'].append(dict(argv=argv, code=reply.returncode, stdout=reply.stdout, stderr=reply.stderr))
        except subprocess.TimeoutExpired:
            results['commands'].append(dict(argv=argv, timeout=True))
    os.environ['XDG_CONFIG_HOME'] = manifest['config']
    backend.emit = lambda _value: None
    results['versions'] = backend.versions(Path(manifest['file']))
    results['security'] = backend.security(Path(manifest['security']) / 'subpasta/arquivo.txt')
    results['recursive_preview'] = backend.recursive_preview(Path(manifest['security']))
    results['current_file_sha256'] = hashlib.sha256(Path(manifest['file']).read_bytes()).hexdigest()
    results['current_file_unchanged'] = results['current_file_sha256'] == manifest['current_sha256']
    results['execution_marker_absent'] = not Path(manifest['execution_marker']).exists()
    results['link_target_sha256'] = hashlib.sha256((Path(manifest['untouched_link_target']) / 'preservar.txt').read_bytes()).hexdigest()
    results['backend_source_sha256'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
