#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-device-manager/files/usr/lib/linuxbr-device-manager'))
from PyQt6.QtWidgets import QApplication,QMessageBox
from devices import Devices
application=QApplication([])
class Preview(Devices):
    def refresh(self):pass
window=Preview();window.timer.stop();window.resize(1380,800)
fixture=dict(kernel='6.12-test',architecture='x86_64',warnings=[],diagnostics=['test private log'],
 devices=[dict(id='pci:0000:01:00.0',name='Wi-Fi Intel',category='Rede',bus='PCI',vendor='Intel',hardware_id='8086:1234',
               driver='iwlwifi',modules=['iwlwifi'],modalias='pci:test',status='Driver associado'),
          dict(id='usb:1-1',name='Teclado USB',category='USB',bus='USB',vendor='Fabricante',hardware_id='1234:0001',driver='usbhid',modules=[],modalias='',status='Driver associado')],
 modules={'iwlwifi':dict(firmware=[dict(name='example.ucode',present=False)])},
 firmware=[dict(package='firmware-iwlwifi',description='Wi-Fi Intel',type='Firmware',installed='',installed_version='',candidate='1.0',related=True,
                devices=[dict(id='pci:0000:01:00.0',name='Wi-Fi Intel',reason='Driver detectado')],action='install',status='Disponível para instalar'),
           dict(package='firmware-realtek',description='Rede Realtek',type='Firmware',installed='',installed_version='',candidate='',related=False,
                devices=[],action='',status='Indisponível nos índices locais'),
           dict(package='linux-image-amd64',description='Kernel e drivers integrados',type='Kernel',installed='installed 6.12.1',installed_version='6.12.1',candidate='6.12.2',related=True,
                devices=[],action='upgrade',status='Atualização disponível')])
window.populate(fixture)
assert window.table.rowCount()==2
window.search.setText('Intel');assert window.table.rowCount()==1
assert 'Não encontrado: example.ucode' in window.details.toPlainText()
assert len(window.software_rows)==2 # unrelated firmware hidden by default
window.show_device_options();assert len(window.software_rows)==1
assert window.selected_software()['package']=='firmware-iwlwifi'
window.clear_device_filter();assert len(window.software_rows)==2
window.search.clear();window.category.setCurrentText('USB');assert window.table.rowCount()==1
window.show_device_options();assert not window.software_rows
assert not window.install_button.isEnabled()
window.clear_device_filter();window.category.setCurrentIndex(0)
window.show_all.setChecked(True);assert len(window.software_rows)==3
index=next(i for i,r in enumerate(window.software_rows) if r['package']=='firmware-realtek')
window.firmware_table.selectRow(index);assert not window.install_button.isEnabled()
window.show_all.setChecked(False)
window.firmware_table.selectRow(0);assert window.install_button.text()=='Instalar selecionado…'
calls=[];window.run=lambda *args:calls.append(args)
with patch('devices.QMessageBox.question',return_value=QMessageBox.StandardButton.No):window.install_selected()
assert not calls
with patch('devices.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):window.install_selected()
assert calls==[('/usr/bin/pkexec',['/usr/lib/linuxbr-device-manager/install-firmware','firmware-iwlwifi'],True)]
window.firmware_table.selectRow(1);assert window.install_button.text()=='Atualizar selecionado…'
with patch('devices.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes) as question:window.install_selected()
assert calls[-1][1][-1]=='linux-image-amd64'
assert 'kernel Debian' in question.call_args[0][2]
window.check_updates();assert calls[-1][1][-1]=='--refresh'
window.process=object();window.update_install_button()
assert not window.install_button.isEnabled() and not window.check_updates_button.isEnabled()
window.process=None;window.update_install_button()
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'report.json'
    with patch('devices.QFileDialog.getSaveFileName',return_value=(str(path),'')):window.export_report()
    report=json.loads(path.read_text());assert 'diagnostics' not in report
    assert report['devices'][0]['driver']=='iwlwifi'
window.installing=True;assert not window.shutdown();window.installing=False
window.show();application.processEvents()
assert window.grab().save(os.environ.get('DEVICE_PREVIEW','/tmp/linuxbr-devices.png'))
# Refresh must also remove obsolete choices after hardware/package state changes.
fixture['firmware'][0].update(action='',status='Atualizado',installed_version='1.0')
window.populate(fixture);window.firmware_table.selectRow(next(i for i,r in enumerate(window.software_rows) if r['package']=='firmware-iwlwifi'))
assert not window.install_button.isEnabled()
fixture['firmware'].append(dict(package='nvidia-driver',description='NVIDIA',type='Proprietário',related=True,
    devices=[dict(id='gpu',name='GPU teste',reason='Detector Debian')],installed='',installed_version='',candidate='550.1',
    action='install',status='Disponível para instalar',prerequisites=['linux-headers-test','linux-headers-amd64','dkms']))
window.populate(fixture)
window.firmware_table.selectRow(next(i for i,r in enumerate(window.software_rows) if r['package']=='nvidia-driver'))
with patch('devices.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes) as question:window.install_selected()
assert calls[-1][1][-1]=='nvidia-driver' and 'DKMS' in question.call_args[0][2]
fixture['firmware'][-1].update(action='',status='Secure Boot: cadastre MOK')
window.populate(fixture)
window.firmware_table.selectRow(next(i for i,r in enumerate(window.software_rows) if r['package']=='nvidia-driver'))
assert not window.install_button.isEnabled()
window.shutdown();window.close()
print('PASS: device-specific options, unrelated firmware hidden, versions, install/update/refresh routing, confirmation and report')
