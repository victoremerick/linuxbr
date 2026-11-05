#!/usr/bin/env python3
"""Partition planning/dispatch on synthetic UDisks objects. No real device writes."""
import copy
import os
import fcntl
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
from core import PREFIX, inventory
from partitioning import MIB, describe, plan, annotate
import partition_worker as worker


def fixture():
    return {
        '/drive': {PREFIX+'Drive': {'Serial': 'TEST-ONLY', 'TimeDetected': 100}},
        '/disk': {PREFIX+'Block': {'Device': b'/dev/fixture\0', 'DeviceNumber': 999, 'Size': 1024*MIB, 'Drive': '/drive'},
                  PREFIX+'PartitionTable': {'Type': 'gpt', 'Partitions': ['/p1']}},
        '/p1': {PREFIX+'Block': {'Device': b'/dev/fixture1\0', 'Size': 256*MIB, 'Drive': '/drive', 'IdUsage': 'filesystem', 'IdType': 'ext4', 'IdUUID': 'fs1'},
                PREFIX+'Partition': {'Table': '/disk', 'Offset': MIB, 'Size': 256*MIB, 'Number': 1, 'UUID': 'part1', 'Type': '0fc63daf-8483-4772-8e79-3d69d8477de4'},
                PREFIX+'Filesystem': {'MountPoints': []}},
    }


