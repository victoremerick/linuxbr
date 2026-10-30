#!/usr/bin/env python3
"""Exercise task filtering and termination boundaries without signaling processes."""
import os
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication,QMessageBox
import tasks

APP=QApplication([])


class TaskManager(unittest.TestCase):
    def setUp(self):
        # A non-root fixture verifies ownership even when tests run in a container.
        self.uid=1234
        self.rows=[dict(pid=424242,name='Editor',user='teste',uid=self.uid,rss=1024,cpu=0),
                   dict(pid=1,name='systemd',user='root',uid=0,rss=1024,cpu=0),
                   dict(pid=os.getpid(),name='task-manager',user='teste',uid=self.uid,rss=1024,cpu=0)]
        self.snapshot=patch.object(tasks,'snapshot',return_value=(self.rows,{'MemTotal':4096,'MemAvailable':2048}))
        self.snapshot.start();self.addCleanup(self.snapshot.stop)
        self.window=tasks.Tasks();self.window.timer.stop()
        self.addCleanup(self.window.close)

    def row(self,pid):
        return next(i for i in range(self.window.table.rowCount()) if self.window.table.item(i,1).text()==str(pid))

    def test_filter(self):
        self.window.search.setText('EDITOR')
        self.assertFalse(self.window.table.isRowHidden(self.row(424242)))
        self.assertTrue(self.window.table.isRowHidden(self.row(1)))

    def test_protected_processes_and_confirmation(self):
        with patch.object(tasks.os,'getuid',return_value=self.uid),patch.object(tasks.os,'kill') as kill:
            for pid in (1,os.getpid()):
                self.window.table.selectRow(self.row(pid));self.window.end_task()
            kill.assert_not_called()
            self.window.table.selectRow(self.row(424242))
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):
                self.window.end_task()
            kill.assert_not_called()
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
                self.window.end_task()
            kill.assert_called_once_with(424242,signal.SIGTERM)


if __name__=='__main__':unittest.main()
