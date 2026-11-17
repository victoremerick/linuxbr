#!/usr/bin/env python3
"""Regressões de restauração de prefixos, revisões web e privacidade."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0, str(MODULES))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidgetItem, QMessageBox
import compatibility_report
import isolated_document
import local_certificates
import webapp_updates
import windows_auth
import windows_graphics
import windows_recipes
import windows_runner

APP = QApplication.instance() or QApplication([])


def certificate(name, now):
    key = ec.generate_private_key(ec.SECP256R1())
    label = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
    return (x509.CertificateBuilder().subject_name(label).issuer_name(label)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
        .sign(key,hashes.SHA256()).public_bytes(serialization.Encoding.PEM))


class PrivacyTests(unittest.TestCase):
    def test_component_lookup_lists_applications_and_architectures(self):
        component = dict(id='vc',filename='vc_redist.exe',source='https://vendor.example/',
                         name='Visual C++',note='Runtime')
        entries=[dict(id='a',name='Editor',architecture='win32',dependencies=[component]),
                 dict(id='b',name='Jogo',architecture='win64',dependencies=[component])]
        catalog=windows_recipes.component_catalog({'recipes':entries})
        self.assertEqual(len(catalog),1)
        self.assertEqual(catalog[0]['recipes'],[dict(id='a',name='Editor',architecture='win32'),
                                             dict(id='b',name='Jogo',architecture='win64')])

    def test_detects_listener_and_connection_in_selected_prefix(self):
        script=('import socket, sys\n'
                'with socket.socket() as listener:\n'
                '    listener.bind(("127.0.0.1",0))\n'
                '    listener.listen()\n'
                '    print(listener.getsockname()[1],flush=True)\n'
                '    connection,_=listener.accept()\n'
                '    with connection:\n'
                '        print("aceita",flush=True)\n'
                '        sys.stdin.read()\n')
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/'prefix'
            with subprocess.Popen([sys.executable,'-u','-c',script],text=True,stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,env=dict(os.environ,WINEPREFIX=str(prefix))) as receiver:
                try:
                    port=int(receiver.stdout.readline())
                    proc=Path('/proc')
                    tables=(proc/'net/tcp').read_text()
                    if not tables:
                        # WSL1 exposes descriptors but leaves TCP tables empty.
                        proc=Path(directory)/'proc'
                        (proc/'net').mkdir(parents=True)
                        (proc/str(receiver.pid)).symlink_to(Path('/proc')/str(receiver.pid),target_is_directory=True)
                        inode=next(iter(windows_auth.socket_owners(prefix,proc)))
                        header='sl local_address rem_address st tx tr retr uid timeout inode\n'
                        address=f'0100007F:{port:04X}'
                        tables=header+f'0: {address} 00000000:0000 0A 0 0 0 0 0 {inode}\n'
                        (proc/'net/tcp').write_text(tables)
                    self.assertIn(port,windows_auth.transport(prefix,proc)[0])
                    self.assertNotIn(port,windows_auth.transport(prefix,proc)[1])
                    self.assertEqual(windows_auth.transport(prefix/'outro',proc),(set(),set()))
                    with socket.create_connection(('127.0.0.1',port),timeout=3):
                        self.assertEqual(receiver.stdout.readline().strip(),'aceita')
                        if proc != Path('/proc'):
                            accepted=windows_auth.socket_owners(prefix,proc)-{inode}
                            self.assertEqual(len(accepted),1)
                            (proc/'net/tcp').write_text(tables+f'1: {address} 0100007F:C000 01 0 0 0 0 0 {accepted.pop()}\n')
                        self.assertIn(port,windows_auth.transport(prefix,proc)[1])
                finally:
                    receiver.stdin.close()
                    if receiver.poll() is None:receiver.terminate()
                    receiver.wait(timeout=3)

    def test_graphics_options_apply_only_to_the_registered_program(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'XDG_DATA_HOME':directory}):
            environment=windows_runner.create_environment('Jogos')
            executable=Path(directory)/'jogo com espaços.exe'
            header=bytearray(64)
            header[:2]=b'MZ'
            struct.pack_into('<I',header,60,64)
            executable.write_bytes(header+b'PE\0\0\x64\x86')
            item=windows_runner.register_program(environment,executable,'Jogo de teste')
            self.assertEqual(windows_graphics.read(item)['current'],windows_graphics.DEFAULT)
            settings=dict(renderer='wined3d',window='1280x768')
            windows_graphics.save(item,settings)
            self.assertEqual(windows_graphics.read(item)['previous'],windows_graphics.DEFAULT)
            path=r'C:\Games\jogo com espaços.exe'
            with patch.object(windows_graphics.subprocess,'check_output',return_value=path+'\n'):
                command,env=windows_graphics.apply_launch(item,environment,executable,[],{})
            self.assertIn('1280x768',command[2])
            self.assertEqual(command[-1],path)
            self.assertEqual(env[windows_graphics.PROGRAM_MARKER],item)
            self.assertEqual(env['WINEDLLOVERRIDES'],'d3d9,d3d10core,d3d11,dxgi=b')
            with self.assertRaisesRegex(ValueError,'outro atalho'):
                windows_graphics.apply_launch(item,'different',executable,[],{})
            with patch.object(windows_runner.subprocess,'Popen') as launch:
                windows_runner.start_job(environment,'run',executable,item)
                self.assertEqual(launch.call_args.args[0][-2:],['--program-id',item])
            windows_graphics.save(item,windows_graphics.DEFAULT)
            self.assertEqual(windows_graphics.read(item)['previous'],settings)

    def test_steam_graphics_exports_only_documented_options(self):
        self.assertEqual(windows_graphics.steam_option('environment','normal'),'')
        self.assertEqual(windows_graphics.steam_option('wined3d','normal'),'PROTON_USE_WINED3D=1 %command%')
        self.assertEqual(windows_graphics.steam_option('environment','1280x768'),
                         'gamescope -w 1280 -h 768 -W 1280 -H 768 -- %command%')
        with self.assertRaises(ValueError):
            windows_graphics.steam_option('environment','arbitraria')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'XDG_DATA_HOME':directory}):
            dialog=windows_graphics.SteamGraphics(dict(name='Jogo',id='1234'),True)
            dialog.renderer.setCurrentIndex(1)
            dialog.window.setCurrentIndex(3)
            dialog.copy_option()
            self.assertIn('PROTON_USE_WINED3D=1 gamescope',APP.clipboard().text())
            self.assertEqual(dialog.state['previous'],windows_graphics.DEFAULT)
            self.assertTrue(dialog.previous.isEnabled())
            dialog.previous.click()
            self.assertEqual(dialog.option.toPlainText(),'%command%')

    def test_report_attaches_versions_gpu_and_evidence_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            display=root/'card0/device'
            display.mkdir(parents=True)
            (display/'uevent').write_text('DRIVER=amdgpu\nPCI_ID=1002:15DD\n')
            evidence=root/'ensaio.png'
            evidence.write_bytes(b'captura')
            devices=compatibility_report.gpu_inventory(root)
            self.assertEqual(devices[0]['driver'],'amdgpu')
            with patch.object(compatibility_report,'gpu_inventory',return_value=devices), \
                    patch.object(compatibility_report,'current_version',return_value='1.1.1~alpha1'):
                report=compatibility_report.report_document('Aplicativo','3.6.1','Wine','10.0',
                    [compatibility_report.CHECKS[0]],'Passou',str(evidence))
            self.assertEqual(report['application'],{'name':'Aplicativo','version':'3.6.1'})
            self.assertEqual(report['environment']['version'],'10.0')
            self.assertEqual(report['environment']['gpus'][0]['pci_id'],'1002:15DD')
            self.assertTrue(report['environment']['displays']['session'])
            self.assertEqual(report['evidence']['file'],'ensaio.png')
            self.assertNotIn(directory,json.dumps(report))

    def test_window_checks_distinguish_shortcuts_and_active_monitors(self):
        dimensions = {'session':'wayland','screens':[dict(width=1920,height=1080,scale=1.0)]}
        with patch.object(compatibility_report,'display_context',return_value=dimensions):
            report = compatibility_report.CompatibilityReport('Aplicativo','Proton','10.0')
            window_actions = {control.text():control for control in report.checks}
            self.assertIn('Alt+Tab',window_actions['Atalhos de janelas'].toolTip())
            self.assertFalse(window_actions['Múltiplos monitores'].isEnabled())
        dimensions['screens'].append(dict(width=1280,height=768,scale=1.0))
        with patch.object(compatibility_report,'display_context',return_value=dimensions):
            report = compatibility_report.CompatibilityReport('Aplicativo','Wine','10.0')
            self.assertTrue(report.checks[-1].isEnabled())

    def test_isolated_viewer_loads_only_selected_document(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory)/'documento tamanho.pdf'
            document.write_bytes(b'exemplo')
            with patch.object(isolated_document.os,'access',return_value=True):
                args = isolated_document.sandbox_command(document, '/tmp/compositor/wayland-0')
            self.assertIn('--unshare-all',args)
            self.assertIn('--new-session',args)
            self.assertIn('--disable-userns',args)
            self.assertNotIn('--share-net',args)
            self.assertNotIn(str(Path.home()),args)
            self.assertNotIn('/tmp/compositor',args)
            self.assertEqual(args[args.index(str(document))-1],'--ro-bind')
            self.assertEqual(args[-3:],['--','/usr/bin/okular','/documento/arquivo.pdf'])

    def test_inventory_distinguishes_trusted_and_organization_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now(timezone.utc).replace(microsecond=0)
            trust = root/'trusted'
            distro = root/'distribution'
            admin = root/'admin'
            organization = admin/'linuxbr-organizacao'
            for path in (trust,distro,organization):
                path.mkdir(parents=True,exist_ok=True)
            ca = certificate('Sistema',now)
            company = certificate('Organização',now)
            (distro/'system.crt').write_bytes(ca)
            (organization/'organization.crt').write_bytes(company)
            (trust/'system.pem').symlink_to(distro/'system.crt')
            (trust/'organization.pem').symlink_to(organization/'organization.crt')
            (trust/'untrusted.pem').write_bytes(certificate('Fora',now))
            (trust/'ca-certificates.crt').write_bytes(ca + company)
            with patch.multiple(local_certificates, DISTRIBUTION=distro, ADMIN=admin, ORGANIZATION=organization):
                items=local_certificates.inventory(trust,now)
            self.assertEqual({r['origin'] for r in items}, {'Distribuição','Pasta da organização'})
            self.assertEqual({r['status'] for r in items}, {'Em vigor'})
            self.assertEqual(len({r['digest'] for r in items}),2)

    def test_restore_creates_independent_environment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'XDG_DATA_HOME':directory}), \
                patch.object(windows_runner.os,'geteuid',return_value=1000), \
                patch.object(windows_recipes,'ensure_idle'):
            identifier = windows_runner.create_environment('Aplicativo')
            prefix = windows_runner.environment_path(identifier)/'prefix'
            prefix.mkdir()
            (prefix/'system.reg').write_text('versão anterior')
            (prefix/'externo').symlink_to('/home/fora')
            copy = windows_recipes.backup_environment(identifier)
            (prefix/'system.reg').write_text('versão atual')
            self.assertEqual(windows_recipes.environment_backups(identifier),[(copy.name,'Aplicativo')])
            restored = windows_recipes.restore_environment(identifier,copy.name)
            self.assertNotEqual(restored,identifier)
            self.assertEqual((prefix/'system.reg').read_text(),'versão atual')
            new = windows_runner.environment_path(restored)/'prefix'
            self.assertEqual((new/'system.reg').read_text(),'versão anterior')
            self.assertTrue((new/'externo').is_symlink())
            self.assertEqual(windows_runner.read_environment(restored)['name'],'Aplicativo — restaurado')

    def test_installer_runs_after_backup_under_same_environment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'XDG_DATA_HOME':directory}), \
                patch.object(windows_runner.os,'geteuid',return_value=1000), \
                patch.object(windows_recipes,'ensure_idle'):
            identifier=windows_runner.create_environment('Aplicativo')
            installer=Path(directory)/'instalador.msi'
            installer.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1'))
            order=[]
            def backup(current):
                order.append(('cópia',current))
                return Path(directory)/'copia'
            def install(current,operation,filename):
                order.append(('instalador',current,operation,filename))
                return 0
            with patch.object(windows_recipes,'backup_environment',backup), \
                    patch.object(windows_runner,'_run',install), \
                    patch.object(windows_recipes.subprocess,'run'):
                self.assertEqual(windows_recipes.maintain(identifier,'installer',filename=str(installer)),0)
            self.assertEqual(order,[('cópia',identifier),('instalador',identifier,'run',str(installer))])

    def test_signed_change_requires_confirmation_and_opens_clean_offer(self):
        with patch.object(webapp_updates.WebUpdates,'refresh'):
            widget=webapp_updates.WebUpdates()
        row=dict(current_url='https://anterior.example/', url='https://novo.example/', name='Aplicativo',
                 changed_url=True, disabled=False, source='fonte', app='app', changelog='Mudou',
                 upstream_version='', upstream_release_url='')
        item=QListWidgetItem('Aplicativo')
        item.setData(Qt.ItemDataRole.UserRole,row)
        widget.list.addItem(item)
        widget.list.setCurrentRow(0)
        self.assertIn(row['current_url'],widget.detail.text())
        with patch.object(webapp_updates.QProcess,'startDetached',return_value=(True,1)) as launch, \
                patch.object(QMessageBox,'exec',return_value=0), \
                patch.object(QMessageBox,'clickedButton',return_value=None):
            widget.open_new()
            launch.assert_not_called()
        original=QMessageBox.buttons
        def selected(prompt):
            return next(button for button in original(prompt) if button.text()=='Continuar em perfil limpo')
        with patch.object(webapp_updates.QProcess,'startDetached',return_value=(True,1)) as launch, \
                patch.object(QMessageBox,'exec',return_value=0), \
                patch.object(QMessageBox,'clickedButton',selected):
            widget.open_new()
            args=launch.call_args.args[1]
            self.assertEqual(args[0],'--offer')
            self.assertTrue(json.loads(args[1])['new_session'])


if __name__ == '__main__':
    unittest.main()
