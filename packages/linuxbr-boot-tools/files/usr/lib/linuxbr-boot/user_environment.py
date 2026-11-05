"""Load literal per-user environment values for the service manager."""
import json
import os
from pathlib import Path
import re
import shlex
import sys
from boot_policy import mode


def values():
    if mode():return {}
    path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'linuxbr/environment.json'
    if not path.exists():return {}
    info=path.stat()
    if path.is_symlink() or info.st_uid!=os.getuid() or info.st_size>5*1024*1024:raise ValueError('Arquivo de ambiente pessoal inválido.')
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or len(data)>512:raise ValueError('Lista de variáveis inválida.')
    for key,value in data.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',key) or not isinstance(value,str) or len(value)>8192 or any(c in value for c in '\r\n\x00'):raise ValueError('Nome ou valor de variável inválido.')
    return data


if __name__=='__main__':
    try:
        data=values()
        for key,value in sorted(data.items()):print(key+'='+shlex.quote(value))
    except Exception as error:print('Linux BR: ambiente pessoal não carregado: '+str(error),file=sys.stderr)
