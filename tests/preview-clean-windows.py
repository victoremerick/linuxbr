#!/usr/bin/python3
"""Capture installed applications in a disposable container, using fake inventory.
Run under Xvfb and dbus-run-session with a fresh HOME, KWin, Dolphin and the
Linux BR files installed. Output: /tmp/linuxbr-{explorer,central}-layout.png.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
if not Path('/run/.containerenv').exists() and not Path('/.dockerenv').exists():
    raise SystemExit('Use um container descartável com HOME temporário.')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
app=QApplication([]);QIcon.setThemeName('breeze')
root=Path(__file__).resolve().parents[1];home=Path.home()
for name in ['Documentos','Downloads','Imagens','Vídeos','Música','Projetos']:
    (home/name).mkdir(exist_ok=True)
config=home/'.config';config.mkdir(exist_ok=True)
(config/'user-dirs.dirs').write_text('\n'.join('XDG_'+kind+'_DIR="'+str(home/name)+'"' for kind,name in [('DOCUMENTS','Documentos'),('DOWNLOAD','Downloads'),('PICTURES','Imagens'),('VIDEOS','Vídeos'),('MUSIC','Música')]))
settings=config/'linuxbr/sidebar.json';settings.parent.mkdir(exist_ok=True)
settings.write_text(json.dumps({'limit':3,'history':{(home/name).as_uri():[int(time.time())-600+n*61 for n in range(count)] for name,count in [('Projetos',5),('Documentos',4),('Downloads',3)]}}))
server=subprocess.Popen(['python3',str(root/'tests/dolphin-navigation-fixture.py')])
wm=subprocess.Popen(['kwin_x11','--replace'],stdout=open('/tmp/kwin-layout.log','w'),stderr=subprocess.STDOUT)
explorer=None

def wait(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        app.processEvents();time.sleep(.03)

def capture(name):
    subprocess.run(['xdotool','mousemove','1439','959'],check=True);wait(2)
    assert app.primaryScreen().grabWindow(0).save('/tmp/'+name+'.png')

try:
    wait(3)
    explorer=subprocess.Popen(['dolphin','--new-window','-geometry','1280x800+80+60','linuxbr:/'],stdout=open('/tmp/dolphin-layout.log','w'),stderr=subprocess.STDOUT)
    wait(7)
    assert explorer.poll() is None,Path('/tmp/dolphin-layout.log').read_text()
    capture('linuxbr-explorer-layout')
    explorer.terminate();explorer.wait(timeout=10)
    sys.path[:0]=['/usr/lib/linuxbr-system','/usr/lib/linuxbr-drive-manager','/usr/lib/linuxbr-device-manager']
    import central,about
    central.Devices.refresh=lambda self:None
    central.Drives.refresh=lambda self:None
    about.system_details=lambda:[('Especificações do dispositivo',[('Nome do dispositivo','linuxbr-demo'),('Processador','Máquina de demonstração'),('Memória RAM','16 GiB'),('Arquitetura','x86_64')]),('Especificações do sistema',[('Edição','Linux BR '+(root/'VERSION').read_text().strip()+' Alpha'),('Ambiente de trabalho','KDE Plasma'),('Tema','Linux BR Clean'),('Sessão','Prévia em ambiente de teste')])]
    window=central.Central();window.drives.timer.stop();window.devices.timer.stop()
    window.resize(1280,800);window.move(80,60);window.show();wait(3)
    capture('linuxbr-central-layout');window.close()
finally:
    for proc in (explorer,server,wm):
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
