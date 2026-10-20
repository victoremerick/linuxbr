import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/linuxbr-drive-manager/files'
spec=importlib.util.spec_from_file_location('linuxbr_terminal',SOURCE/'usr/lib/linuxbr-drive-manager/terminal.py')
terminal=importlib.util.module_from_spec(spec); spec.loader.exec_module(terminal)
class Terminal(unittest.TestCase):
    def test_resolution_and_network(self):
        self.assertEqual(terminal.resolve('C:/etc'),'/etc')
        self.assertEqual(terminal.resolve('d:/Minha pasta',lambda _: 'file:///mnt/Dados'),'/mnt/Dados/Minha pasta')
        self.assertEqual(terminal.resolve(r'D:\docs',lambda _: 'file:///mnt/Dados'),'/mnt/Dados/docs')
        self.assertEqual(terminal.resolve('D:/../../etc',lambda _: 'file:///mnt/Dados'),'/mnt/Dados/etc')
        with patch.object(terminal,'remember') as remember:
            self.assertEqual(terminal.resolve('Z:/Projetos',lambda _: 'smb://server/team',lambda _: '/run/user/1000/kio/team'),'/run/user/1000/kio/team/Projetos')
            remember.assert_called_once_with('smb://server/team','/run/user/1000/kio/team')
        for text in ('A:', 'D:relative', 'D:/bad\nname'):
            with self.assertRaises(ValueError): terminal.resolve(text,lambda _: 'file:///tmp')
        with self.assertRaises(ValueError): terminal.resolve('D:',lambda _: 'http://server')
    def test_display_and_modes(self):
        state={'data':{'letters':{'uuid:x':'D'}},'rows':[{'key':'uuid:x','mounts':['/mnt/data'],'protected':False}]}
        self.assertEqual(terminal.display('/mnt/data/docs',state),'D:/docs')
        self.assertEqual(terminal.display('/mnt/database',state),'C:/mnt/database')
        self.assertEqual(terminal.display('/home/user',{}),'C:/home/user')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}):
            self.assertEqual(terminal.mode(),'letras')
            terminal.set_mode('linux'); self.assertEqual(terminal.mode(),'linux')
            self.assertEqual(terminal.config_path().stat().st_mode & 0o777,0o600)
            with self.assertRaises(ValueError): terminal.set_mode('other')
            terminal.config_path().write_text('broken'); self.assertEqual(terminal.mode(),'letras')
    def test_network_prompt_tracks_current_assignments(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'XDG_RUNTIME_DIR':tmp}):
            mount=Path(tmp)/'team'; mount.mkdir()
            terminal.remember('smb://server/team',str(mount))
            state={'data':{'letters':{'smb:smb://server/team':'Z'}}}
            self.assertEqual(terminal.display(str(mount/'Docs'),state),'Z:/Docs')
            state['data']['letters']['smb:smb://server/team']='Y'
            self.assertEqual(terminal.display(str(mount/'Docs'),state),'Y:/Docs')
            terminal.mount_cache().write_text('[]')
            terminal.remember('smb://server/team',str(mount))
            self.assertEqual(terminal.display(str(mount/'Docs'),state),'Y:/Docs')

    def test_interactive_bash_and_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); target=root/'Dados com espaço'; target.mkdir(); (target/'Projetos').mkdir(); (target/'-P').mkdir()
            (root/'terminal.py').write_text((SOURCE/'usr/lib/linuxbr-drive-manager/terminal.py').read_text())
            (root/'client.py').write_text('class Stub:\n def Resolve(self,letter,timeout):\n  if letter=="D": return '+repr(target.as_uri())+'\n  raise ValueError("unavailable")\ndef interface(): return Stub()\n')
            shell=(SOURCE/'usr/share/linuxbr/terminal.bash').read_text().replace('/usr/lib/linuxbr-drive-manager/terminal.py',str(root/'terminal.py'))
            (root/'terminal.bash').write_text(shell)
            (root/'rc').write_text("PS1='original> '\nPROMPT_COMMAND=': preserved'\nsource "+shlex.quote(str(root/'terminal.bash'))+'\n')
            script='''set -e
[[ $PS1 == '> ' ]]
d:
[[ $PWD == TARGET ]]
cd D:/Projetos
[[ $PWD == TARGET/Projetos ]]
[[ $(unidade D:/Projetos) == TARGET/Projetos ]]
cd D:
cd -- -P
[[ $PWD == TARGET/-P ]]
cd D:
! Z:
[[ $PWD == TARGET ]]
C:
[[ $PWD == / ]]
[[ ${PROMPT_COMMAND[0]} == ': preserved' ]]
terminal-modo linux
[[ $PS1 == 'original> ' ]]
! D:
cd TARGET
[[ $PWD == TARGET ]]
terminal-modo letras
D:
LINUXBR_TERMINAL_PATH='$(touch MARKER)'
printf '%s' "${PS1@P}" >/dev/null
[[ ! -e MARKER ]]
terminal-modo linux
'''.replace('TARGET',shlex.quote(str(target))).replace('MARKER',shlex.quote(str(root/'injected')))
            env={**os.environ,'HOME':tmp,'XDG_CONFIG_HOME':tmp}
            result=subprocess.run(['bash','--noprofile','--rcfile',str(root/'rc'),'-ic',script],env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertFalse((root/'linuxbr/terminal.json').exists())
            (root/'linuxbr').mkdir()
            (root/'linuxbr/terminal.json').write_text('{"mode":"linux"}')
            fresh=subprocess.run(['bash','--noprofile','--rcfile',str(root/'rc'),'-ic','[[ $(terminal-modo) == letras ]]; C:; [[ $PWD == / ]]'],env=env,capture_output=True,text=True)
            self.assertEqual(fresh.returncode,0,fresh.stderr)
            result=subprocess.run(['bash','-c','source '+shlex.quote(str(root/'terminal.bash'))+'; ! declare -F terminal-modo'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            with (root/'rc').open('w') as stream:
                stream.write('function cd { builtin cd "$@"; CUSTOM_CD=preserved; }\nsource '+shlex.quote(str(root/'terminal.bash'))+'\n')
            result=subprocess.run(['bash','--noprofile','--rcfile',str(root/'rc'),'-ic','cd /; [[ $CUSTOM_CD == preserved ]]'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main()
