#!/usr/bin/python3
"""Visible app actions and safe host changes at the target screen size."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication,QScrollArea
from PyQt6.QtCore import QPoint
import store_frontend,virtualization
APP=QApplication.instance() or QApplication([])


def wait(callback,seconds=35):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        APP.processEvents();time.sleep(.02)
        if callback():return True
    return False


class PlatformWindows(unittest.TestCase):
    def test_vm_controls_reflect_selection_filter_and_power_state(self):
        with patch.object(virtualization.Window,'refresh'):
            window = virtualization.Window('test:///default')
        self.addCleanup(window.close)
        window.timer.stop()
        self.assertFalse(window.pages.isEnabled())
        offline = dict(id='one', name='Arquivos', state='Desligada', active=False, memory=2048, cpus=2, cpu_ns=0)
        paused = dict(id='two', name='Teste', state='Pausada', active=True, memory=2048, cpus=2, cpu_ns=0)
        fixture = dict(domains=[offline,paused],networks=[],pools=[],capabilities={'kind':'kvm'})
        window.loaded(fixture)
        self.assertFalse(window.vm_controls['start'].isEnabled())
        window.vms.selectRow(0)
        self.assertTrue(window.vm_controls['start'].isEnabled())
        self.assertFalse(window.vm_controls['poweroff'].isEnabled())
        window.vm_search.setText('Teste')
        self.assertIsNone(virtualization.selected(window.vms))
        window.vms.selectRow(1)
        self.assertTrue(window.vm_controls['resume'].isEnabled())
        self.assertFalse(window.vm_controls['pause'].isEnabled())
        with patch.object(window,'action') as action:
            window.vm_controls['resume'].trigger()
            action.assert_called_once_with('resume')
        window.loaded(dict(fixture,domains=[offline]))
        self.assertIsNone(virtualization.selected(window.vms))
        self.assertFalse(window.vm_controls['resume'].isEnabled())

    def test_store_primary_action_stays_visible_while_details_scroll(self):
        with patch('webapp_icons.request_refresh'):
            window=store_frontend.Window();window.show()
            self.assertTrue(wait(lambda:not window.queries and not window.sources.jobs and not window.firmware_page.jobs))
            window.note.setText('Detalhes adicionais do aplicativo. '*500);APP.processEvents()
            origin=window.primary.mapTo(window,QPoint(0,0))
            for area in window.findChildren(QScrollArea):area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
            APP.processEvents()
            self.assertTrue(window.primary.isVisible());self.assertEqual(window.primary.mapTo(window,QPoint(0,0)),origin)
            self.assertTrue(window.rect().contains(origin));self.assertLess(origin.y()+window.primary.height(),680)
            window.close()

    def test_switching_hosts_clears_old_storage_before_connecting(self):
        window=virtualization.Window('test:///default');window.show();self.assertTrue(wait(lambda:not window.tasks))
        connection=window.manager;window.refresh();self.assertTrue(wait(lambda:not window.tasks));self.assertIs(window.manager,connection)
        window.vm_search.setText('nenhuma-maquina-com-este-nome');self.assertIsNone(virtualization.selected(window.vms));window.vm_search.clear()
        self.assertTrue(window.data);window.address.setText('qemu+ssh://usuario@servidor/system')
        with patch.object(window,'work') as work:window.connect_host();work.assert_called_once()
        self.assertEqual(window.data,{});self.assertEqual(window.pools.rowCount(),0);self.assertFalse(window.pages.isEnabled());window.close()


if __name__=='__main__':unittest.main(verbosity=2)
