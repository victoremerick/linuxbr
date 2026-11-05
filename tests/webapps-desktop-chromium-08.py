#!/usr/bin/python3
"""Exercise two private Chromium profiles against local HTTP/TLS fixtures."""
import argparse
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import shlex
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from unittest.mock import patch
import websocket

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
EXT=ROOT/'packages/linuxbr-system/files/usr/share/linuxbr/webapps'
sys.path.insert(0,str(LIB))
import webapps_backend as web


class Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urllib.parse.urlsplit(self.path);query=urllib.parse.parse_qs(parsed.query)
        if parsed.path=='/download':
            label=query.get('profile',['unknown'])[0]
            if label not in ('pessoal','trabalho'):self.send_error(400);return
            body=('Arquivo do perfil '+label+'.\n').encode()
            self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Content-Disposition','attachment; filename="arquivo-'+label+'.txt"')
        elif parsed.path=='/favicon.ico':
            body=b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#005fb8"/><circle cx="32" cy="32" r="17" fill="white"/></svg>'
            self.send_response(200);self.send_header('Content-Type','image/svg+xml')
        else:
            body='''<!doctype html><meta charset="utf-8"><title>Perfis Linux BR — laboratório</title>
<style>body{margin:0;background:#f3f6fa;color:#202c3a;font:20px system-ui}main{max-width:880px;margin:70px auto;padding:36px;background:white;border:1px solid #c7d5e3}h1{color:#005fb8}a{display:inline-block;margin:14px 24px 14px 0}small{color:#526375}</style>
<main><h1>Perfis Linux BR</h1><h2 id="profile">Laboratório de sessões</h2><p id="state">Somente dados locais de teste.</p>
<a id="same" href="/inside">Página deste aplicativo</a><a id="external" href="https://external.example.org/fixture?a=1#parte">Link externo de teste</a>
<p><small>Não há contas conectadas. Os marcadores e arquivos pertencem ao laboratório.</small></p></main>
<script>const label=localStorage.getItem('profileMarker');if(label){document.querySelector('#profile').textContent='Perfil '+label;document.querySelector('#state').textContent='Marcador salvo neste perfil: '+label;}</script>'''.encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def log_message(self,*_args):pass


class Server(http.server.ThreadingHTTPServer):
    def handle_error(self,request,client_address):
        if isinstance(sys.exception(),(BrokenPipeError,ConnectionResetError)):return
        super().handle_error(request,client_address)


def wait_for(callback,seconds=15):
    deadline=time.monotonic()+seconds;last=None
    while time.monotonic()<deadline:
        try:
            value=callback()
            if value:return value
        except (OSError,ValueError,StopIteration,websocket.WebSocketException) as error:last=error
        time.sleep(.1)
    raise RuntimeError('A operação não ficou pronta: '+str(last))


