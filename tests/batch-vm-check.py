#!/usr/bin/python3
"""Execute real batch control flow in a dedicated user-owned Wine environment."""
import json
import os
from pathlib import Path
import sys
import tempfile

source=Path(__file__).resolve().parents[1]/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0,str(source) if source.is_dir() else '/usr/lib/linuxbr-system')
import windows_runner as runner

base=Path.home()/'qa-batch';base.mkdir(exist_ok=True)
os.environ['XDG_DATA_HOME']=str(base/'data')
identifier=runner.create_environment('Validação BAT e CMD')
folder=base/'Minha pasta & ação';folder.mkdir(exist_ok=True)
child=folder/'child.cmd';child.write_bytes(b'@echo off\r\necho child>> resultado.txt\r\nexit /b 0\r\n')
script=folder/'Meu script & teste.bat'
script.write_bytes(b'@echo off\r\nset "BRASIL=ok"\r\nif not "%BRASIL%"=="ok" exit /b 9\r\n'
                  b'for %%i in (1 2 3) do echo %%i>> resultado.txt\r\n'
                  b'call child.cmd\r\nif errorlevel 1 exit /b 10\r\ngoto fim\r\nexit /b 11\r\n:fim\r\nexit /b 7\r\n')
output=folder/'resultado.txt';output.unlink(missing_ok=True)
code=runner.run(identifier,'run',script)
lines=output.read_text().splitlines()
assert code==7,(code,lines)
assert [line.strip() for line in lines]==['1','2','3','child'],lines
cmd=folder/'Outro arquivo.cmd';cmd.write_bytes(b'@echo off\r\necho cmd> segundo.txt\r\nexit /b 0\r\n')
assert runner.run(identifier,'run',cmd)==0
assert (folder/'segundo.txt').read_text().strip()=='cmd'
result={'status':'PASS','bat_exit_code':code,'cmd_exit_code':0,'control_flow':['set','if','for','call','goto','exit /b'],
        'space_and_ampersand_in_path':True,'relative_files':True,'environment':identifier}
(base/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
