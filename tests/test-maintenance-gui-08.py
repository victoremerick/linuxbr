#!/usr/bin/python3
"""Exercise asynchronous page results and explicit actions with isolated workers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication,QMessageBox
import maintenance
from migration_backend import check_cancel

APP=QApplication.instance() or QApplication([])


def plan(category='cache'):
    return {'category':category,'root':'/private/'+category,'entries':[{'parts':['fixture']}],
            'bytes':4,'skipped':0,'errors':[]}


def protection():
    return {'backups':[],'snapshots':{'configured':False,'destination_available':False,'last_success':None,'last':{}},
            'preflight':{'checked_at':'2026-11-03T20:00:00+00:00','free':4096,'warnings':[],'dpkg_audit':''},'indexes':[]}


class MaintenanceGUI08(unittest.TestCase):
    def setUp(self):
        self.widgets=[];self.events=[]
        for name in ('launch',):
            mocked=patch.object(maintenance,name);value=mocked.start();self.addCleanup(mocked.stop);setattr(self,name,value)
        warning=patch.object(QMessageBox,'warning');self.warning=warning.start();self.addCleanup(warning.stop)

    def tearDown(self):
        for event in self.events:event.set()
        for widget in self.widgets:
            page=widget.page if isinstance(widget,maintenance.MaintenanceWindow) else widget
            for job in page.jobs:job.cancel.set()
            self.wait(page)
            widget.close()
        APP.processEvents()

    def page(self, section='storage'):
        page=maintenance.MaintenancePage(section);self.widgets.append(page);return page

    def events_pair(self):
        started=threading.Event();release=threading.Event();self.events.append(release);return started,release

    def wait(self,page):
        deadline=time.monotonic()+5
        while page.jobs and time.monotonic()<deadline:
            APP.processEvents();time.sleep(.003)
        APP.processEvents();self.assertFalse(page.jobs,'O worker não terminou no prazo do teste.')

    def test_construction_preview_and_queries_do_not_launch_or_clean(self):
        with (patch.object(maintenance,'scan',return_value=plan()),patch.object(maintenance,'clean') as clean,
              patch.object(maintenance,'protection_report',return_value=protection())):
            page=self.page();APP.processEvents();self.launch.assert_not_called();clean.assert_not_called()
            page.scan_cleanup.click();self.wait(page)
            self.assertTrue(page.apply_cleanup.isEnabled());clean.assert_not_called();self.launch.assert_not_called()
            page.check_protection.click();self.wait(page);self.launch.assert_not_called();clean.assert_not_called()

    def test_late_scan_does_not_replace_the_new_category_preview(self):
        started,release=self.events_pair()
        def scan(category,cancel,progress):
            started.set();release.wait(3);return plan(category)
        with patch.object(maintenance,'scan',side_effect=scan),patch.object(maintenance,'clean') as clean:
            page=self.page();page.preview_cleanup();self.assertTrue(started.wait(2))
            self.assertFalse(page.category.isEnabled())
            # Programmatic changes also invalidate callbacks, despite the disabled control.
            page.category.setCurrentIndex(1);release.set();self.wait(page)
            self.assertEqual(page.category.currentData(),'trash');self.assertIsNone(page.cleanup_plan)
            self.assertFalse(page.apply_cleanup.isEnabled());self.assertTrue(page.category.isEnabled())
            page.run_cleanup();clean.assert_not_called();self.launch.assert_not_called()

    def test_scan_can_be_cancelled_without_deletion_or_error_dialog(self):
        started,release=self.events_pair()
        def scan(category,cancel,progress):
            started.set();release.wait(3);check_cancel(cancel);return plan(category)
        with patch.object(maintenance,'scan',side_effect=scan),patch.object(maintenance,'clean') as clean:
            page=self.page();page.preview_cleanup();self.assertTrue(started.wait(2))
            self.assertTrue(page.cancel_cleanup.isEnabled());page.cancel_cleanup.click();release.set();self.wait(page)
            self.assertIsNone(page.cleanup_plan);self.assertIsNone(page.cleanup_job)
            self.assertIn('Conferência cancelada',page.cleanup_text.toPlainText())
            self.assertTrue(page.scan_cleanup.isEnabled());self.assertTrue(page.category.isEnabled())
            clean.assert_not_called();self.warning.assert_not_called()

    def test_late_diagnostic_keeps_current_problem_and_actions(self):
        started,release=self.events_pair()
        def diagnose(problem):
            started.set();release.wait(3)
            return {'problem':problem,'help':'RESULTADO DA CATEGORIA ANTERIOR','results':[]}
        with patch.object(maintenance,'diagnose',side_effect=diagnose):
            page=self.page('diagnostics');page.run_diagnostics();self.assertTrue(started.wait(2))
            page.problem.setCurrentIndex(1);expected=maintenance.PROBLEMS[page.problem.currentText()]['help']
            release.set();self.wait(page)
            self.assertEqual(page.diagnostic_text.toPlainText(),expected)
            self.assertIsNone(page.diagnostic_job);self.assertTrue(page.diagnose_button.isEnabled());self.launch.assert_not_called()

    def test_cleanup_requires_the_two_explicit_confirmations(self):
        result={'cancelled':False,'removed':1,'changed_or_retained':0,'errors':[]}
        with (patch.object(maintenance,'scan',return_value=plan()),patch.object(maintenance,'clean',return_value=result) as clean,
              patch.object(QMessageBox,'information'),patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No) as question):
            page=self.page();page.preview_cleanup();self.wait(page)
            page.apply_cleanup.click();clean.assert_not_called();question.assert_not_called()
            page.closed_apps.setChecked(True);page.apply_cleanup.click();clean.assert_not_called()
            question.return_value=QMessageBox.StandardButton.Yes;page.apply_cleanup.click();self.wait(page)
            clean.assert_called_once();self.assertIsNone(page.cleanup_job);self.assertIsNone(page.cleanup_plan)
            self.assertTrue(page.scan_cleanup.isEnabled());self.assertTrue(page.category.isEnabled());self.launch.assert_not_called()

    def test_fast_and_failed_cleanup_workers_always_release_controls(self):
        page=self.page();page.closed_apps.setChecked(True)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
            with patch.object(maintenance,'clean',return_value={'cancelled':False,'removed':1,'changed_or_retained':0,'errors':[]}):
                for _attempt in range(25):
                    page.cleanup_plan=plan();page.run_cleanup();self.wait(page)
                    self.assertIsNone(page.cleanup_job);self.assertTrue(page.scan_cleanup.isEnabled());self.assertTrue(page.category.isEnabled())
            with patch.object(maintenance,'clean',side_effect=OSError('Destino desconectado')):
                page.cleanup_plan=plan();page.run_cleanup();self.wait(page)
                self.assertIsNone(page.cleanup_job);self.assertTrue(page.category.isEnabled());self.assertTrue(page.scan_cleanup.isEnabled())
                self.warning.assert_called_once()

    def test_close_cancels_pending_update_query_without_opening_an_app(self):
        started,release=self.events_pair()
        def query():started.set();release.wait(3);return protection()
        window=maintenance.MaintenanceWindow('protection');self.widgets.append(window);window.show();APP.processEvents()
        with patch.object(maintenance,'protection_report',side_effect=query),patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes) as question:
            window.page.open_updates();self.assertTrue(started.wait(2))
            self.assertFalse(window.close());self.assertTrue(window.isVisible())
            release.set();self.wait(window.page)
            self.launch.assert_not_called();question.assert_not_called();self.warning.assert_not_called()
            self.assertTrue(window.close());self.assertFalse(window.isVisible())

    def test_close_during_cleanup_still_shows_completed_removal_counts(self):
        started,release=self.events_pair()
        def clean(current,cancel,progress):
            started.set();release.wait(3)
            return {'cancelled':cancel.is_set(),'removed':2,'changed_or_retained':1,'errors':[]}
        window=maintenance.MaintenanceWindow('storage');self.widgets.append(window);window.show();APP.processEvents()
        with patch.object(maintenance,'clean',side_effect=clean),patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
            window.page.cleanup_plan=plan();window.page.closed_apps.setChecked(True);window.page.run_cleanup();self.assertTrue(started.wait(2))
            self.assertFalse(window.close());release.set();self.wait(window.page)
            text=window.page.cleanup_text.toPlainText();self.assertIn('Limpeza cancelada',text);self.assertIn('2 itens removidos',text)
            self.assertTrue(window.close());self.warning.assert_not_called()


if __name__=='__main__':unittest.main()