class Client:
    def __init__(self,target):
        self.socket=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=15,suppress_origin=True);self.sequence=0
    def close(self):self.socket.close()
    def call(self,method,params=None):
        self.sequence+=1;identifier=self.sequence
        self.socket.send(json.dumps({'id':identifier,'method':method,'params':params or {}}))
        while True:
            answer=json.loads(self.socket.recv())
            if answer.get('id')==identifier:
                if 'error' in answer:raise RuntimeError(str(answer['error']))
                return answer.get('result',{})
    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result:raise RuntimeError(str(result['exceptionDetails']))
        return result['result'].get('value')
    def navigate(self,url):
        self.call('Page.navigate',{'url':url})
        wait_for(lambda:self.evaluate('location.href')==url and self.evaluate('document.readyState')=='complete')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--http-port',type=int,default=17948);parser.add_argument('--tls-port',type=int,default=17949)
    parser.add_argument('--serve',action='store_true');args=parser.parse_args()
    if os.geteuid()==0:raise SystemExit('Execute na conta de teste, sem sudo.')
    work=args.workspace.resolve();work.mkdir(parents=True,exist_ok=True)
    if not args.serve and (work/'manifest.json').exists():raise SystemExit('Use outro diretório novo para preservar o laboratório existente.')
    env={'HOME':str(work/'home'),'XDG_CONFIG_HOME':str(work/'config'),'XDG_DATA_HOME':str(work/'data'),
         'XDG_CACHE_HOME':str(work/'cache'),'XDG_STATE_HOME':str(work/'state'),'XDG_CONFIG_DIRS':str(work/'system-config'),
         'XDG_CURRENT_DESKTOP':'X-Generic','DE':'generic','DESKTOP_SESSION':'','DISPLAY':':998','CHROME_CONFIG_HOME':str(work/'config/chromium')}
    os.environ.update(env)
    for variable in ('WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','BROWSER'):os.environ.pop(variable,None)
    for name in ('home','config','data','cache','state','system-config','downloads','logs'):(work/name).mkdir(exist_ok=True)
    certificate=work/'certificate.pem';key=work/'key.pem'
    if not certificate.exists():
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(certificate),
                        '-days','2','-subj','/CN=app.linuxbr.example.org','-addext','subjectAltName=DNS:app.linuxbr.example.org'],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    public=subprocess.check_output(['openssl','x509','-in',str(certificate),'-pubkey','-noout'])
    der=subprocess.check_output(['openssl','pkey','-pubin','-outform','DER'],input=public)
    pin=base64.b64encode(hashlib.sha256(der).digest()).decode()
    servers=[Server(('127.0.0.1',args.http_port),Page),Server(('127.0.0.1',args.tls_port),Page)]
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certificate,key)
    servers[1].socket=context.wrap_socket(servers[1].socket,server_side=True)
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    http_url='http://127.0.0.1:'+str(args.http_port)+'/'
    tls_url='https://app.linuxbr.example.org/'
    if args.serve:
        print(json.dumps({'http':http_url,'tls':tls_url,'spki':pin}),flush=True)
        try:
            while True:time.sleep(.5)
        except KeyboardInterrupt:return
        finally:
            for server in servers:server.shutdown();server.server_close()
    web.CATALOG=EXT/'catalog.json';original_popen=subprocess.Popen
    host=work/'native-host';host.write_text('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(LIB/'webapps_host.py'))+'\n');host.chmod(0o700)
    manifest=json.loads((EXT/'manifest.json').read_text());extension_id=''.join(chr(ord('a')+int(value,16)) for value in hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32])
    host_manifest={'name':'org.linuxbr.webapps','description':'Comunicação local dos perfis de laboratório','path':str(host),'type':'stdio','allowed_origins':['chrome-extension://'+extension_id+'/']}
    native_dir=work/'config/chromium/NativeMessagingHosts';native_dir.mkdir(parents=True,exist_ok=True)
    (native_dir/'org.linuxbr.webapps.json').write_text(json.dumps(host_manifest))
    helper=work/'default-browser';helper.write_text('#!/usr/bin/python3\nimport json,sys\nwith open('+repr(str(work/'external-links.jsonl'))+',"a") as out:out.write(json.dumps(sys.argv[1:])+"\\n")\n');helper.chmod(0o700)
    desktop=web.apps_dir()/'laboratory-browser.desktop';desktop.parent.mkdir(parents=True,exist_ok=True)
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Navegador do laboratório\nExec='+shlex.quote(str(helper))+' %u\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n')
    for scheme in ('http','https'):subprocess.run(['xdg-mime','default',desktop.name,'x-scheme-handler/'+scheme],check=True)
    assert web.default_browser('https')==desktop.name
    identifiers=[]
    with patch('webapp_icons.request_refresh'):
        for label in ('Pessoal','Trabalho'):identifiers.append(web.install({'url':'https://app.linuxbr.example.org/','name':'Perfis Linux BR — laboratório','session':label,'new_session':True}))
    web.save_profile_options(identifiers[0],'default-browser',True)
    assert not web.profile_options(identifiers[1])['session_start']
    web.save_profile_options(identifiers[1],'profile',True)
    assert all(web.profile_options(identifier)['session_start'] for identifier in identifiers)
    for identifier,label in zip(identifiers,('pessoal','trabalho')):
        downloads=work/'downloads'/label;downloads.mkdir(exist_ok=True)
        profile=web.record_path(identifier)/'profile/Default';profile.mkdir(parents=True,mode=0o700)
        # Existing user preferences are fixture data, seeded before Chromium starts.
        preferences={'download':{'default_directory':str(downloads),'prompt_for_download':False},
                     'profile':{'default_content_setting_values':{'notifications':2 if label=='pessoal' else 3,
                        'media_stream_camera':2 if label=='pessoal' else 3,'media_stream_mic':2 if label=='pessoal' else 3}}}
        (profile/'Preferences').write_text(json.dumps(preferences))
        native_profile=profile.parent/'NativeMessagingHosts';native_profile.mkdir()
        (native_profile/'org.linuxbr.webapps.json').write_text(json.dumps(host_manifest))
    processes={};clients=[];logs=[];checks=[];settings_routes=[]
    def spawn(argv,*positional,**keywords):
        if Path(argv[0]).name=='chromium':
            profile=Path(next(value.split('=',1)[1] for value in argv if value.startswith('--user-data-dir=')))
            identifier=profile.parent.name
            flags=['--headless=new','--window-size=1100,760','--disable-gpu','--use-angle=swiftshader','--disable-background-networking','--disable-dev-shm-usage','--no-proxy-server','--remote-debugging-port=0',
                   '--disable-extensions-except='+str(EXT),'--load-extension='+str(EXT),
                   '--host-resolver-rules=MAP app.linuxbr.example.org:443 127.0.0.1:'+str(args.tls_port),'--ignore-certificate-errors-spki-list='+pin]
            argv=list(argv)+flags
            log=(work/'logs'/('chromium-'+identifier+'.log')).open('a');logs.append(log)
            keywords.update(stdout=log,stderr=subprocess.STDOUT)
        return original_popen(argv,*positional,**keywords)
    def targets(identifier):
        port=int((web.record_path(identifier)/'profile/DevToolsActivePort').read_text().splitlines()[0])
        return json.load(urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json/list',timeout=2))
    def client_for(identifier,predicate):
        target=wait_for(lambda:next((item for item in targets(identifier) if predicate(item)),None))
        client=Client(target);clients.append(client);return client
    def browser_close(only=None):
        selected=[identifier for identifier in processes if only is None or identifier==only]
        for identifier in selected:
            try:
                client=client_for(identifier,lambda item:item['type']=='page');client.call('Browser.close')
            except (RuntimeError,OSError,websocket.WebSocketException):pass
        for client in clients:
            try:client.close()
            except OSError:pass
        clients.clear()
        for identifier in selected:
            process=processes.pop(identifier)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
    try:
        with patch.object(web.subprocess,'Popen',side_effect=spawn),patch('webapp_icons.request_refresh'):
            for round_number in (1,2):
                browsers=[]
                for identifier in identifiers:processes[identifier]=web.launch(identifier)
                for identifier,label in zip(identifiers,('pessoal','trabalho')):
                    client=client_for(identifier,lambda item:item['type']=='page' and item['url'].startswith(tls_url));browsers.append(client)
                    wait_for(lambda:client.evaluate('document.readyState')=='complete')
                    wait_for(lambda:client.evaluate('Boolean(document.getElementById("linuxbr-profile-controls"))'))
                    worker=client_for(identifier,lambda item:item['type']=='service_worker' and item['url'].startswith('chrome-extension://'+extension_id+'/'))
                    native=worker.evaluate('new Promise(resolve=>chrome.runtime.sendNativeMessage("org.linuxbr.webapps",{action:"profile-context"},resolve))')
                    assert native['available'] and native['session'].casefold()==label,native
                    assert native['external_links']==('default-browser' if label=='pessoal' else 'profile'),native
                    if round_number==1:
                        assert client.call('Network.setCookie',{'name':'session_tls_test','value':label,'url':tls_url,'secure':True,'expires':time.time()+86400})['success']
                        client.evaluate('localStorage.setItem("profileMarker",'+json.dumps(label)+')')
                    assert client.evaluate('document.cookie')=='session_tls_test='+label
                    assert client.evaluate('localStorage.getItem("profileMarker")')==label
                    client.navigate(http_url)
                    if round_number==1:
                        assert client.call('Network.setCookie',{'name':'session_test','value':label,'url':http_url,'expires':time.time()+86400})['success']
                        client.evaluate('localStorage.setItem("profileMarker",'+json.dumps(label)+')')
                    assert client.evaluate('document.cookie')=='session_test='+label
                    assert client.evaluate('localStorage.getItem("profileMarker")')==label
                    checks.append({'round':round_number,'profile':label,'http_cookie':True,'http_storage':True,'tls_cookie':True,'tls_storage':True,'native_context':True})
                    if round_number==1:
                        for section in ('downloads','site','notifications','camera','microphone'):
                            print('Preferência nativa:',label,section,flush=True)
                            browser_close(identifier)
                            processes[identifier]=web.open_profile_settings(identifier,section)
                            settings=client_for(identifier,lambda item:item['type']=='page' and item['url'].startswith('chrome://settings/'))
                            route=wait_for(lambda:settings.evaluate('location.href'))
                            expected={'downloads':'chrome://settings/downloads','site':'chrome://settings/content/siteDetails?site=https%3A%2F%2Fapp.linuxbr.example.org','notifications':'chrome://settings/content/notifications','camera':'chrome://settings/content/camera','microphone':'chrome://settings/content/microphone'}[section]
                            assert any(item['url']==expected for item in targets(identifier)),(section,route)
                            settings_routes.append({'profile':label,'section':section,'route':expected,'directory':str(web.record_path(identifier)/'profile')})
                            if section=='downloads':
                                current=settings.evaluate('new Promise(resolve=>chrome.settingsPrivate.getPref("download.default_directory",resolve))')
                                assert current['value']==str(work/'downloads'/label),current
                            if section in ('notifications','camera','microphone'):
                                key={'notifications':'notifications','camera':'media-stream-camera','microphone':'media-stream-mic'}[section]
                                current=settings.evaluate('import("chrome://resources/js/cr.js").then(module=>module.sendWithPromise("getDefaultValueForContentType",'+json.dumps(key)+'))')
                                assert current['setting']==('block' if label=='pessoal' else 'ask'),current
                                settings_routes[-1]['stored_preference']=current['setting']
                        browser_close(identifier);processes[identifier]=web.launch(identifier)
                        client=client_for(identifier,lambda item:item['type']=='page' and item['url'].startswith(tls_url))
                        wait_for(lambda:client.evaluate('document.readyState')=='complete');client.navigate(http_url)
                        client.call('Browser.setDownloadBehavior',{'behavior':'default'})
                        client.call('Page.navigate',{'url':http_url+'download?profile='+label})
                        download=work/'downloads'/label/('arquivo-'+label+'.txt')
                        wait_for(lambda:download.is_file())
                        assert download.read_text()=='Arquivo do perfil '+label+'.\n'
                        client.navigate(tls_url)
                        wait_for(lambda:client.evaluate('Boolean(document.getElementById("linuxbr-profile-controls"))'))
                        if label=='pessoal':
                            client.call('Page.bringToFront')
                            client.evaluate('document.addEventListener("click",event=>{window.labClick={trusted:event.isTrusted,button:event.button,target:event.target.id};},true)')
                            position=client.evaluate('(()=>{const r=document.getElementById("external").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()')
                            client.call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','buttons':1,'clickCount':1,**position})
                            client.call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','buttons':0,'clickCount':1,**position})
                            external=work/'external-links.jsonl'
                            try:wait_for(lambda:external.is_file() and external.read_text().strip())
                            except RuntimeError:
                                print('Diagnóstico do clique:',client.evaluate('({click:window.labClick,url:location.href,text:document.body.innerText})'),flush=True);raise
                            time.sleep(.4)
                            assert external.read_text().splitlines()==['["https://external.example.org/fixture?a=1#parte"]']
                            assert client.evaluate('location.href')==tls_url
                browser_close()
        loop=web.apps_dir()/'laboratory-loop.desktop'
        loop.write_text('[Desktop Entry]\nType=Application\nName=Rota de retorno de teste\nExec=/usr/bin/linuxbr-webapps --launch '+identifiers[0]+'\nMimeType=x-scheme-handler/https;\n')
        subprocess.run(['xdg-mime','default',loop.name,'x-scheme-handler/https'],check=True)
        try:
            try:web.open_external(identifiers[0],'https://external.example.org/fixture?a=1#parte')
            except ValueError:pass
            else:raise AssertionError('A associação que retorna ao perfil web não foi recusada.')
        finally:subprocess.run(['xdg-mime','default',desktop.name,'x-scheme-handler/https'],check=True)
        assert (work/'external-links.jsonl').read_text().splitlines()==['["https://external.example.org/fixture?a=1#parte"]']
        for identifier,label in zip(identifiers,('pessoal','trabalho')):
            preferences=json.loads((web.record_path(identifier)/'profile/Default/Preferences').read_text())
            assert preferences['download']['default_directory']==str(work/'downloads'/label)
            assert identifier in web.session_start_path(identifier).read_text()
        result={'status':'PASS','checks':checks,'settings_routes':settings_routes,'downloads':True,'download_preferences_persisted':True,
                'autostart_selected_profiles':True,'external_trusted_click_native_helper':True,'external_link_no_loop':True,'external_mime_loop_refused':True,
                'profiles':[{'id':identifier,'label':label,'directory':str(web.record_path(identifier)/'profile')} for identifier,label in zip(identifiers,('Pessoal','Trabalho'))],
                'http':http_url,'tls':tls_url,'tls_server':'127.0.0.1:'+str(args.tls_port),'spki':pin,'extension_id':extension_id,'workspace':str(work),'real_accounts_tested':False,
                'chromium_version':subprocess.check_output(['/usr/bin/chromium','--version'],text=True).strip(),
                'tested_files':[{'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in [LIB/'webapps_backend.py',LIB/'webapps_host.py',EXT/'manifest.json',EXT/'background.js',EXT/'content.js',EXT/'profiles-worker.js',EXT/'settings.html',EXT/'settings.js']],
                'limits':['O nome HTTPS do laboratório é resolvido para um servidor TLS local por flags exclusivas do teste. A URL produzida pelo lançador é preservada. Cookies e armazenamento são conferidos também na mesma origem HTTP local.','O certificado da fixture é aceito apenas pelo seu SPKI. Nenhuma autoridade é instalada na confiança da conta ou do sistema.','O modo headless recusa a segunda invocação do mesmo perfil. As preferências são abertas depois do encerramento do processo, preservando o diretório; a reutilização de janela na sessão gráfica precisa ser conferida separadamente.','As preferências iniciais são semeadas na fixture com Chromium fechado. A leitura nativa, preservação e downloads são conferidos; a alteração pelo seletor de pastas exige validação gráfica.','Câmera, microfone e notificações são conferidos pelas páginas nativas; nenhum dispositivo ou conta real é utilizado.']}
        (work/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    finally:
        browser_close()
        for log in logs:log.close()
        for server in servers:server.shutdown();server.server_close()


if __name__=='__main__':main()
