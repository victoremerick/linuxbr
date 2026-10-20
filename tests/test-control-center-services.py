#!/usr/bin/python3
"""Input and safety checks for privileged Central operations, without changing host state."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'packages/linuxbr-system/files/usr/lib/linuxbr-system'
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

firewall=load('firewall_backend');network=load('network_ip');groups=load('groups_backend')

class Services(unittest.TestCase):
    def test_port_validation_and_fixed_command(self):
        for value in ('0/tcp','65536/udp','22/tcp;touch /tmp/x','22/icmp','-1/tcp'):
            with self.assertRaises(ValueError):firewall.validate(value)
        self.assertEqual(firewall.validate('443/tcp'),'443/tcp')
        with patch.object(firewall,'command',side_effect=['public','public','','']) as command:
            firewall.apply('allow','443/tcp')
        self.assertEqual(command.call_args_list[2].args,
            ('firewall-cmd','--permanent','--zone=public','--add-port=443/tcp'))

    def test_ipv4_ipv6_and_dns_validation(self):
        self.assertEqual(network.validated(4,'manual','192.168.1.3/24','192.168.1.1','1.1.1.1, 8.8.8.8')['dns'],'1.1.1.1,8.8.8.8')
        self.assertEqual(network.validated(6,'auto','','','2001:4860:4860::8888')['ignore-auto-dns'],'yes')
        for method,address,gateway,dns in [('manual','not-an-ip','',''),('manual','192.168.1.3/24','2001:db8::1',''),('auto','192.168.1.2/24','',''),('auto','','','8.8.8.8;touch /tmp/x')]:
            with self.assertRaises(ValueError):network.validated(4,method,address,gateway,dns)

    def test_keep_local_admin_and_primary_group(self):
        admin=['sudo','x','27','alice'];staff=['staff','x','1001','alice']
        with patch.object(groups,'local_groups',return_value={'sudo':admin,'staff':staff}), patch.object(groups,'local_users',return_value={'alice':['alice','x','1001','1001']}),patch.object(groups.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'administrador'):groups.execute('remove','sudo','alice')
            with self.assertRaisesRegex(ValueError,'principal'):groups.execute('delete','staff')
            with self.assertRaises(ValueError):groups.execute('add','staff','alice;rm')
            self.assertFalse(run.called)

if __name__=='__main__':unittest.main()