class Partitions(unittest.TestCase):
    def setUp(self):
        self.objects = fixture()
        self.snapshot = describe(self.objects, '/disk')
        self.request = dict(action='resize', disk='/disk', token=self.snapshot['token'], path='/p1', size=128*MIB, format='ext4', start=257*MIB)
        self.manager = Mock(); self.manager.GetManagedObjects.side_effect = lambda **kwargs: copy.deepcopy(self.objects)
        self.bus = Mock(); self.bus.get_object.side_effect = lambda service, path: path
        self.calls = []
        self.interfaces = {}
        for name in ('Manager', 'Filesystem', 'Partition', 'Block', 'PartitionTable'):
            self.interfaces[name] = Mock()
        self.interfaces['Manager'].CanFormat.return_value = (True, '')
        self.interfaces['Manager'].CanResize.return_value = (True, 6, '')
        self.interfaces['Manager'].CanCheck.return_value = (True, '')
        self.interfaces['Manager'].CanRepair.return_value = (True, '')
        self.interfaces['Filesystem'].Repair.side_effect = lambda *a, **kw: self.calls.append('prepare') or True
        self.interfaces['Filesystem'].Check.return_value = True
        self.interfaces['Filesystem'].Resize.side_effect = lambda *args, **kw: self.calls.append('filesystem')
        def partition_resize(size, *args, **kw):
            self.calls.append('partition'); self.objects['/p1'][PREFIX+'Partition']['Size'] = int(size)
            self.objects['/p1'][PREFIX+'Block']['Size'] = int(size)
        self.interfaces['Partition'].Resize.side_effect = partition_resize
        self.properties = Mock(); self.properties.Get.return_value = 128*MIB
        def iface(obj, name):
            if name == 'org.freedesktop.DBus.Properties': return self.properties
            return self.interfaces[name.removeprefix(PREFIX)]
        self.patch = patch.object(worker.dbus, 'Interface', side_effect=iface); self.patch.start(); self.addCleanup(self.patch.stop)

    def run_request(self, **changes):
        return worker.run(self.bus, self.manager, dict(self.request, **changes))

    def test_aligned_gap_and_annotations(self):
        self.assertEqual(self.snapshot['gaps'], [dict(start=257*MIB, size=766*MIB)])
        self.assertFalse(self.snapshot['reason'])
        rows = annotate(inventory(self.objects), self.objects)
        self.assertTrue(next(r for r in rows if r['path'] == '/p1')['partition_disk']['gaps'])

    def test_shrink_and_grow_order(self):
        self.run_request(); self.assertEqual(self.calls, ['prepare', 'filesystem', 'partition'])

    def test_grow_order(self):
        self.run_request(size=512*MIB); self.assertEqual(self.calls, ['prepare', 'partition', 'filesystem'])

    def test_failed_shrink_never_truncates_partition(self):
        self.interfaces['Filesystem'].Resize.side_effect = RuntimeError('minimum filesystem size')
        with self.assertRaisesRegex(ValueError, 'minimum filesystem size'): self.run_request()
        self.interfaces['Partition'].Resize.assert_not_called()

    def test_unknown_filesystem_size_never_truncates(self):
        self.properties.Get.return_value = 0
        with self.assertRaisesRegex(ValueError, 'confirmar'): self.run_request()
        self.interfaces['Partition'].Resize.assert_not_called()

    def test_failed_grow_reports_partial_without_rollback(self):
        self.interfaces['Filesystem'].Resize.side_effect = RuntimeError('denied')
        with self.assertRaisesRegex(ValueError, 'após ampliar'): self.run_request(size=512*MIB)
        self.interfaces['Partition'].Resize.assert_called_once()

    def test_mounted_readonly_configured_and_stale_rejected(self):
        variants = []
        for prop, value in [('ReadOnly', True), ('Configuration', [('fstab', {})])]:
            obj=fixture(); obj['/p1'][PREFIX+'Block'][prop]=value; variants.append(obj)
        obj=fixture(); obj['/p1'][PREFIX+'Filesystem']['MountPoints']=[b'/\0']; variants.append(obj)
        obj=fixture(); obj['/drive'][PREFIX+'Drive']['TimeDetected']=200; variants.append(obj)
        for obj in variants:
            self.objects=obj
            with self.assertRaises(ValueError): self.run_request(action='delete')
        self.interfaces['Partition'].Delete.assert_not_called()

    def test_busy_job_and_missing_tools(self):
        self.objects['/job']={PREFIX+'Job': {'Objects':['/p1']}}
        with self.assertRaisesRegex(ValueError, 'andamento'): self.run_request(action='format')
        del self.objects['/job']
        self.interfaces['Manager'].CanFormat.return_value=(False, 'mkfs.ext4')
        with self.assertRaisesRegex(ValueError, 'mkfs.ext4'): self.run_request(action='format')
        self.interfaces['Block'].Format.assert_not_called()

    def test_create_delete_format_dispatch(self):
        self.run_request(action='create', size=64*MIB)
        self.interfaces['PartitionTable'].CreatePartitionAndFormat.assert_called_once()
        self.run_request(action='format'); self.interfaces['Block'].Format.assert_called_once()
        self.run_request(action='delete'); self.interfaces['Partition'].Delete.assert_called_once()

    def test_limits_and_system_types(self):
        for change in [dict(size=1024*MIB), dict(size=0), dict(size=-1), dict(size=True)]:
            with self.assertRaises(ValueError): plan(self.snapshot, dict(self.request, **change))
        with self.assertRaises(ValueError): plan(self.snapshot, dict(self.request, action='create', start=MIB))
        self.objects['/p1'][PREFIX+'Partition']['Type']='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
        current=describe(self.objects, '/disk')
        with self.assertRaisesRegex(ValueError, 'protegida'): plan(current, dict(self.request, token=current['token'], action='delete'))

    def test_incomplete_and_extended_tables_not_editable(self):
        self.objects['/disk'][PREFIX+'PartitionTable']['Partitions'].append('/missing')
        self.assertTrue(describe(self.objects, '/disk')['reason'])
        self.assertFalse(describe(self.objects, '/disk')['gaps'])
        self.objects=fixture(); self.objects['/p1'][PREFIX+'Partition']['IsContainer']=True
        self.assertTrue(describe(self.objects, '/disk')['reason'])

    def test_resize_capability_check_and_filesystem_health(self):
        self.interfaces['Manager'].CanResize.return_value=(True, 4, '')
        with self.assertRaises(ValueError): self.run_request()
        self.interfaces['Manager'].CanResize.return_value=(True, 6, '')
        self.interfaces['Filesystem'].Check.return_value=False
        with self.assertRaisesRegex(ValueError, 'contém erros'): self.run_request()
        self.assertEqual(self.calls, [])
        self.interfaces['Filesystem'].Repair.assert_not_called()

    def test_preparation_failure_never_changes_sizes(self):
        self.interfaces['Filesystem'].Repair.side_effect = RuntimeError('Not authorized')
        with self.assertRaisesRegex(ValueError, 'preparação'): self.run_request()
        self.interfaces['Partition'].Resize.assert_not_called()
        self.interfaces['Filesystem'].Resize.assert_not_called()

    def test_failed_post_preparation_check_never_resizes(self):
        self.interfaces['Filesystem'].Check.side_effect = [True, False]
        with self.assertRaisesRegex(ValueError, 'após a preparação'): self.run_request()
        self.interfaces['Filesystem'].Repair.assert_called_once()
        self.interfaces['Filesystem'].Resize.assert_not_called()
        self.interfaces['Partition'].Resize.assert_not_called()

    def test_parallel_window_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            with open(Path(tmp)/'linuxbr-partitions.lock', 'w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, 'Outra operação'):
                    worker.execute(self.bus, self.manager, self.request)
        self.assertEqual(self.calls, [])

    def test_four_primary_mbr_and_authorization_denial(self):
        self.objects['/disk'][PREFIX+'PartitionTable']['Type']='dos'
        for index in range(1, 5):
            name=f'/p{index}'
            self.objects[name]=copy.deepcopy(self.objects['/p1'])
            self.objects[name][PREFIX+'Partition'].update(Offset=index*100*MIB, Size=32*MIB, Type='0x83', UUID=name)
        self.objects['/disk'][PREFIX+'PartitionTable']['Partitions']=['/p1','/p2','/p3','/p4']
        snap=describe(self.objects, '/disk')
        with self.assertRaisesRegex(ValueError, 'quatro'):
            plan(snap, dict(self.request, action='create', token=snap['token'], start=snap['gaps'][0]['start'], size=32*MIB))
        self.objects=fixture()
        self.interfaces['Block'].Format.side_effect=RuntimeError('Not authorized')
        with self.assertRaisesRegex(RuntimeError, 'Not authorized'): self.run_request(action='format')
        self.interfaces['Partition'].Delete.assert_not_called()

    def test_change_between_resize_phases_aborts(self):
        def swapped(*args, **kwargs):
            self.objects['/drive'][PREFIX+'Drive']['TimeDetected']=999
        self.interfaces['Filesystem'].Resize.side_effect=swapped
        with self.assertRaisesRegex(ValueError, 'mudou'): self.run_request()
        self.interfaces['Partition'].Resize.assert_not_called()

if __name__ == '__main__': unittest.main()
