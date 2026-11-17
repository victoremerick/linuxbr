#!/usr/bin/python3
"""Check discovery and launching through the real desktop application registry."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))


class DesktopInventory(unittest.TestCase):
    def test_wine_launcher_is_windows_and_deduplicated_when_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wine_apps = root/'applications/wine'
            wine_apps.mkdir(parents=True)
            env = {**os.environ, 'XDG_DATA_HOME': str(root), 'XDG_DATA_DIRS': str(root/'empty'),
                   'PYTHONPATH': sys.path[0]}
            code = '''
import os
from pathlib import Path
from unittest.mock import patch
import store_backend as backend
import windows_runner as runner

wine = Path(os.environ['XDG_DATA_HOME']) / 'applications/wine'
with patch.object(os, 'geteuid', return_value=1000):
    identifier = runner.create_environment('PDF')
prefix = runner.environment_path(identifier) / 'prefix'
(wine/'sumatra.desktop').write_text('[Desktop Entry]\\nType=Application\\nName=SumatraPDF\\n'
    'Exec=/usr/bin/env WINEPREFIX="' + str(prefix) + '" /usr/bin/true\\nTerminal=false\\n')
item, = backend.desktop_applications()
assert item['kind'] == 'windows' and item['wine_prefix'] == str(prefix), item
managed = {'name': 'SumatraPDF', 'environment': identifier, 'id': 'managed'}
with patch.object(runner, 'programs', return_value=[managed]), patch.object(runner, 'program_icon', return_value='wine'):
    item, = backend.installed_entries([])
    assert item['kind'] == 'windows' and item['program_id'] == 'managed', item
'''
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_registered_app_is_listed_and_only_runs_after_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);apps=root/'applications';apps.mkdir()
            program=root/'programa com espaço.py'
            marker=root/'executado'
            program.write_text('from pathlib import Path\nPath(__file__).with_name("executado").write_text("ok")\n')
            desktop=apps/'linuxbr-inventory-fixture.desktop'
            desktop.write_text('[Desktop Entry]\nType=Application\nName=Programa de validação\n'
                'Exec=/usr/bin/python3 "'+str(program)+'"\nTerminal=false\n')
            (apps/'linuxbr-second-fixture.desktop').write_text(desktop.read_text().replace('Programa de validação','Outro componente'))
            (apps/'linuxbr-hidden-fixture.desktop').write_text(desktop.read_text()+'NoDisplay=true\n')
            env={**os.environ,'XDG_DATA_HOME':str(root),'XDG_DATA_DIRS':str(root/'empty')}
            code='''import store_backend as backend
import pathlib,subprocess,time
items=backend.desktop_applications()
assert len(items)==2,items
items=backend.installed_entries([])
assert {item['name'] for item in items}=={'Programa de validação','Outro componente'},items
assert not pathlib.Path(MARKER).exists()
argv=backend.local_action(items[0])
assert argv[:2]==['/usr/bin/gio','launch'],argv
subprocess.run(argv,check=True)
for _ in range(100):
 if pathlib.Path(MARKER).exists():break
 time.sleep(.02)
assert pathlib.Path(MARKER).read_text()=='ok'
'''.replace('MARKER',repr(str(marker)))
            result=subprocess.run([sys.executable,'-c',code],env={**env,'PYTHONPATH':sys.path[0]},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
