#!/usr/bin/env python3
"""Service model and native Places tests, isolated from real user state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
from core import Store
from service_model import places_for, resolve, computer_bookmark

class Model(unittest.TestCase):
    def test_reconnect_and_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json')
            row=dict(key='uuid:data',name='Dados',kind='Volume',mounts=[],mountable=True,protected=False,path='/block/data',device='/dev/test')
            data=store.discover([row]); letter=data['letters'][row['key']]
            self.assertEqual(resolve('C',store), 'file:///')
            calls=[]
            def backend(args):
                calls.append(args)
                return [row] if args==['list'] else '/media/usuario/Dados com espaço'
            self.assertIn('Dados%20com%20espa%C3%A7o',resolve(letter,store,backend))
            self.assertEqual(calls[1],['mount','/block/data','uuid:data','/dev/test'])
            self.assertEqual(len(places_for([],store.discover([]))),1)
            self.assertEqual(store.discover([row])['letters'][row['key']],letter)
            with self.assertRaises(ValueError): resolve(letter,store,lambda args: [])
            row['protected']=True
            with self.assertRaises(ValueError): resolve(letter,store,backend)
            with self.assertRaises(ValueError): store.assign(row['key'],'DE')
            share=store.add_share('smb://servidor/empresa','Empresa')
            self.assertEqual(resolve(share['letters']['smb:smb://servidor/empresa'],store),'smb://servidor/empresa')

    def test_capacity_icons_and_labels_follow_usage(self):
        row=dict(key='system',name='Sistema',kind='Sistema',mounts=['/'],usage=dict(total=100*1024**3,used=60*1024**3,free=35*1024**3,reserved=5*1024**3))
        data=dict(letters={'uuid:usb':'D'},shares={})
        usb=dict(key='uuid:usb',name='USB',kind='Removível',mounts=[],protected=False)
        places=places_for([row,usb],data)
        self.assertTrue(places[0]['icon'].endswith('disk-060.svg'))
        self.assertIn('35.0 GiB livres de 100.0 GiB',places[0]['name'])
        self.assertEqual(places[0]['url'],'linuxbr:/C')
        self.assertEqual(places[0]['card']['title'],'Sistema (C:)')
        self.assertEqual(places[0]['card']['icon'],'drive-harddisk')
        self.assertEqual(places[0]['card']['usage'],row['usage'])
        self.assertEqual(places[1]['card']['capacityText'],'Monte para consultar espaço')
        self.assertEqual(places[1]['icon'],'drive-removable-media')
        row['usage']['used']=95*1024**3
        self.assertTrue(places_for([row],data)[0]['icon'].endswith('disk-095.svg'))

    @unittest.skipUnless(os.environ.get('PLACES_SYNC'),'native helper not supplied')
    def test_bookmarks_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,XDG_DATA_HOME=tmp)
            target=Path(tmp)/'user-places.xbel'
            original=b'<xbel><bookmark href="file:///home/user/favorite"><title>Meu favorito</title><info><metadata owner="http://www.kde.org"><ID>custom</ID><IsHidden>true</IsHidden></metadata></info></bookmark></xbel>'
            target.write_bytes(original)
            def sync(places):
                return subprocess.run([os.environ['PLACES_SYNC']],input=json.dumps(places),text=True,env=env,capture_output=True)
            places=places_for([],dict(letters={},shares={}))
            result=sync(places); self.assertEqual(result.returncode,0,result.stderr)
            root=ET.parse(target).getroot()
            self.assertEqual(len(root.findall('bookmark')),2)
            self.assertEqual(root.find('bookmark/title').text,'Meu favorito')
            self.assertEqual(root.find('.//IsHidden').text,'true')
            self.assertEqual(Path(str(target)+'.before-linuxbr').read_bytes(),original)
            before=target.read_bytes(); self.assertEqual(sync(places).returncode,0)
            self.assertEqual(target.read_bytes(),before)
            self.assertEqual(sync(computer_bookmark()).returncode,0)
            bookmarks=ET.parse(target).getroot().findall('bookmark')
            self.assertEqual(len(bookmarks),2)
            self.assertIn('linuxbr:/',[b.get('href') for b in bookmarks])
            self.assertNotIn('linuxbr:/C',[b.get('href') for b in bookmarks])
            self.assertEqual(sync([]).returncode,0)
            self.assertEqual(len(ET.parse(target).getroot().findall('bookmark')),1)
            target.write_text('<broken>')
            self.assertEqual(sync(places).returncode,4)
            self.assertEqual(target.read_text(),'<broken>')

if __name__=='__main__': unittest.main()
