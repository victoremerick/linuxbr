#!/usr/bin/env python3
"""Verify Chromium profile isolation in a disposable desktop VM using a local TLS site."""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch
import websocket

sys.path.insert(0,'/usr/lib/linuxbr-system')
import webapps_backend as web
if os.geteuid()==0:raise SystemExit('Execute sem sudo na sessão gráfica de teste.')
work=Path(tempfile.mkdtemp(prefix='linuxbr-profiles-qa-',dir=Path.home()))
os.environ['XDG_DATA_HOME']=str(work/'data')
pid=subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','plasmashell'],text=True).splitlines()[0]
for value in Path('/proc',pid,'environ').read_bytes().split(b'\0'):
    key,_,data=value.partition(b'=')
    if key.decode() in {'DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP','DESKTOP_SESSION'}:
        os.environ[key.decode()]=data.decode()
subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(work/'key.pem'),'-out',str(work/'cert.pem'),'-days','1','-subj','/CN=app.linuxbr.example.org'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
public=subprocess.check_output(['openssl','x509','-in',str(work/'cert.pem'),'-pubkey','-noout'])
der=subprocess.check_output(['openssl','pkey','-pubin','-outform','DER'],input=public)
pin=base64.b64encode(hashlib.sha256(der).digest()).decode()


class Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data=b'<!doctype html><meta charset="utf-8"><title>Teste de perfis Linux BR</title><h1>Conta de teste</h1>'
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(data)
    def log_message(self,*_):pass


class Server(http.server.ThreadingHTTPServer):
    def handle_error(self,request,client_address):
        if isinstance(sys.exception(),(BrokenPipeError,ConnectionResetError)):return
        super().handle_error(request,client_address)


server=Server(('127.0.0.1',8443),Page)
tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(work/'cert.pem',work/'key.pem')
server.socket=tls.wrap_socket(server.socket,server_side=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
canonical='https://app.linuxbr.example.org/'
url='https://app.linuxbr.example.org:8443/'
identifiers=[web.install({'url':canonical,'name':'Validação de perfis','session':label,'new_session':i>0}) for i,label in enumerate(('Pessoal','Trabalho'))]
commands=[]
for identifier,port in zip(identifiers,(9223,9224)):
    with patch.object(web.subprocess,'Popen') as launch:
        web.launch(identifier);argv=launch.call_args.args[0]
    commands.append([arg for arg in argv if not arg.startswith('--app=')]+['--app='+url,
        '--remote-debugging-port='+str(port),'--host-resolver-rules=MAP app.linuxbr.example.org 127.0.0.1',
        '--ignore-certificate-errors-spki-list='+pin,'--no-proxy-server'])


class Client:
    def __init__(self,port):
        for _ in range(100):
            try:
                pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1))
                page=next(p for p in pages if p['type']=='page' and p['url'].startswith(url))
                self.socket=websocket.create_connection(page['webSocketDebuggerUrl'],timeout=10,suppress_origin=True)
                self.sequence=0
                if self.evaluate('document.readyState')=='complete' and self.evaluate('location.href')==url and self.evaluate('document.title')=='Teste de perfis Linux BR':return
                self.socket.close()
            except (OSError,StopIteration,ValueError,websocket.WebSocketException):pass
            time.sleep(.3)
        raise RuntimeError('A janela Chromium não ficou pronta.')
    def call(self,method,params=None):
        self.sequence+=1;identifier=self.sequence
        self.socket.send(json.dumps({'id':identifier,'method':method,'params':params or {}}))
        while True:
            answer=json.loads(self.socket.recv())
            if answer.get('id')==identifier:
                if 'error' in answer:raise RuntimeError(str(answer['error']))
                return answer.get('result',{})
    def evaluate(self,expression):
        answer=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True})
        if 'exceptionDetails' in answer:raise RuntimeError(str(answer['exceptionDetails']))
        return answer['result'].get('value')


clients=[];processes=[]
def close():
    for client in clients:
        try:client.call('Browser.close')
        except Exception:pass
        client.socket.close()
    clients.clear()
    for process in processes:
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
    processes.clear()


try:
    for round_number in range(2):
        print('Rodada Chromium:',round_number+1,flush=True)
        for index,argv in enumerate(commands):
            with (work/f'chromium-{round_number+1}-{index+1}.log').open('w') as log:
                processes.append(subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT))
        clients.extend(Client(port) for port in (9223,9224))
        for client,label in zip(clients,('pessoal','trabalho')):
            if round_number==0:
                assert client.call('Network.setCookie',{'name':'session_test','value':label,'url':url,'secure':True,'expires':time.time()+86400})['success']
                client.evaluate('localStorage.setItem("sessionLabel",'+json.dumps(label)+')')
            actual=client.evaluate('localStorage.getItem("sessionLabel")')
            assert actual==label,{'round':round_number+1,'expected':label,'actual':actual}
            cookie=client.evaluate('document.cookie')
            assert cookie=='session_test='+label,{'round':round_number+1,'expected_cookie':'session_test='+label,'actual_cookie':cookie}
        close()
    result={'status':'PASS','simultaneous_profiles':2,'cookie_isolation':True,'local_storage_isolation':True,'persistence_after_restart':True,'real_authenticated_accounts_tested':False,'directory':str(work)}
    (work/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
finally:
    close();server.shutdown();server.server_close()
