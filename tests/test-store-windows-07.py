#!/usr/bin/env python3
"""Exercise observed package metadata, PE resources and compatibility diagnostics."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'packages/linuxbr-system/files'
sys.path.insert(0,str(FILES/'usr/lib/linuxbr-system'))
import store_backend as store
import windows_runner as runner
import windows_compat as windows
from PyQt6.QtGui import QImageReader
from PyQt6.QtWidgets import QApplication,QMessageBox
APP=QApplication.instance() or QApplication([])


def resource_executable(path):
    """Minimal PE with distinct primary and secondary icon groups; never executed."""
    header=bytearray(512);header[:2]=b'MZ';struct.pack_into('<I',header,60,128)
    header[128:132]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',header,132,0x14c,1,0,0,0,224,0x102)
    optional=152
    struct.pack_into('<H',header,optional,0x10b)
    struct.pack_into('<I',header,optional+8,512)
    struct.pack_into('<III',header,optional+28,0x400000,4096,512)
    struct.pack_into('<HH',header,optional+40,4,0)
    struct.pack_into('<II',header,optional+56,8192,512)
    struct.pack_into('<H',header,optional+68,2)
    struct.pack_into('<IIIII',header,optional+72,1048576,4096,1048576,4096,0)
    struct.pack_into('<I',header,optional+92,16)
    section=optional+224;header[section:section+8]=b'.rsrc\0\0\0'
    image=struct.pack('<IiiHHIIiiII',40,1,2,1,32,0,4,0,0,0,0)+b'\x20\x60\xe0\xff'+bytes(4)
    second=struct.pack('<IiiHHIIiiII',40,2,4,1,32,0,16,0,0,0,0)+b'\xe0\x60\x20\xff'*4+bytes(8)
    group=struct.pack('<HHHBBBBHHIH',0,1,1,1,1,0,0,1,32,len(image),1)
    other=struct.pack('<HHHBBBBHHIH',0,1,1,2,2,0,0,1,32,len(second),2)
    resources=bytearray();payloads=[]
    def directory(entries):
        offset=len(resources);resources.extend(bytes(16+8*len(entries)))
        struct.pack_into('<IIHHHH',resources,offset,0,0,0,0,0,len(entries))
        for index,(identifier,child) in enumerate(sorted(entries.items())):
            if isinstance(child,dict):target=directory(child)|0x80000000
            else:
                target=len(resources);resources.extend(bytes(16));payloads.append((target,child))
            struct.pack_into('<II',resources,offset+16+8*index,identifier,target)
        return offset
    directory({3:{1:{1033:image},2:{1033:second}},14:{1:{1033:group},100:{1033:other}}})
    for offset,value in payloads:
        resources.extend(bytes((-len(resources))%4));target=len(resources)
        resources.extend(value);struct.pack_into('<IIII',resources,offset,4096+target,len(value),0,0)
    size=len(resources);rawsize=((size+511)//512)*512;resources.extend(bytes(rawsize-size))
    struct.pack_into('<II',header,optional+112,4096,size)
    struct.pack_into('<IIIIIIHHI',header,section+8,size,4096,rawsize,512,0,0,0,0,0x40000040)
    path.write_bytes(header+resources);return path


class StoreWindows07(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)
        for context in (patch.dict(os.environ,{'XDG_DATA_HOME':temporary.name}),patch('os.geteuid',return_value=1000)):
            context.start();self.addCleanup(context.stop)
        self.environment=runner.create_environment('Programa de validação')
        self.file=resource_executable(self.directory/'Programa com espaço & acentuação.exe')

    def test_metadata_uses_exact_deb_owner_and_installed_version(self):
        item={'kind':'linux','source':'Fornecedor','desktop_file':'/usr/share/applications/test.desktop'}
        with patch.object(store,'query_local',side_effect=[
            'fixture:amd64: /usr/share/applications/test.desktop','ii \t1.2.3\t2048']) as query:
            value=store.package_metadata(item)
        self.assertEqual(value['version'],'1.2.3');self.assertIn('2.0 MiB',value['size'])
        self.assertIn('fixture:amd64',value['origin'])
        self.assertEqual(query.call_args.args[0][-1],'fixture:amd64')
        self.assertIn('--',query.call_args_list[0].args[0])

    def test_uninstalled_or_invalid_owner_is_not_claimed_as_installed(self):
        item={'kind':'linux','desktop_file':'/tmp/local.desktop'}
        with patch.object(store,'query_local',return_value='--bad-option: /tmp/local.desktop') as query:
            value=store.package_metadata(item)
        self.assertEqual(query.call_count,1);self.assertIn('não identificado',value['origin'])
        self.assertIn('Não informada',value['version'])

    def test_flatpak_reports_remote_version_size_and_installation(self):
        item={'kind':'linux','flatpak_id':'org.example.Test'}
        with patch.object(store,'query_local',return_value='org.example.Other\t9\t1 MB\tx\tuser\n'
            'org.example.Test\t2.4\t10.5 MB\tflathub\tuser'):
            value=store.package_metadata(item)
        self.assertEqual(value['type'],'Linux / Flatpak');self.assertEqual(value['version'],'2.4')
        self.assertEqual(value['origin'],'flathub (user)');self.assertIn('10.5 MB',value['size'])

    def test_metadata_timeout_is_readonly_and_bounded(self):
        import subprocess
        with patch.object(store.subprocess,'run',side_effect=subprocess.TimeoutExpired('query',3)) as query:
            self.assertEqual(store.query_local(['/usr/bin/flatpak','list']),'')
        self.assertEqual(query.call_args.kwargs['timeout'],3)
        self.assertNotIn('shell',query.call_args.kwargs)

    def test_web_metadata_explains_shared_browser_and_variable_size(self):
        value=store.package_metadata({'kind':'web','source':'https://example.org/'})
        self.assertIn('Chromium compartilhado',value['size']);self.assertIn('Serviço online',value['version'])

    def test_extracts_real_resource_without_executing_exe(self):
        self.assertTrue(Path('/usr/bin/wrestool').is_file(),'Instale icoutils para validar a extração real.')
        with patch.object(runner.subprocess,'call') as execute:
            identifier=runner.register_program(self.environment,self.file,'Programa real')
            execute.assert_not_called()
        path=runner.program_icon_path(identifier)
        self.assertTrue(runner.valid_icon(path.read_bytes()))
        reader=QImageReader(str(path));self.assertFalse(reader.read().isNull(),reader.errorString())
        self.assertEqual(QImageReader(str(path)).read().size().width(),1)
        self.assertEqual(runner.primary_icon_resource(self.file),['--name=1','--language=1033'])
        self.assertIn('Icon='+str(path),runner.program_desktop(identifier).read_text())
        item=next(item for item in store.installed_entries([]) if item.get('program_id')==identifier)
        self.assertEqual(item['icon'],str(path));self.assertIn('somente o EXE',store.package_metadata(item)['size'])
        self.assertEqual(store.manage_action(item),['linuxbr-windows','--program',identifier])
        runner.forget_program(identifier)
        self.assertFalse(path.exists());self.assertTrue(self.file.exists())

    def test_missing_extractor_keeps_shortcut_with_fallback(self):
        with patch.object(runner,'bounded_tool_output',side_effect=FileNotFoundError):
            identifier=runner.register_program(self.environment,self.file,'Sem ícone')
        self.assertEqual(runner.program_icon(identifier),'wine')
        self.assertIn('Icon=wine',runner.program_desktop(identifier).read_text())

    def test_truncated_icon_and_symlink_are_rejected(self):
        self.assertFalse(runner.valid_icon(b'\0\0\1\0'+bytes(20)))
        with patch.object(runner,'bounded_tool_output',side_effect=FileNotFoundError):
            identifier=runner.register_program(self.environment,self.file,'Teste')
        outside=self.directory/'preservar';outside.write_text('preservado')
        runner.program_icon_path(identifier).parent.mkdir(parents=True,exist_ok=True)
        runner.program_icon_path(identifier).symlink_to(outside)
        with self.assertRaises(ValueError):runner.extract_program_icon(identifier,self.file)
        self.assertEqual(outside.read_text(),'preservado')

    def test_tool_output_has_size_and_time_limits(self):
        self.assertIsNone(runner.bounded_tool_output([sys.executable,'-c','print("x"*10000)'],100,3))
        self.assertIsNone(runner.bounded_tool_output([sys.executable,'-c','import time;time.sleep(5)'],100,.05))
        self.assertEqual(runner.bounded_tool_output([sys.executable,'-c','print("ok")'],100,3),b'ok\n')

    def test_resource_language_and_name_are_explicit_and_reviewed(self):
        listing=(b'--type=14 --name=100 --language=1033 [type=group_icon]\n'
                 b'--type=14 --name=1 --language=1046 [type=group_icon]\n'
                 b'--type=14 --name=1 --language=1033 [type=group_icon]\n')
        with patch.object(runner,'bounded_tool_output',return_value=listing):
            self.assertEqual(runner.primary_icon_resource(self.file),['--name=1','--language=1033'])

    def test_diagnosis_reads_headers_and_indicates_missing_runtime(self):
        with patch.object(runner.subprocess,'call') as execute:
            value=runner.diagnose_program(self.environment,self.file,53,'',
                'err:module:import_dll Library VCRUNTIME140.dll not found')
        execute.assert_not_called();self.assertIn('x86',value);self.assertIn('biblioteca ausente',value)
        self.assertIn('Nenhuma biblioteca foi instalada',value)
        self.assertIn('7-Zip',runner.compatibility_guidance('/tmp/7zFM.exe'))
        self.assertIn('existe edição Linux',runner.compatibility_guidance('/tmp/openttd.exe'))

    def test_success_exit_does_not_claim_compatibility(self):
        value=runner.diagnose_program(self.environment,self.file,0)
        self.assertIn('não confirma todas as funções',value)

    def test_uninstall_cancel_does_not_start_job(self):
        window=windows.WindowsCompatibility()
        try:
            with patch.object(windows.QMessageBox,'question',return_value=QMessageBox.StandardButton.Cancel),patch.object(window,'start') as start:
                window.uninstall_programs();start.assert_not_called()
            with patch.object(windows.QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(window,'start') as start:
                window.uninstall_programs();start.assert_called_once_with('uninstall')
        finally:window.close()

    def test_failed_shortcut_monitor_opens_diagnosis(self):
        window=windows.WindowsCompatibility()
        try:
            root=runner.data_root()/'jobs';root.mkdir()
            (root/'fixture.json').write_text(json.dumps({'code':53,'error':'Library not found'}))
            window.job='fixture';window.monitor_only=True;window.job_context=(self.environment,str(self.file))
            with patch.object(window,'show') as show,patch.object(window,'diagnose_last_job') as diagnose:
                window.poll();show.assert_called_once();diagnose.assert_called_once()
            self.assertFalse(window.monitor_only);self.assertIsNone(window.job)
            self.assertEqual(window.last_job_result['code'],53)
        finally:window.close()


if __name__=='__main__':unittest.main()
