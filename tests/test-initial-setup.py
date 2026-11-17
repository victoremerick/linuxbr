#!/usr/bin/env python3
"""Validate setup checkpoints, privilege boundaries, and the visible offline flow."""
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0, str(MODULES))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
import initial_setup as gui
import initial_setup_service as service

APP = QApplication.instance() or QApplication([])


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state = service.State(self.directory)
        self.setup = service.Setup(self.state)

    def test_rejects_skipping_steps_and_resumes_on_disk(self):
        marker = self.directory/'pending'
        marker.touch()
        with self.assertRaisesRegex(ValueError, 'etapas anteriores'):
            self.setup.call('finish', {})
        with self.assertRaisesRegex(ValueError, 'etapas anteriores'):
            self.setup.call('account', {'mode': 'local'})
        with patch.multiple(service, KEYBOARD_DEFAULTS=self.directory/'keyboard',
                            KEYBOARD_XORG=self.directory/'Xorg'):
            result = self.setup.call('keyboard', {'layout': 'br'})
        self.assertEqual(result['next'], 1)
        self.assertIn('XKBVARIANT="abnt2"', (self.directory/'keyboard').read_text())
        self.assertEqual(service.State(self.directory).next, 1)
        self.assertTrue(marker.exists())

    def test_retry_does_not_create_duplicate_account_or_log_password(self):
        for key, value in (('keyboard', 'br'), ('network', True), ('timezone', 'America/Sao_Paulo')):
            self.state.save(key, value)
        login = 'validacao'
        full_name = 'Validação Offline'
        credentials = dict(mode='local', username=login, display=full_name, password='senha de ensaio')
        user = [login, 'x', '1000', '1000', full_name, '/home/' + login, '/bin/bash']
        with patch.object(service, 'local_user', side_effect=[None, user]), \
                patch.object(service.pwd, 'getpwnam', side_effect=KeyError), \
                patch.object(service, 'uid_exists', return_value=False), \
                patch.object(service, 'command', side_effect=[b'', ValueError('temporário')]):
            with self.assertRaisesRegex(ValueError, 'temporário'):
                self.setup.call('account', credentials)
        resumed = service.Setup(service.State(self.directory))
        with patch.object(service, 'local_user', return_value=user), patch.object(service, 'command') as run:
            answer = resumed.call('account', credentials)
        self.assertEqual(answer['next'], 4)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ['/usr/sbin/chpasswd'])
        self.assertNotIn('senha de ensaio', resumed.state.path.read_text())
        self.assertNotIn('draft', resumed.state.data)

    def test_optional_catalog_retry_and_marker_completion(self):
        for key, value in (('keyboard', 'br'), ('network', True), ('timezone', 'America/Sao_Paulo'),
                           ('account', {'mode': 'local', 'login': 'validacao', 'uid': 1000})):
            self.state.save(key, value)
        (self.directory/'pending').touch()
        with patch.object(service, 'internet_available', return_value=False):
            self.assertEqual(self.setup.call('catalog', {}), {'apps': []})
        with patch.object(service, 'app_rows', return_value=[{'id': 'kate', 'package': 'kate'}]), \
                patch.object(service, 'command', side_effect=ValueError('sem rede')):
            with self.assertRaisesRegex(ValueError, 'sem rede'):
                self.setup.call('apps', {'items': ['kate']})
        self.assertEqual(service.State(self.directory).next, 4)
        self.assertEqual(self.state.data['requested_apps'], ['kate'])
        self.setup.call('apps', {'items': []})
        with patch.object(service.pwd, 'getpwnam', return_value=type('User', (), {'pw_uid': 1000})()), \
                patch.object(service, 'command', return_value=b'validacao P 11/17/2026'), \
                patch.object(service, 'remove_autologin'):
            self.setup.call('finish', {})
        self.assertTrue((self.directory/'complete').exists())
        self.assertFalse((self.directory/'pending').exists())

    def test_failed_wifi_profile_is_not_saved_and_retry_persists_only_success(self):
        class BusError(Exception):
            pass

        profile = Mock()
        wireless = Mock()
        wireless.GetAccessPoints.return_value = ['/access-point']
        bus = Mock()
        bus.get_object.side_effect = lambda _, path: wireless if path == '/device' else profile
        manager = Mock()
        manager.GetDevices.return_value = ['/device']
        manager.AddAndActivateConnection2.return_value = '/profile', '/active', {}
        dbus = SimpleNamespace(DBusException=BusError, Boolean=bool, Interface=lambda item, _:item)
        network = dict(name='Rede de ensaio', key='wpa-psk')
        with patch.object(service,'network_api',return_value=(dbus,bus,manager)), \
                patch.object(service,'get_properties',side_effect=[
                    {'DeviceType':2,'State':30},{},{'State':4},
                    {'DeviceType':2,'State':30},{},{'State':2}]), \
                patch.object(service,'access_point',return_value=network), \
                patch.object(service,'networks',return_value={'internet':True}):
            with self.assertRaisesRegex(ValueError,'senha, o alcance'):
                service.connect_wifi('/device','/access-point','senha descartável')
            profile.Delete.assert_called_once()
            profile.Save.assert_not_called()
            self.assertTrue(service.connect_wifi('/device','/access-point','senha de ensaio')['internet'])
        profile.Save.assert_called_once()
        profile.Delete.assert_called_once()
        self.assertTrue(all(call.args[3]=={'persist':'memory'}
                            for call in manager.AddAndActivateConnection2.call_args_list))
        self.assertFalse(self.state.path.exists())

    def test_interrupted_installation_resumes_only_remaining_packages(self):
        for key, value in (('keyboard', 'br'), ('network', True), ('timezone', 'America/Sao_Paulo'),
                           ('account', {'mode': 'local', 'login': 'validacao', 'uid': 1000})):
            self.state.save(key,value)
        choices = ['primeiro','segundo']
        rows = [{'id':item,'package':f'pkg-{item}'} for item in choices]
        with patch.object(service,'app_rows',return_value=rows):
            with patch.object(service,'command',side_effect=[b'',ValueError('sem rede')]):
                with self.assertRaisesRegex(ValueError,'sem rede'):
                    self.setup.call('apps',{'items':choices})
            resumed = service.Setup(service.State(self.directory))
            self.assertEqual(resumed.state.data['installed_apps'],['primeiro'])
            self.assertEqual(resumed.state.data['requested_apps'],choices)
            self.assertEqual(resumed.state.next,4)
            with patch.object(service,'command') as run:
                resumed.call('apps', {'items':choices})
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0][-1],'pkg-segundo')
        self.assertEqual(resumed.state.data['apps'],choices)

    def test_existing_installation_starts_sddm_without_session_template(self):
        config = self.directory/'pref.conf'
        config.write_text('[Theme]\nCurrent=personalizado\n')
        fields = dict(STATE_DIR=self.directory,SDDM_CONFIG=config,
                      SDDM_SESSION=self.directory/'session.desktop',
                      SESSION_TEMPLATE=self.directory/'missing.desktop')
        with patch.multiple(service,**fields), patch.object(service,'setup_user') as user, \
                patch.object(service,'notify_ready') as ready:
            service.main()
        ready.assert_called_once_with()
        user.assert_not_called()
        self.assertEqual(config.read_text(),'[Theme]\nCurrent=personalizado\n')
        self.assertFalse(self.state.path.exists())

    def test_finish_sends_result_before_socket_worker_exits(self):
        path = self.directory/'control.sock'
        with service.Server(str(path),service.Handler) as server:
            server.uid = os.getuid()
            server.setup = Mock()
            server.setup.call.return_value = {}
            server.operation_lock = threading.Lock()
            worker = threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            try:
                with patch.object(service,'STATE_DIR',self.directory), patch.object(gui,'SOCKET_PATH',str(path)):
                    self.assertEqual(gui.request('finish'),{})
                worker.join(2)
                self.assertFalse(worker.is_alive())
            finally:
                if worker.is_alive():
                    server.shutdown()
                    worker.join(2)

    def test_invalid_ldaps_certificate_never_writes_sssd_config(self):
        for key, value in (('keyboard', 'br'), ('network', True), ('timezone', 'America/Sao_Paulo')):
            self.state.save(key, value)
        config = self.directory/'sssd.conf'
        with patch.object(service, 'SSSD_CONFIG', config), \
                patch.object(service, 'verify_ldaps', side_effect=ValueError('certificado inválido')):
            with self.assertRaisesRegex(ValueError, 'certificado inválido'):
                self.setup.call('account', dict(mode='ldap', host='ldap.empresa.example',
                                               base='dc=empresa,dc=example', login='validacao',
                                               user_password='senha de ensaio'))
        self.assertFalse(config.exists())
        self.assertNotIn('ldap_draft', self.state.data)

    def test_failed_ldap_authentication_rolls_back_only_new_profile(self):
        for key, value in (('keyboard', 'br'), ('network', True), ('timezone', 'America/Sao_Paulo')):
            self.state.save(key, value)
        config = self.directory/'sssd.conf'
        with patch.object(service, 'SSSD_CONFIG', config), patch.object(service, 'verify_ldaps'), \
                patch.object(service, 'verified_domain_account', side_effect=ValueError('senha inválida')), \
                patch.object(service, 'command') as run:
            with self.assertRaisesRegex(ValueError, 'senha inválida'):
                self.setup.call('account', dict(mode='ldap', host='ldap.empresa.example',
                                               base='dc=empresa,dc=example', login='validacao',
                                               user_password='senha de ensaio'))
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['restart', 'stop'])
        self.assertFalse(config.exists())
        self.assertNotIn('ldap_draft', self.state.data)
        self.assertNotIn('senha de ensaio', self.state.path.read_text())
        self.assertEqual(self.state.next, 3)

    def test_cleanup_leaves_admin_owned_autologin_config(self):
        conf = self.directory/'sddm.conf'
        session = self.directory/'session.desktop'
        template = self.directory/'sddm.desktop'
        template.write_text('[Desktop Entry]\nName=setup\n')
        conf.write_text('[Theme]\nCurrent=custom\n')
        session.write_bytes(template.read_bytes())
        with patch.multiple(service, SDDM_CONFIG=conf, SDDM_SESSION=session, SESSION_TEMPLATE=template):
            service.remove_autologin()
        self.assertEqual(conf.read_text(), '[Theme]\nCurrent=custom\n')
        self.assertFalse(session.exists())

    def test_profile_contains_only_portable_settings_and_preserves_checkpoints(self):
        value = dict(schema=1, language='pt_BR', edition='desktop', keyboard='br',
                     timezone='America/Manaus', apps=[])
        with self.assertRaisesRegex(ValueError, 'predefinições'):
            self.setup.call('profile', {'value': dict(value, password='senha de ensaio')})
        response = self.setup.call('profile', {'value': value})
        self.assertEqual(response['state']['profile'], value)
        self.assertEqual(response['next'], 0)
        self.assertEqual(service.State(self.directory).data['profile'], value)
        self.state.save('keyboard', 'br')
        with self.assertRaisesRegex(ValueError, 'antes de confirmar'):
            self.setup.call('profile', {'value': value})

    def test_live_checks_only_include_supported_values(self):
        (self.directory/'live-checks.json').write_text(
            '{"schema":1,"keyboard":true,"touchpad":false,"audio":null,"video":"concluído","text":"omitido"}')
        self.assertEqual(self.setup.call('state', {})['live_checks'],
                         dict(keyboard=True, touchpad=False, audio=None))

    def test_catalog_retains_selection_after_wifi_reconnect(self):
        for key, value in (('keyboard','br'), ('network',True), ('timezone','America/Sao_Paulo'),
                           ('account',{'mode':'local','login':'validacao'})):
            self.state.save(key,value)
        online = True
        requests = []

        def mock_service(operation, **data):
            requests.append(operation)
            if operation == 'networks':
                return {'wifi':[], 'internet':online, 'status':'Rede de ensaio'}
            if operation == 'catalog':
                return {'apps':[dict(id='kate',name='Kate',category='Produtividade')] if online else []}
            return self.setup.call(operation,data)

        def idle():
            for _ in range(200):
                APP.processEvents()
                if wizard.job is None:
                    return
                time.sleep(0.006)
            self.fail('O assistente não respondeu.')

        wizard = gui.Wizard(mock_service)
        wizard.setGeometry(APP.primaryScreen().geometry())
        wizard.showFullScreen()
        idle()
        self.assertEqual(wizard.step,4)
        wizard.checked[0][0].setChecked(True)
        online = False
        wizard.reload_catalog()
        idle()
        self.assertIn('indisponível',wizard.apps_status.text())
        output = os.environ.get('LINUXBR_SETUP_EVIDENCE')
        if output:
            QTest.qWait(100)
            self.assertTrue(wizard.grab().save(str(Path(output)/'13-catalogo-sem-rede.png')))
        wizard.review_network()
        idle()
        self.assertEqual(wizard.step,1)
        online = True
        wizard.advance()
        idle()
        self.assertEqual(wizard.step,4)
        self.assertTrue(wizard.checked[0][0].isChecked())
        self.assertEqual(requests,['state','catalog','catalog','networks','network','catalog'])
        wizard.hide()

    def test_offline_wizard_includes_summary_and_ignores_close(self):
        operations = []

        def mock_service(operation, **data):
            operations.append(operation)
            if operation == 'networks':
                return {'wifi': [], 'internet': False, 'status': 'Nenhuma conexão ativa.'}
            if operation == 'timezones':
                return {'zones': ['America/Sao_Paulo', 'America/Manaus'], 'suggested': None}
            if operation == 'catalog':
                return {'apps': []}
            if operation == 'keyboard':
                self.state.save('keyboard', data['layout'])
            if operation == 'network':
                self.state.save('network', True)
            if operation == 'timezone':
                self.state.save('timezone', data['zone'])
            if operation == 'account':
                self.state.save('account', {'mode': 'local', 'login': data['username']})
            if operation == 'apps':
                self.state.save('apps', data['items'])
            return self.state.public()

        def idle():
            for _ in range(200):
                APP.processEvents()
                if wizard.job is None:
                    return
                time.sleep(0.006)
            self.fail('O assistente não respondeu.')

        output = os.environ.get('LINUXBR_SETUP_EVIDENCE')
        with patch.object(gui.subprocess, 'run'):
            wizard = gui.Wizard(mock_service)
            wizard.setGeometry(APP.primaryScreen().geometry())
            wizard.showFullScreen()
            idle()
            self.assertTrue(wizard.isFullScreen())
            self.assertFalse(wizard.close())
            if output:
                self.assertTrue(wizard.grab().save(str(Path(output)/'06-teclado.png')))
            original_speech = wizard.speech
            with patch.object(wizard, 'speech') as speech:
                wizard.reader.setChecked(True)
                speech.start.assert_called_once_with('/usr/bin/orca', ['--replace'])
                wizard.reader.setChecked(False)
            self.assertIs(wizard.speech, original_speech)
            wizard.virtual_keyboard.setChecked(True)
            wizard.keyboard_test.setFocus()
            wizard.screen_keyboard.type_key('ç')
            self.assertEqual(wizard.keyboard_test.text(), 'ç')
            if output:
                QTest.qWait(120)
                self.assertTrue(wizard.grab().save(str(Path(output)/'08-teclado-na-tela.png')))
            wizard.virtual_keyboard.setChecked(False)
            wizard.advance()
            idle()
            self.assertIn('Nenhuma conexão', wizard.network_status.text())
            wizard.advance()
            idle()
            wizard.timezone.setCurrentIndex(wizard.timezone.findText('America/Manaus'))
            wizard.advance()
            idle()
            wizard.username.setText('validacao')
            wizard.display_name.setText('Pessoa de Validação')
            wizard.virtual_keyboard.setChecked(True)
            wizard.local_password.setFocus()
            for key in 'senha de ensaio':
                wizard.screen_keyboard.type_key(key)
            self.assertEqual(wizard.local_password.text(), 'senha de ensaio')
            self.assertNotEqual(wizard.local_password.displayText(), 'senha de ensaio')
            wizard.virtual_keyboard.setChecked(False)
            wizard.local_confirmation.setText('senha de ensaio')
            wizard.advance()
            idle()
            wizard.advance()
            idle()
            self.assertEqual(wizard.step, 5)
            self.assertIn('America/Manaus', wizard.summary.text())
            self.assertIn('validacao', wizard.summary.text())
            self.assertNotIn('senha', wizard.summary.text())
            if output:
                QTest.qWait(150)
                self.assertTrue(wizard.grab().save(str(Path(output)/'07-resumo-offline.png')))
                profile = str(Path(output) / 'profile-validation.json')
                with patch.object(gui.QFileDialog, 'getSaveFileName', return_value=(profile, '.json')):
                    wizard.save_profile()
                saved = Path(profile).read_text()
                self.assertIn('America/Manaus', saved)
                self.assertNotIn('validacao', saved)
                self.assertNotIn('senha', saved)
                Path(profile).unlink()
            wizard.advance()
            idle()
            wizard.hide()
        self.assertEqual(operations, ['state', 'keyboard', 'networks', 'network', 'timezones',
                                      'timezone', 'account', 'catalog', 'apps', 'finish'])


if __name__ == '__main__':
    unittest.main()
