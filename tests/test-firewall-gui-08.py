#!/usr/bin/env python3
"""Opening settings must not request firewall authorization implicitly."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtWidgets import QApplication, QPushButton
from firewall import Firewall

APP = QApplication.instance() or QApplication([])


class FirewallOpening(unittest.TestCase):
    def test_constructor_does_not_query_or_enable_mutations(self):
        with patch('firewall_backend.state') as query:
            window = Firewall()
            self.addCleanup(window.close)
            query.assert_not_called()
            self.assertIn('ainda não foi consultado', window.status.text())
            self.assertFalse(window.toggle.isEnabled())
            self.assertFalse(window.zone.isEnabled())
            self.assertFalse(window.add_rule.isEnabled())

    def test_explicit_query_loads_rules_and_enables_supported_actions(self):
        state = {'running': True, 'zone': 'public', 'zones': ['public'],
                 'details': {'public': {'services': [], 'ports': ['8080/tcp'],
                                       'rich': [], 'forward': [], 'service_ports': {}}},
                 'listeners': [{'app': 'programa', 'address': '127.0.0.1:8080', 'protocol': 'TCP'}]}
        with patch('firewall_backend.state', return_value=state) as query:
            window = Firewall()
            self.addCleanup(window.close)
            button = next(item for item in window.findChildren(QPushButton) if item.text() == 'Consultar estado e regras')
            button.click()
            query.assert_called_once_with()
            self.assertIn('zona padrão: public', window.status.text())
            self.assertTrue(window.toggle.isEnabled())
            self.assertTrue(window.zone.isEnabled())
            self.assertTrue(window.add_rule.isEnabled())
            self.assertEqual(window.ports.rowCount(), 1)
            self.assertEqual(window.apps.item(0, 0).text(), 'programa')

    def test_denied_query_keeps_mutations_disabled(self):
        with patch('firewall_backend.state', side_effect=PermissionError('Acesso recusado.')) as query:
            window = Firewall()
            self.addCleanup(window.close)
            window.refresh()
            query.assert_called_once_with()
            self.assertIn('Acesso recusado.', window.status.text())
            self.assertFalse(window.toggle.isEnabled())
            self.assertFalse(window.zone.isEnabled())
            self.assertFalse(window.add_rule.isEnabled())


if __name__ == '__main__':
    unittest.main()
