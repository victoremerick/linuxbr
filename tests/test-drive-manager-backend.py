#!/usr/bin/env python3
"""Exercise D-Bus dispatch with doubles, never real mounts."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager'))
import backend
from core import PREFIX


class Backend(unittest.TestCase):
    def setUp(self):
        self.objects = {'/volume': {PREFIX + 'Block': {'Device': b'/dev/vdb1\0', 'IdUUID': 'abc'}, PREFIX + 'Filesystem': {'MountPoints': []}}}
        self.manager = Mock()
        self.manager.GetManagedObjects.return_value = self.objects
        self.fs = Mock()
        self.fs.Mount.return_value = '/media/test'
        self.bus = Mock()
        self.patches = [patch.object(backend.dbus, 'SystemBus', return_value=self.bus),
                        patch.object(backend.dbus, 'Interface', side_effect=lambda obj, iface: self.manager if iface == 'org.freedesktop.DBus.ObjectManager' else self.fs)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    def invoke(self, *args):
        with patch.object(sys, 'argv', ['backend.py', *args]): return backend.main()

    def test_mount_and_unmount_use_dbus(self):
        self.assertEqual(self.invoke('mount', '/volume', 'uuid:abc', '/dev/vdb1'), '/media/test')
        self.fs.Mount.assert_called_once()
        self.invoke('unmount', '/volume', 'uuid:abc', '/dev/vdb1')
        self.fs.Unmount.assert_called_once()

    def test_reject_disconnected_and_changed_device(self):
        for path, key, dev in [('/gone', 'uuid:abc', '/dev/vdb1'), ('/volume', 'uuid:old', '/dev/vdb1'), ('/volume', 'uuid:abc', '/dev/vdc1')]:
            with self.assertRaises(ValueError): self.invoke('mount', path, key, dev)
        self.fs.Mount.assert_not_called()

    def test_root_and_unknown_identity_never_unmounted(self):
        self.objects['/volume'][PREFIX + 'Filesystem']['MountPoints'] = [b'/\0']
        with self.assertRaises(ValueError): self.invoke('unmount', '/volume', 'uuid:abc', '/dev/vdb1')
        self.objects['/volume'][PREFIX + 'Filesystem']['MountPoints'] = []
        self.objects['/volume'][PREFIX + 'Block']['IdUUID'] = ''
        with self.assertRaises(ValueError): self.invoke('unmount', '/volume', '', '/dev/vdb1')
        self.fs.Unmount.assert_not_called()

    def test_authorization_error_propagated(self):
        self.fs.Mount.side_effect = RuntimeError('Not authorized')
        with self.assertRaisesRegex(RuntimeError, 'Not authorized'):
            self.invoke('mount', '/volume', 'uuid:abc', '/dev/vdb1')

if __name__ == '__main__': unittest.main()
