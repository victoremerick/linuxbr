import sys
import unittest
from pathlib import Path

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


if __name__ == '__main__':
    unittest.main()
