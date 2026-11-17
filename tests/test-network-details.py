import sys
import unittest
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import network_details as backend


class DetailsTests(unittest.TestCase):
    def test_multiple_devices_and_ipv6(self):
        rows = backend.parse_devices('GENERAL.DEVICE:enp1s0\nGENERAL.TYPE:ethernet\nGENERAL.STATE:100 (connected)\nGENERAL.HWADDR:AA:BB:CC:DD:EE:FF\nIP6.ADDRESS[1]:2001:db8::1/64\nIP6.ADDRESS[2]:fe80::1/64\nIP4.DNS[1]:1.1.1.1\nGENERAL.DEVICE:wlan0\nGENERAL.STATE:30 (disconnected)\nGENERAL.CONNECTION:--\n')
        self.assertEqual(len(rows), 2)
        details = dict(backend.fields(rows[0]))
        self.assertEqual(details['Endereço físico (MAC)'], 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(details['Endereços IPv6'], '2001:db8::1/64\nfe80::1/64')
        self.assertEqual(details['Estado'], 'Conectado')
        self.assertEqual(dict(backend.fields(rows[1]))['Estado'], 'Desconectado')
        self.assertEqual(dict(backend.fields(rows[1]))['Conexão'], 'Não disponível')

    def test_names_and_unknown_data(self):
        rows = backend.parse_devices('GENERAL.DEVICE:tun0\nGENERAL.CONNECTION:VPN: escritório\\teste\nGENERAL.TYPE:tun\n')
        self.assertEqual(rows[0]['GENERAL.CONNECTION'], 'VPN: escritório\\teste')
        self.assertEqual(dict(backend.fields(rows[0]))['Estado'], 'Não disponível')
        self.assertEqual(backend.parse_devices(''), [])

    def test_dhcp_and_dns(self):
        data = {'DHCP4.OPTION[1]': 'dhcp_server_identifier = 192.168.1.1',
                'IP4.DNS[1]': '1.1.1.1', 'IP4.DNS[2]': '8.8.8.8'}
        fields = dict(backend.fields(data))
        self.assertEqual(fields['Servidor DHCP IPv4'], '192.168.1.1')
        self.assertEqual(fields['Servidores DNS IPv4'], '1.1.1.1\n8.8.8.8')

    def test_wifi_escaped_name_routes_and_mask(self):
        wifi=backend.wifi_details('*:Escritório\\: principal:5180 MHz:72:WPA2:AA\\:BB\\:CC\\:DD\\:EE\\:FF\n')
        self.assertEqual(wifi['WIFI.SSID'],'Escritório: principal')
        self.assertEqual(wifi['WIFI.BSSID'],'AA:BB:CC:DD:EE:FF')
        fields=dict(backend.fields(dict(wifi,**{'GENERAL.TYPE':'wifi','IP4.ADDRESS[1]':'192.0.2.4/24','IP4.ROUTE[1]':'dst = 0.0.0.0/0, nh = 192.0.2.1, mt = 100'})))
        self.assertEqual(fields['Máscaras IPv4'],'255.255.255.0')
        self.assertIn('Rota padrão → 192.0.2.1',fields['Rotas IPv4'])
        with self.assertRaises(ValueError):backend.reconnect_command({'GENERAL.DEVICE':'--bad'})

    def test_dns_failure_and_gateway_timeout_are_independent(self):
        adapter = {'GENERAL.DEVICE': 'wlan0', 'GENERAL.STATE': '100 (connected)',
                   'IP4.ADDRESS[1]': '192.0.2.20/24', 'IP4.GATEWAY': '192.0.2.1'}
        reply = [TimeoutExpired('ping', 4), CompletedProcess([], 0, 'limited\n'), CompletedProcess([], 2)]
        with (patch.object(backend, 'inventory', return_value=[adapter]),
              patch.object(backend.shutil, 'which', return_value='/usr/bin/ping'),
              patch.object(backend.subprocess, 'run', side_effect=reply) as run):
            rows, connectivity = backend.connectivity_check('wlan0')
        self.assertEqual(connectivity, 'limited')
        self.assertIn('pode bloquear', dict(rows)['Gateway IPv4'])
        self.assertIn('não encontrou', dict(rows)['DNS'])
        self.assertIn('wlan0', run.call_args_list[0].args[0])

    def test_captive_portal_skips_external_dns_check(self):
        adapter = {'GENERAL.DEVICE': 'wlan0', 'GENERAL.STATE': '100', 'IP4.ADDRESS[1]': '192.0.2.20/24'}
        with (patch.object(backend, 'inventory', return_value=[adapter]),
              patch.object(backend.subprocess, 'run', return_value=CompletedProcess([], 0, 'portal\n')) as run):
            rows, connectivity = backend.connectivity_check('wlan0')
        self.assertEqual(connectivity, 'portal')
        self.assertNotIn('DNS', dict(rows))
        run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
