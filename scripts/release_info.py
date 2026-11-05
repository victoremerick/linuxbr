"""One version source for packages, installer labels and release metadata."""
import re
from pathlib import Path


def release_info(root):
    version=(Path(root)/'VERSION').read_text(encoding='utf-8').strip()
    match=re.fullmatch(r'(\d+\.\d+\.\d+)(?:~(alpha|beta|rc)([1-9]\d*))?',version)
    if not match:raise ValueError('Versão inválida: '+version)
    base,stage,number=match.groups()
    label={'alpha':'Alpha','beta':'Beta','rc':'RC'}.get(stage,'')
    return {'version':version,'base_version':base,
            'display_version':base+' '+label+' '+number if stage else base,
            'channel':stage or 'stable',
            'distribution':'Debian 13','codename':'trixie'}
