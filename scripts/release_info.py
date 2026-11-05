"""One version source for packages, installer labels and release metadata."""
import re
from pathlib import Path


def release_info(root):
    version=(Path(root)/'VERSION').read_text(encoding='utf-8').strip()
    match=re.fullmatch(r'(\d+\.\d+\.\d+)(?:~beta([1-9]\d*))?',version)
    if not match:raise ValueError('Versão inválida: '+version)
    base,beta=match.groups()
    return {'version':version,'base_version':base,
            'display_version':base+' Beta '+beta if beta else base,
            'channel':'beta' if beta else 'stable',
            'distribution':'Debian 13','codename':'trixie'}
