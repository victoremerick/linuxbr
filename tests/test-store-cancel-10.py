"""Cancellation follows the native manager's current permission."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
import store_transactions as transactions
from store_operations import Operations
APP=QApplication.instance() or QApplication([])


class NativeCancellation(unittest.TestCase):
    def manager(self):
        value=transactions.PackageKit.__new__(transactions.PackageKit)
        value.Gio=MagicMock();return value

    def test_critical_stage_is_not_cancelled(self):
        proxy=MagicMock();proxy.get_cached_property.return_value.unpack.return_value=False
        with patch.object(transactions,'emit'):
            self.assertFalse(self.manager().request_cancel(proxy))
        proxy.call_sync.assert_not_called()

    def test_allowed_cancel_uses_native_method(self):
        proxy=MagicMock();proxy.get_cached_property.return_value.unpack.return_value=True
        manager=self.manager()
        with patch.object(transactions,'emit'):
            self.assertTrue(manager.request_cancel(proxy))
        self.assertEqual(proxy.call_sync.call_args.args[0],'Cancel')

    def test_manager_rejection_does_not_claim_cancellation(self):
        proxy=MagicMock();proxy.get_cached_property.return_value.unpack.return_value=True
        proxy.call_sync.side_effect=RuntimeError('stage changed')
        with patch.object(transactions,'emit') as emit:
            self.assertFalse(self.manager().request_cancel(proxy))
        self.assertTrue(any('não aceitou' in call.kwargs.get('text','') for call in emit.call_args_list))

    def test_ui_sends_request_without_terminating_worker(self):
        window=Operations();process=MagicMock();window.process=process
        try:
            window.request_cancel();process.write.assert_not_called()
            window.cancel_current.setEnabled(True);window.request_cancel()
            process.write.assert_called_once_with(b'cancel\n')
            process.kill.assert_not_called();process.terminate.assert_not_called()
            self.assertFalse(window.cancel_current.isEnabled())
        finally:
            window.process=None;window.close()

    def test_ui_tracks_manager_permission_changes(self):
        window=Operations();window.process=MagicMock()
        try:
            for allowed in (True,False):
                window.process.readAllStandardOutput.return_value=(json.dumps(dict(event='cancelable',allowed=allowed))+'\n').encode()
                window.read_output();self.assertEqual(window.cancel_current.isEnabled(),allowed)
        finally:
            window.process=None;window.close()


if __name__=='__main__':unittest.main()
