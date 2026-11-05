"""Read installed release, local APT metadata and restart requirements."""
import json
import os
from pathlib import Path
import re
import subprocess


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10,
                                env={**os.environ, 'LC_ALL': 'C'})
        return result.stdout if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def release_status():
    installed = command(['dpkg-query', '-W', '-f=${Version}', 'linuxbr-release']).strip()
    policy = command(['apt-cache', 'policy', 'linuxbr-release'])
    candidate = next((line.split(':', 1)[1].strip() for line in policy.splitlines()
                      if line.strip().startswith('Candidate:')), '')
    sources = []
    directory = Path('/etc/apt/sources.list.d')
    for path in sorted(directory.glob('*')):
        if path.suffix not in ('.sources', '.list'):
            continue
        try:
            content = path.read_text()
            active = '\n'.join(line for line in content.splitlines() if line.strip() and not line.lstrip().startswith('#'))
            if path.suffix == '.sources':
                enabled = any(not re.search(r'^Enabled:\s*no\s*$', stanza, re.M | re.I)
                              and re.search(r'^URIs:\s*\S', stanza, re.M | re.I)
                              for stanza in re.split(r'\n\s*\n', content))
            else:
                enabled = any(line.lstrip().startswith('deb ') for line in active.splitlines())
            if 'linuxbr' in path.name.lower() and enabled:
                sources.append(path.name)
        except OSError:
            pass
    reboot = Path('/run/reboot-required').exists()
    current_kernel = os.uname().release
    for kernel in Path('/boot').glob('vmlinuz-*'):
        version = kernel.name.removeprefix('vmlinuz-')
        if version != current_kernel:
            try:
                reboot = reboot or subprocess.run(['dpkg', '--compare-versions', version, 'gt', current_kernel],
                                                  capture_output=True, timeout=5).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                pass
    return {'installed': installed, 'candidate': candidate if candidate != '(none)' else '',
            'sources': sources, 'reboot_recommended': reboot}


if __name__ == '__main__':
    print(json.dumps(release_status(), ensure_ascii=False))
