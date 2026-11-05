"""Bounded native-messaging protocol; installation always opens confirmation UI."""
import json
import os
import struct
import subprocess
import sys
import webapps_backend as backend

def handle(message):
    if os.geteuid()==0 or not isinstance(message,dict):
        raise ValueError('Use a sua conta de usuário.')
    action=message.get('action')
    if action in ('profile-context','new-profile','profile-preferences','external-link'):
        item=backend.profile_context()
        if not item:return {'available':False}
        if action=='external-link':
            backend.open_external(item['id'],message.get('url',''))
            return {'opened':True}
        if action in ('new-profile','profile-preferences'):
            option='--new-profile' if action=='new-profile' else '--preferences'
            subprocess.Popen(['/usr/bin/linuxbr-webapps',option,item['id']],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            return {'opened':True}
        options=backend.profile_options(item['id'])
        service=backend.service_for(item['url'])
        hosts=list(service.get('hosts',[])) if service else []
        from urllib.parse import urlsplit
        hosts.append(urlsplit(item['url']).hostname)
        return {'available':True,'name':item['name'],'session':item['session'],
                'external_links':options['external_links'],'hosts':sorted(set(hosts))}
    if action=='status':return backend.status(message)
    if action=='offer':
        item=backend.normalize_offer(message)
        subprocess.Popen(['/usr/bin/linuxbr-webapps','--offer',json.dumps(item,ensure_ascii=False)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        return {'opened':True}
    if action=='manage':
        subprocess.Popen(['/usr/bin/linuxbr-webapps'],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        return {'opened':True}
    raise ValueError('Ação não reconhecida.')

def main():
    stream=sys.stdin.buffer
    header=stream.read(4)
    if len(header)!=4:return
    length=struct.unpack('=I',header)[0]
    if not 0<length<=16384:return
    payload=stream.read(length)
    try:
        if len(payload)!=length:raise ValueError('Mensagem incompleta.')
        result=handle(json.loads(payload))
    except (ValueError,TypeError,KeyError,OSError) as exc:result={'error':str(exc)}
    encoded=json.dumps(result,ensure_ascii=False).encode()
    sys.stdout.buffer.write(struct.pack('=I',len(encoded))+encoded);sys.stdout.buffer.flush()

if __name__=='__main__':main()
