#!/usr/bin/python3
"""Boundaries for VM definitions, repositories and administrative settings."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import virtualization_backend as vm
import store_sources as sources
import catalog_sources
import administration_backend as admin
import app_permissions
import settings_catalog
import store_transactions


class Domains(unittest.TestCase):
    def spec(self,**changes):return dict(name='Minha-VM',memory=2048,cpus=2,pool='imagens',volume='teste.qcow2',uefi=True,secure_boot=False,tpm=False,**changes)

    def test_domain_definition_uses_managed_volume_and_loopback_console(self):
        root=ET.fromstring(vm.domain_xml(self.spec(),{'kind':'qemu'}))
        self.assertEqual(root.find('devices/disk/source').attrib,{'pool':'imagens','volume':'teste.qcow2'})
        self.assertEqual(root.find('devices/graphics/listen').get('address'),'127.0.0.1')
        self.assertEqual(root.find('devices/interface').get('type'),'user')
        self.assertEqual(root.find('memory').text,'2048')
        self.assertEqual(root.find('cpu').get('mode'),'maximum')
        accelerated=ET.fromstring(vm.domain_xml(self.spec(),{'kind':'kvm'}));self.assertEqual(accelerated.find('cpu').get('mode'),'host-model')

    def test_invalid_names_do_not_become_xml_or_paths(self):
        for value in ('../VM','vm/name','<vm>','VM\nOutra','-opcao',''):
            with self.subTest(value=value),self.assertRaises(ValueError):vm.checked_name(value)

    def test_resources_preserve_unknown_hardware_and_metadata(self):
        root=ET.fromstring(vm.domain_xml(self.spec(),{}));ET.SubElement(root.find('metadata'),'nota').text='preservar';ET.SubElement(root.find('devices'),'watchdog',{'model':'i6300esb'})
        result=ET.fromstring(vm.patch_resources(ET.tostring(root,encoding='unicode'),4096,4))
        self.assertEqual(result.findtext('metadata/nota'),'preservar');self.assertIsNotNone(result.find('devices/watchdog'));self.assertEqual(result.findtext('vcpu'),'4')
        self.assertEqual(result.find('cpu/topology').attrib,dict(sockets='1',cores='4',threads='1'))

    def test_custom_cpu_topology_is_not_silently_overwritten(self):
        root=ET.fromstring(vm.domain_xml(self.spec(),{}));root.find('cpu/topology').attrib.update(sockets='2',cores='1',threads='1')
        with self.assertRaises(ValueError):vm.patch_resources(ET.tostring(root,encoding='unicode'),4096,4)

    def test_private_internal_and_bridge_networks_are_distinct(self):
        for mode in ('private','internal','nat','bridge'):
            root=ET.fromstring(vm.network_xml(dict(name='Rede',mode=mode,subnet='192.168.155.0/24',bridge='br0')))
            self.assertEqual(root.find('ip') is not None,mode in ('internal','nat'))
            self.assertEqual(root.find('forward') is not None,mode in ('nat','bridge'))
        with self.assertRaises(ValueError):vm.network_xml(dict(name='Rede',mode='nat',subnet='192.168.1.5/24'))

    def test_remote_uri_cannot_smuggle_ssh_commands(self):
        self.assertEqual(vm.checked_uri('qemu+ssh://victor@servidor/system'),'qemu+ssh://victor@servidor/system')
        for uri in ('qemu+ssh://a@host/system?command=sh','qemu+ssh://a:senha@host/system','qemu+ssh://a@host/../../x','exec:///bin/sh'):
            with self.subTest(uri=uri),self.assertRaises(ValueError):vm.checked_uri(uri)


class Repositories(unittest.TestCase):
    def test_transport_and_credentials_are_checked(self):
        for value in ('http://example.com/repo','https://u:p@example.com/repo','https://example.com/repo\nOutra','file:///tmp/repo'):
            with self.assertRaises(ValueError):sources.https_url(value)

    def test_catalogs_cannot_introduce_executable_commands(self):
        row=dict(id='whatsapp',name='Mensagens',description='Comunicação',category='Internet',kind='web',source='https://example.com/',url='https://example.com/',command='rm -rf /',icon='/etc/shadow')
        result=catalog_sources.checked(dict(apps=[row]),'exemplo')[0]
        self.assertNotIn('command',result);self.assertNotIn('icon',result)
        with self.assertRaises(ValueError):catalog_sources.checked(dict(apps=[dict(row,kind='linux')]),'exemplo')
        with self.assertRaises(ValueError):catalog_sources.checked(dict(apps=[row,row]),'exemplo')

    def test_apt_edit_refuses_changed_file_without_overwriting(self):
        if os.geteuid()!=0:self.skipTest('Exige o executor administrativo isolado.')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'linuxbr-extra-teste.sources';original=b'Types: deb\nURIs: https://example.com\nSuites: trixie\nComponents: main\n';path.write_bytes(original);path.chmod(0o644)
            with patch.object(sources,'SOURCE_DIR',Path(folder)),self.assertRaises(ValueError):sources.apply(dict(action='disable',path=str(path),sha256='0'*64))
            self.assertEqual(path.read_bytes(),original)

    def test_local_install_request_requires_hash_and_correct_scope(self):
        request=dict(manager='file',action='install',target='/tmp/teste.deb',scope='system',origin='Arquivo local',name='teste',sha256='a'*64)
        self.assertEqual(store_transactions.checked_request(request)['sha256'],'a'*64)
        with self.assertRaises(ValueError):store_transactions.checked_request(dict(request,scope='user'))
        with self.assertRaises(ValueError):store_transactions.checked_request(dict(request,sha256=''))


class DesktopSettings(unittest.TestCase):
    def test_permissions_are_only_fixed_argv(self):
        values=app_permissions.commands('org.exemplo.App',dict(network=False,camera=False))
        self.assertEqual(values[0],['/usr/bin/flatpak','override','--user','--unshare=network','org.exemplo.App'])
        self.assertEqual(values[1][-2:],['org.exemplo.App','no'])
        for identifier in ('../etc','--system','org.x.App;sh'):
            with self.assertRaises(ValueError):app_permissions.commands(identifier,dict(network=True))

    def test_user_environment_treats_shell_metacharacters_as_data(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_CONFIG_HOME':folder}):
            path=Path(folder)/'injetado';value="$(touch "+str(path)+") ; ' valor % com espaços"
            record=admin.environment('user');admin.save_environment('user',dict(TESTE=value),record['sha256']);hook=Path(folder)/'plasma-workspace/env/linuxbr-variables.sh'
            command='. '+shlex.quote(str(hook))+'; '+shlex.quote(sys.executable)+' -c '+shlex.quote('import os;print(os.environ["TESTE"])')
            result=subprocess.check_output(['/bin/sh','-c',command],text=True)
            self.assertEqual(result.rstrip('\n'),value);self.assertFalse(path.exists())
            with self.assertRaises(ValueError):admin.save_environment('user',dict(TESTE='outro'),record['sha256'])

    def test_scheduler_escapes_expansion_without_using_shell(self):
        self.assertEqual(admin.unit_argument('valor %n $HOME'),'"valor %%n $$HOME"')
        with self.assertRaises(ValueError):admin.unit_argument('linha\noutro')

    def test_categories_have_unique_routes_and_familiar_search(self):
        self.assertEqual(len(settings_catalog.CATEGORIES),12)
        identifiers=[page['id'] for page in settings_catalog.PAGES];self.assertEqual(len(identifiers),len(set(identifiers)))
        self.assertIn('virtualization',[page['id'] for page in settings_catalog.search('hyper-v')])
        self.assertIn('keyboard',[page['id'] for page in settings_catalog.search('ABNT2')])
        self.assertIn('about',[page['id'] for page in settings_catalog.search('memória')])


class Bundles(unittest.TestCase):
    def test_imported_nvram_cannot_reference_an_external_host_file(self):
        import struct
        from virtualization_transfer import checked_state_data
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);header=bytearray(104);header[:4]=b'QFI\xfb';struct.pack_into('>I',header,4,3);struct.pack_into('>Q',header,24,540672);path=root/'state.bin';path.write_bytes(header);configuration=ET.fromstring('<domain><os><nvram format="qcow2"/></os></domain>');item=dict(role='nvram',file='state.bin',size=len(header),sha256=hashlib.sha256(header).hexdigest())
            self.assertEqual(checked_state_data(root,item,configuration),bytes(header))
            struct.pack_into('>Q',header,8,4096);path.write_bytes(header);item['sha256']=hashlib.sha256(header).hexdigest()
            with self.assertRaises(ValueError):checked_state_data(root,item,configuration)

    def test_secure_firmware_preserves_keys_and_same_names_in_different_namespaces(self):
        import uuid
        import vm_firmware
        from virt.firmware.efi import efivar,ucs16
        store,variables=vm_firmware.variables(vm_firmware.BASE)
        for index,value in enumerate((b'primeiro',b'segundo')):variables['fixture'+str(index)]=efivar.EfiVar(ucs16.from_string('NamespaceTeste'),guid=uuid.uuid4(),data=value)
        source=store.bytes_varstore(variables);updated=vm_firmware.enroll(source)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'vars.fd';path.write_bytes(updated);_,after=vm_firmware.variables(path)
        self.assertEqual({item.data for item in after.values() if str(item.name)=='NamespaceTeste'},{b'primeiro',b'segundo'})
        for name in ('PK','dbx'):self.assertEqual(after[name].data,variables[name].data)
        self.assertIn((vm_firmware.ASSETS/'windows-uefi-ca-2023.der').read_bytes(),after['db'].data)
        self.assertTrue(vm_firmware.signatures(variables['db'])<=vm_firmware.signatures(after['db']))

    def test_firmware_refuses_a_certificate_changed_after_review(self):
        import shutil
        import vm_firmware
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'certificates';shutil.copytree(vm_firmware.ASSETS,root);target=root/'windows-uefi-ca-2023.der';target.write_bytes(target.read_bytes()+b'alterado')
            with patch.object(vm_firmware,'ASSETS',root),self.assertRaises(ValueError):vm_firmware.enroll(vm_firmware.BASE.read_bytes())

    def test_local_secure_template_does_not_depend_on_daemon_firmware_cache(self):
        spec=dict(name='VM Windows',memory=4096,cpus=2,pool='images',volume='vm.qcow2',uefi=True,secure_boot=True,tpm=True,windows=True,firmware_template='/var/lib/linuxbr/firmware/vars.fd',firmware_code='/usr/share/OVMF/OVMF_CODE_4M.ms.fd')
        root=ET.fromstring(vm.domain_xml(spec,dict(kind='kvm')))
        self.assertIsNone(root.find('os').get('firmware'));self.assertEqual(root.find('os/nvram').get('template'),spec['firmware_template']);self.assertEqual(root.find('os/loader').get('secure'),'yes')

    def test_firmware_descriptor_supports_libvirt_json_parser(self):
        descriptor=ROOT/'packages/linuxbr-system/files/usr/share/qemu/firmware/10-linuxbr-x86_64-secure-2023.json'
        raw=descriptor.read_bytes();self.assertTrue(raw.isascii())
        value=json.loads(raw);self.assertEqual(value['mapping']['nvram-template']['filename'],'/var/lib/linuxbr/firmware/OVMF_VARS_4M.ms-2023.fd')

    def test_host_preferences_are_private_and_reject_password_urls(self):
        import virtualization_preferences as preferences
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_CONFIG_HOME':folder}):
            value=dict(hosts=['qemu+ssh://victor@servidor/system'],last_uri='qemu:///system',defaults={'qemu:///system':dict(memory=4096,cpus=4,disk_gib=64)})
            preferences.save(value);self.assertEqual(preferences.load(),value);self.assertEqual(preferences.path().stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):preferences.save(dict(value,hosts=['qemu+ssh://user:senha@host/system']))
            self.assertEqual(preferences.load(),value)

    def test_external_and_backing_images_are_rejected_before_import(self):
        import struct
        from virtualization_transfer import validate_disk
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'disk.qcow2';header=bytearray(104);header[:4]=b'QFI\xfb';struct.pack_into('>I',header,4,3);struct.pack_into('>Q',header,24,1024**3);path.write_bytes(header)
            validate_disk(path,'qcow2',1024**3)
            for offset,value in [(8,4096),(72,4),(72,1),(72,2)]:
                changed=bytearray(header);struct.pack_into('>Q',changed,offset,value);path.write_bytes(changed)
                with self.assertRaises(ValueError):validate_disk(path,'qcow2',1024**3)

    def test_bundle_file_paths_cannot_escape_or_follow_links(self):
        from virtualization_transfer import local_file
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'file').write_text('conteúdo');(root/'link').symlink_to(root/'file')
            for name in ('../file','/etc/passwd','link','folder/file','folder\\file'):
                with self.assertRaises(ValueError):local_file(root,name)

    def test_existing_desktop_links_route_to_store(self):
        from store_redirect import command
        self.assertEqual(command(['--mode','update']),['/usr/bin/linuxbr-store','--updates'])
        self.assertEqual(command(['--search','editor']),['/usr/bin/linuxbr-store','--search','editor'])


if __name__=='__main__':unittest.main(verbosity=2)
