from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
sys.path.insert(0, str(ROOT / 'packages/linuxbr-boot-tools/files/usr/lib/linuxbr-boot'))
from remote_console_launcher import server_url
from document_handoff import manifest, resolve_document
import file_offer
from network_backup import command, password_input, repository, restore_args
from scan_share import scanner_list
from send_content import available_devices, valid_link
from shared_links import encode_link, load_link
from support_share import history_path, recent_shares, record_share
from virtualization_backend import Manager
import webapps_backend as webapps
import firewall_trial
from ipaddress import IPv4Interface
from lan_services import render as render_lan
from virtualization_replica_job import schedule as schedule_replica
from wireless_display import client_arguments


class IntegrationTests(unittest.TestCase):
    def test_server_urls_do_not_accept_credentials_or_non_https(self):
        self.assertEqual(server_url('servidor.local'), 'https://servidor.local:9090/')
        self.assertEqual(server_url('[fd00::2]:9443'), 'https://[fd00::2]:9443/')
        for value in ('http://host', 'https://user@host', 'host:0', 'host:99999', 'host/path'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                server_url(value)

    def test_device_listing_and_link_scheme(self):
        self.assertEqual(available_devices('abc_123 Computador da sala\n'), {'Computador da sala (abc_123)': 'abc_123'})
        self.assertTrue(valid_link('https://example.org/rota'))
        self.assertFalse(valid_link('file:///etc/passwd'))
        self.assertFalse(valid_link('https://user:secret@example.org'))

    def test_backup_rejects_destination_escapes_and_uses_a_new_restore_folder(self):
        remote = repository('fd00::2', 'backup', 2222, '/backup/versões antigas')
        self.assertEqual(remote, 'sftp://backup@[fd00::2]:2222//backup/vers%C3%B5es%20antigas')
        self.assertIn('/dev/stdin', command(remote, 'snapshots'))
        self.assertEqual(password_input('uma senha'), b'uma senha\n')
        for host in ('-option', 'host/path', 'user@host'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                repository(host, 'backup', 22, '/backup')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                restore_args('latest', '/home/../etc', folder)
            args, first = restore_args('latest', '/home/nota [1]?.txt', folder)
            _, second = restore_args('latest', '', folder)
            self.assertIn(r'/home/nota \[1]\?.txt', args)
            self.assertNotEqual(first, second)
            self.assertEqual(Path(first).stat().st_mode & 0o777, 0o700)

    def test_scan_selection_retains_backend_name(self):
        self.assertEqual(scanner_list('test:0\tScanner de teste\nlinha inválida\n'),
                         {'Scanner de teste (test:0)': 'test:0'})

    def test_shared_links_accept_only_bounded_http_web_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'link.linuxbr-link'
            address = 'https://example.org/relatorio?versao=2#sumario'
            path.write_bytes(encode_link(address))
            self.assertEqual(load_link(path), address)
            alias = Path(folder) / 'alias.linuxbr-link'
            alias.symlink_to(path)
            with self.assertRaises(OSError):
                load_link(alias)
            for value in ('file:///etc/passwd', 'https://user@example.org', 'https://example.org/' + 'a' * 9000):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    encode_link(value)
            path.write_text('{"schema":"linuxbr-link-1","url":"javascript:alert(1)"}')
            with self.assertRaises(ValueError):
                load_link(path)

    def test_document_handoff_uses_a_relative_path_in_a_distinct_sync_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'origem'
            destination = base / 'destino'
            source.mkdir()
            destination.mkdir()
            document = source / 'relatório.txt'
            document.write_text('documento')
            record = manifest(document, source)
            self.assertEqual(record['document'], document.name)
            with self.assertRaises(FileNotFoundError):
                resolve_document(record, destination)
            target = destination / document.name
            target.symlink_to(document)
            with self.assertRaises(ValueError):
                resolve_document(record, destination)
            target.unlink()
            target.write_text('documento')
            self.assertEqual(resolve_document(record, destination), target)
            with self.assertRaises(ValueError):
                resolve_document(dict(record, document='../origem/relatório.txt'), destination)

    def test_file_offer_only_sends_original_files_after_local_confirmation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_STATE_HOME=folder):
            path = Path(folder) / 'arquivo.txt'
            path.write_text('conteúdo')
            target = 'destination_id'
            with patch.object(file_offer, 'choose_device', return_value=(target, 'Destino')), \
                    patch.object(file_offer, 'exchange', return_value=True) as exchange, \
                    patch.object(file_offer.QMessageBox, 'information'):
                file_offer.offer([str(path)])
                request = exchange.call_args.args[0]
                self.assertEqual(set(request['files'][0]), {'name', 'size'})
                answer = Path(folder) / 'reply.linuxbr-transfer'
                file_offer.write(answer, dict(kind='linuxbr-file-accept-1', token=request['token'], device='outro'))
                with patch.object(file_offer, 'ask', side_effect=[False, True]), \
                        patch('send_content.send_command') as send:
                    file_offer.receive(answer)
                    send.assert_not_called()
                    file_offer.receive(answer)
                    send.assert_called_once_with('--device', target, '--share', path.as_uri())
                with self.assertRaises(FileNotFoundError):
                    file_offer.receive(answer)

    def test_diagnostic_share_records_categories_and_recipient(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_STATE_HOME=folder):
            self.assertEqual(recent_shares(), [])
            record_share('Computador do suporte', ['Hardware'])
            record_share('Notebook (outro-id)', ['Rede', 'Sistema'])
            self.assertEqual([row[1:] for row in recent_shares()], [
                ('Notebook (outro-id)', ['Rede', 'Sistema']), ('Computador do suporte', ['Hardware']),
            ])
            self.assertEqual(history_path().stat().st_mode & 0o777, 0o600)

    def test_firewall_trial_restores_and_only_persists_after_confirmation(self):
        states = {False: True, True: True}

        def update(zone, port, allowed, permanent=False):
            self.assertEqual((zone, port), ('public', '8443/tcp'))
            states[permanent] = allowed

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(firewall_trial, 'STATE', Path(folder) / 'run'), \
                patch.object(firewall_trial.os, 'geteuid', return_value=0), \
                patch.object(firewall_trial, 'query', side_effect=lambda _z, _p, saved=False: states[saved]), \
                patch.object(firewall_trial, 'update', side_effect=update), \
                patch.object(firewall_trial, 'run') as systemd:
            start = ['begin', 'public', '8443/tcp', 'remove']
            token = firewall_trial.apply(start)
            self.assertEqual(states, {False: False, True: True})
            self.assertIn('--on-active=120s', systemd.call_args.args)
            with self.assertRaises(ValueError):
                firewall_trial.apply(['commit', '0' * 32])
            firewall_trial.apply(['rollback', token])
            self.assertEqual(states, {False: True, True: True})
            token = firewall_trial.apply(start)
            with patch.object(firewall_trial, 'monotonic', return_value=10**15):
                with self.assertRaisesRegex(ValueError, 'prazo'):
                    firewall_trial.apply(['commit', token])
            firewall_trial.apply(['commit', token])
            firewall_trial.apply(['rollback', token])
            self.assertEqual(states, {False: False, True: False})

    def test_lan_rejects_dynamic_range_with_gateway_and_dhcp_reservations(self):
        config = dict(interface='enp1s0', subnet='192.168.50.0/24', domain='rede.home.arpa',
                      scope=['192.168.50.100', '192.168.50.200', '192.168.50.1'],
                      records=[dict(name='servidor', address='192.168.50.4', mac='52:54:00:10:20:30')])
        interface = [IPv4Interface('192.168.50.2/24')]
        text = render_lan(config, interface)
        self.assertIn('host-record=servidor.rede.home.arpa,192.168.50.4', text)
        self.assertIn('dhcp-host=52:54:00:10:20:30,192.168.50.4,servidor', text)
        for address in ('192.168.50.129', '192.168.50.1', '192.168.51.4'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                render_lan(dict(config, records=[dict(config['records'][0], address=address)]), interface)

    def test_monitor_tunnel_binds_loopback_and_rejects_ssh_options_in_the_host_field(self):
        argv = client_arguments('operador@servidor', 2222, '/tmp/linuxbr-screen-abc/vnc', 15591)
        self.assertIn('127.0.0.1:15591:/tmp/linuxbr-screen-abc/vnc', argv)
        self.assertIn('StrictHostKeyChecking=yes', argv)
        for host in ('-oProxyCommand=x', 'user@host -p 1'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                client_arguments(host, 22, '/tmp/linuxbr-screen-abc/vnc', 15591)

    def test_replication_schedule_runs_in_operators_account(self):
        origin = 'qemu:///system'
        dest = 'qemu+ssh://victor@destino/system'
        identifier = str(uuid.uuid4())
        with patch('virtualization_replica_job.os.geteuid', return_value=1000), \
                patch('virtualization_replica_job.create_task') as task:
            schedule_replica(origin, identifier, dest, 'dados', 'servidor', 'isolada', 'daily')
            scope, name, argv, schedule = task.call_args.args
            self.assertEqual((scope, name, schedule), ('user', 'Réplica de VM: servidor', 'daily'))
            self.assertEqual(argv[2:], [origin, identifier, dest, 'dados', 'servidor', 'isolada'])

    def test_reservation_rewrites_only_inactive_network_definition(self):
        connection = Mock()
        network = connection.networkLookupByUUIDString.return_value
        network.isActive.return_value = False
        network.XMLDesc.return_value = (
            '<network><name>rede</name><ip address="192.168.50.1" netmask="255.255.255.0">'
            '<dhcp><range start="192.168.50.2" end="192.168.50.254"/></dhcp></ip></network>'
        )
        manager = Manager(connection=connection)
        identifier = str(uuid.uuid4())
        manager.add_network_host(identifier, 'notebook', '192.168.50.22', '52:54:00:11:22:33')
        xml = ET.fromstring(connection.networkDefineXML.call_args.args[0])
        self.assertEqual(xml.findtext('dns/host/hostname'), 'notebook')
        self.assertEqual(xml.find('ip/dhcp/host').get('ip'), '192.168.50.22')
        self.assertIsNotNone(xml.find('ip/dhcp/range'))
        connection.networkDefineXML.reset_mock()
        network.isActive.return_value = True
        with self.assertRaisesRegex(ValueError, 'Desative'):
            manager.add_network_host(identifier, 'outro', '192.168.50.23')
        connection.networkDefineXML.assert_not_called()

    def test_replica_rejects_forwarded_network_before_export(self):
        origin = Mock()
        origin.getCapabilities.return_value = '<capabilities><host><uuid>origem</uuid></host></capabilities>'
        manager = Manager(connection=origin)
        with patch.object(manager, 'editable'), patch.object(manager, 'interfaces', return_value=[{}]), patch.object(manager, 'export_bundle') as export:
            with patch('virtualization_backend.Manager') as constructor:
                target = constructor.return_value
                target.connection.getCapabilities.return_value = '<capabilities><host><uuid>destino</uuid></host></capabilities>'
                network = target.connection.networkLookupByName.return_value
                network.XMLDesc.return_value = '<network><forward mode="nat"/></network>'
                network.isActive.return_value = True
                with self.assertRaisesRegex(ValueError, 'rede isolada'):
                    manager.replicate_offline(str(uuid.uuid4()), 'qemu+ssh://victor@destino/system', 'dados', 'replica', 'nat')
                target.close.assert_called_once()
            export.assert_not_called()

    def test_offline_move_copies_disks_before_retiring_source(self):
        origin = Mock()
        origin.getCapabilities.return_value = '<capabilities><host><uuid>origem</uuid></host></capabilities>'
        manager = Manager(connection=origin)
        identifier = str(uuid.uuid4())
        domain = Mock()
        domain.isPersistent.return_value = True
        domain.listAllSnapshots.return_value = []
        transferred = dict(id=identifier, name='Estação', disks=1, state='Desligada')
        sequence = Mock()
        with patch.object(manager, 'editable'), patch.object(manager, 'domain', return_value=domain), \
                patch.object(manager, 'interfaces', return_value=[{}]), \
                patch.object(manager, 'export_bundle'), patch.object(manager, 'undefine') as remove, \
                patch('virtualization_backend.Manager') as constructor:
            target = constructor.return_value
            target.connection.getCapabilities.return_value = '<capabilities><host><uuid>destino</uuid></host></capabilities>'
            network = target.connection.networkLookupByName.return_value
            network.isActive.return_value = True
            network.XMLDesc.return_value = '<network><forward mode="nat"/></network>'
            target.domains.return_value = []
            target.import_bundle.return_value = transferred
            sequence.attach_mock(target.import_bundle, 'copy')
            sequence.attach_mock(remove, 'remove')
            uri = 'qemu+ssh://victor@destino/system'
            result = manager.move_offline(identifier, uri, 'dados', 'Estação', 'default')
            self.assertTrue(result['source_removed'])
            self.assertEqual([call[0] for call in sequence.mock_calls], ['copy', 'remove'])
            self.assertEqual(target.import_bundle.call_args.args[1:], ('dados', 'Estação', False, 'default'))
            self.assertFalse(Path(target.import_bundle.call_args.args[0]).exists())

            remove.reset_mock()
            target.import_bundle.side_effect = OSError('conexão caiu durante a cópia')
            with self.assertRaises(OSError):
                manager.move_offline(identifier, uri, 'dados', 'Estação', 'default')
            remove.assert_not_called()

            target.import_bundle.side_effect = None
            remove.side_effect = OSError('conexão com a origem caiu')
            result = manager.move_offline(identifier, uri, 'dados', 'Estação', 'default')
            self.assertFalse(result['source_removed'])
            self.assertEqual(result['id'], identifier)

            remove.reset_mock()
            target.import_bundle.reset_mock()
            target.domains.return_value = [{'id': identifier, 'name': 'Outro nome'}]
            with self.assertRaisesRegex(ValueError, 'já tem uma VM'):
                manager.move_offline(identifier, uri, 'dados', 'Estação', 'default')
            target.import_bundle.assert_not_called()
            remove.assert_not_called()

    def test_webapp_shortcuts_discard_private_paths_and_profile_names(self):
        items = [{'url': 'https://example.org/documento/privado', 'name': 'Editor', 'session': 'Pessoal'},
                 {'url': 'https://example.org/documento/trabalho', 'name': 'Editor', 'session': 'Trabalho'}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'webapps.json'
            with patch.object(webapps, 'installed', return_value=items), patch.object(webapps, 'service_for', return_value=None):
                webapps.export_shortcuts(path)
                self.assertEqual(json.loads(path.read_text())['shortcuts'], [{'url': 'https://example.org/', 'name': 'Editor'}])
                self.assertEqual(webapps.load_shortcuts(path)[0]['url'], 'https://example.org/')


if __name__ == '__main__':
    unittest.main()
