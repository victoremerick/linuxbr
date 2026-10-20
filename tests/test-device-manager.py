#!/usr/bin/env python3
"""Synthetic sysfs and command fixtures: never writes to hardware or installs packages."""
from pathlib import Path
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-device-manager/files/usr/lib/linuxbr-device-manager'))
import hardware
import firmware_admin

class Hardware(unittest.TestCase):
    def test_buses_builtin_usb_and_unbound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def device(bus,name,files):
                p=root/'bus'/bus/'devices'/name;p.mkdir(parents=True)
                for key,value in files.items():(p/key).write_text(value)
                return p
            pci=device('pci','0000:00:02.0',{'vendor':'0x8086','device':'0x1234','class':'0x030000','modalias':'pci:test'})
            driver=root/'drivers/i915';driver.mkdir(parents=True);(pci/'driver').symlink_to(driver)
            module=root/'modules/i915';module.mkdir(parents=True);(driver/'module').symlink_to(module)
            device('pci','0000:01:00.0',{'vendor':'0xffff','device':'0x0001','class':'0x020000'})
            device('usb','1-1',{'manufacturer':'Fabricante','product':'Teclado','idVendor':'1234','idProduct':'0001'})
            interface=device('usb','1-1:1.0',{})
            hid=root/'drivers/usbhid';hid.mkdir();(interface/'driver').symlink_to(hid)
            pending=device('usb','1-1:1.1',{'modalias':'usb:v1234p0001'})
            device('virtio','virtio0',{})
            runner=lambda args:(0,'0000:00:02.0 "VGA compatible controller" "Intel" "Graphics"\n','')
            rows,warnings=hardware.discover(root,runner)
            self.assertEqual(len(rows),4)
            self.assertEqual(rows[0]['category'],'Vídeo')
            self.assertEqual(rows[0]['modules'],['i915'])
            self.assertEqual(rows[0]['name'],'Graphics')
            self.assertEqual(rows[1]['driver'],'')
            self.assertIn('ver detalhes',rows[1]['status'])
            usb=next(r for r in rows if r['bus']=='USB')
            self.assertEqual(usb['driver'],'usbhid')
            self.assertEqual(usb['modules'],[]) # built-in does not mean broken
            self.assertEqual(usb['unbound_aliases'],['usb:v1234p0001'])
            self.assertIn('interfaces sem driver',usb['status'])

    def test_b43_exact_detection_and_unrelated_guard(self):
        def runner(args):
            return (1,'','') if args[0]=='dpkg-query' else (0,'  Candidate: 1:019-14\n','')
        for module, expected in [('b43','firmware-b43-installer'),('b43legacy','firmware-b43legacy-installer'),('brcmfmac',None),('ssb',None),('bcma',None),('wl',None)]:
            for field in ('modules','candidates'):
                row=dict(id='wifi',name='Broadcom',modules=[],driver='')
                row[field]=[module]
                options=[r for r in hardware.firmware_catalog([row],runner) if r['package'] in hardware.B43_PACKAGES]
                self.assertEqual([r['package'] for r in options if r['action']], [expected] if expected else [])
                self.assertTrue(all('servidores externos' in r['notes'] for r in options))

    def test_ssb_bcma_unbound_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for bus in ('ssb','bcma'):
                p=root/'bus'/bus/'devices'/(bus+'0:0');p.mkdir(parents=True)
                (p/'modalias').write_text(bus+':v4243id0812rev02')
            def runner(args):
                if args[0]=='lspci':return 0,'',''
                self.assertEqual(args[:2],['modprobe','--resolve-alias'])
                return 0,('b43legacy' if args[-1].startswith('ssb:') else 'b43'),' '
            rows,_=hardware.discover(root,runner)
            hardware.resolve_candidates(rows,runner)
            self.assertEqual({r['bus']:r['candidates'] for r in rows}, {'SSB':['b43legacy'],'BCMA':['b43']})

    def test_b43_privileged_revalidation(self):
        import os
        for allowed in (True,False):
            option=dict(package='firmware-b43-installer',related=allowed,action='install' if allowed else '',status='Sem dispositivo')
            with patch.dict(os.environ,{},clear=False), patch('firmware_admin.os.geteuid',return_value=0), patch('firmware_admin.Path.read_text',return_value='ID=linuxbr\n'), patch('firmware_admin.discover',return_value=([],[])), patch('firmware_admin.resolve_candidates') as resolve, patch('firmware_admin.firmware_catalog',return_value=[option]), patch('firmware_admin.subprocess.call',return_value=0) as call:
                if allowed:
                    self.assertEqual(firmware_admin.main(['firmware-b43-installer']),0)
                    self.assertEqual(call.call_args.args[0][-1],'firmware-b43-installer')
                else:
                    with self.assertRaises(ValueError):firmware_admin.main(['firmware-b43-installer'])
                    call.assert_not_called()
                resolve.assert_called_once()

    def test_unplugged_and_missing_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows,warnings=hardware.discover(Path(tmp),lambda args:(1,'','missing lspci'))
            self.assertEqual(rows,[]);self.assertTrue(warnings)

    def test_firmware_patterns_compression_and_missing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'intel').mkdir();(root/'intel/fw-1.bin.zst').touch()
            details=hardware.module_details('i915',lambda args:(0,'intel/fw-*.bin\noptional.bin\n../../bad\n',''),root)
            self.assertEqual(details['firmware'],[dict(name='intel/fw-*.bin',present=True),dict(name='optional.bin',present=False)])
            self.assertIn('error',hardware.module_details('i915',lambda args:(1,'','missing'),root))
            self.assertIn('error',hardware.module_details('--bad',lambda args:self.fail('command executed')))

    def test_alias_lookup_never_loads_modules(self):
        calls=[]
        def runner(args):
            calls.append(args);return 0,'iwlwifi\n',''
        result=hardware.alias_candidates('pci:v00008086d00001234',runner)
        self.assertEqual(result['candidates'],['iwlwifi'])
        self.assertEqual(calls,[['modprobe','--resolve-alias','pci:v00008086d00001234']])
        self.assertEqual(hardware.alias_candidates('--bad',runner)['candidates'],[])
        self.assertEqual(len(calls),1)

    def test_catalog_candidates_and_related_modules(self):
        def runner(args):
            if args[0]=='dpkg-query':return 0,'installed 1.0',''
            return 0,'  Candidate: '+('2.0' if args[-1]=='firmware-iwlwifi' else '(none)')+'\n',''
        rows=hardware.firmware_catalog([dict(modules=['iwlwifi'])],runner)
        intel=next(r for r in rows if r['package']=='firmware-iwlwifi')
        self.assertTrue(intel['related']);self.assertEqual(intel['candidate'],'2.0')
        self.assertTrue(intel['installed']);self.assertFalse(rows[1]['related']);self.assertEqual(rows[1]['candidate'],'')

    def test_package_actions_and_query_failures(self):
        def status(version,candidate,comparison=0,policy_code=0):
            def runner(args):
                if args[0]=='dpkg-query':return (0,'installed '+version,'') if version else (1,'','not installed')
                if args[0]=='apt-cache':return policy_code,'  Candidate: '+candidate+'\n',''
                self.assertEqual(args,['dpkg','--compare-versions',version,'lt',candidate])
                return comparison,'',''
            return hardware.package_status('firmware-iwlwifi',runner)
        self.assertEqual(status('','2.0')['action'],'install')
        self.assertEqual(status('1.0','2.0')['action'],'upgrade')
        self.assertEqual(status('2.0','2.0',1)['status'],'Atualizado')
        self.assertEqual(status('3.0','2.0',1)['action'],'')
        self.assertEqual(status('1.0','2.0',2)['action'],'')
        self.assertEqual(status('','(none)')['action'],'')
        self.assertEqual(status('','2.0',policy_code=1)['candidate'],'')

    @unittest.skipUnless(shutil.which('dpkg'),'real Debian version comparison requires dpkg')
    def test_debian_epoch_versions(self):
        def runner(args):
            if args[0]=='dpkg-query':return 0,'installed 1:1.0',''
            if args[0]=='apt-cache':return 0,'  Candidate: 2.0\n',''
            return hardware.command(args)
        # Epoch 1 is newer than 2.0: do not offer a downgrade.
        self.assertEqual(hardware.package_status('firmware-iwlwifi',runner)['action'],'')

    def test_device_correlations_and_kernel_option(self):
        rows=[dict(id='wifi',name='Adaptador USB',modules=[],driver='usb',candidates=['rtw88_8822bu'])]
        def runner(args):
            return (1,'','absent') if args[0]=='dpkg-query' else (0,'  Candidate: 1.0\n','')
        with patch('hardware.platform.machine',return_value='x86_64'):
            options=hardware.driver_options(rows,runner)
        realtek=next(r for r in options if r['package']=='firmware-realtek')
        self.assertEqual(realtek['devices'],[dict(id='wifi',name='Adaptador USB',reason='Módulo candidato local')])
        self.assertFalse(next(r for r in options if r['package']=='firmware-iwlwifi')['related'])
        self.assertEqual(next(r for r in options if r['type']=='Kernel')['package'],'linux-image-amd64')
        self.assertEqual(firmware_admin.install_args(['--refresh']),['/usr/bin/apt-get','-o','APT::Update::Error-Mode=any','update'])
        self.assertEqual(firmware_admin.install_args(['linux-image-amd64'])[-1],'linux-image-amd64')
        for args in (['--refresh','--allow-unauthenticated'],['linux-image-amd64','--allow-downgrades']):
            with self.assertRaises(ValueError):firmware_admin.install_args(args)

    def test_privileged_allowlist_rejects_arguments_and_nonroot(self):
        for args in ([],['bash'],['--help'],['firmware-iwlwifi','--reinstall'],['firmware-iwlwifi;touch /tmp/test']):
            with self.assertRaises(ValueError):firmware_admin.install_args(args)
        with patch('firmware_admin.os.geteuid',return_value=1000):
            with self.assertRaises(ValueError):firmware_admin.main(['firmware-iwlwifi'])

    def test_privileged_command_environment_and_os_check(self):
        with patch('firmware_admin.os.geteuid',return_value=0),patch('firmware_admin.Path.read_text',return_value='ID=linuxbr\n'),patch('firmware_admin.subprocess.call',return_value=0) as call:
            self.assertEqual(firmware_admin.main(['firmware-iwlwifi']),0)
            args,kwargs=call.call_args
            self.assertEqual(args[0],['/usr/bin/apt-get','--no-remove','install','-y','firmware-iwlwifi'])
            self.assertEqual(kwargs['cwd'],'/')
            self.assertNotIn('PYTHONPATH',kwargs['env'])
        with patch('firmware_admin.os.geteuid',return_value=0),patch('firmware_admin.Path.read_text',return_value='ID=fedora\n'),patch('firmware_admin.subprocess.call') as call:
            with self.assertRaises(ValueError):firmware_admin.main(['firmware-iwlwifi'])
            call.assert_not_called()

if __name__=='__main__':unittest.main()
