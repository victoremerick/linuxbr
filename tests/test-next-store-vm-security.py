#!/usr/bin/python3
import json
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'
sys.path.insert(0, str(SYSTEM))

import recovery_keys
import store_discovery
import store_holds
import store_impact
import store_optional
import store_products
import store_transactions
import virtualization_disks as disks
import virtualization_observability as observations


class Store(TestCase):
    def test_group_uses_exact_index_identities(self):
        catalog = ROOT / 'packages/linuxbr-system/files/usr/share/linuxbr/store'
        entries = json.loads((catalog / 'catalog.json').read_text(encoding='utf-8'))['apps']
        with patch.object(store_discovery, 'CATALOG', catalog / 'discovery.json.gz'):
            store_discovery.index.cache_clear()
            store_products.discovered.cache_clear()
            try:
                rows = dict(store_products.variants('libreoffice', entries))
                self.assertEqual(rows['DEB']['discovery_id'], 'libreoffice')
                self.assertEqual(rows['Flatpak']['discovery_id'], 'org.libreoffice.LibreOffice')
                self.assertIsNone(store_products.key(dict(id='app-semelhante', name='LibreOffice')))
                self.assertIn('ODF', store_products.comparison({'id': 'libreoffice', 'kind': 'linux'}, {})[-1])
            finally:
                store_products.discovered.cache_clear()
                store_discovery.index.cache_clear()

    def test_apt_preview_counts_exact_versions(self):
        command_result = ['Inst vlc [1.0] (2.0 Debian:stable [amd64])\n',
                          'Package: vlc\nVersion: 2.0\nArchitecture: amd64\nSize: 1048576\nInstalled-Size: 2048\n']
        with patch.object(store_impact, 'read', side_effect=command_result) as read:
            output = store_impact.deb_preview('vlc', 'install')
        self.assertIn('vlc · 2.0', output)
        self.assertEqual(read.call_args_list[1].args[0][-1], 'vlc=2.0')
        self.assertNotIn('parcial', output)

    def test_pause_persists_and_expires(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_CONFIG_HOME=directory):
            request = dict(manager='deb', scope='system', target='vlc', origin='debian')
            store_holds.change(request, 1, 'Revisão da equipe')
            target = dict(request, target='vlc:amd64', origin='Outro rótulo')
            self.assertEqual(store_holds.active(target)[1], 'Revisão da equipe')
            self.assertIsNone(store_holds.active(target, datetime.now(timezone.utc) + timedelta(days=2)))
            store_holds.change(target, 0)
            self.assertIsNone(store_holds.active(request))

    def test_flatpak_data_cleanup_leaves_active_or_other_installs(self):
        installation = dict(action='remove', manager='flatpak', scope='user', origin='flathub',
                            target='org.test.App', name='Aplicativo', trash_data=['cache'])
        request = store_transactions.checked_request(installation)
        with patch.object(store_impact, 'read', return_value='org.test.App\n') as read:
            with self.assertRaisesRegex(ValueError, 'Outra instalação'):
                store_impact.trash_removed_data(request)
            self.assertEqual(read.call_count, 1)
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)):
            config = Path(directory) / '.var/app/org.test.App/config'
            config.mkdir(parents=True)
            (config.parent / 'cache').symlink_to(config)
            self.assertEqual(store_impact.data_directories('org.test.App'), {'config': config})

    def test_homebrew_retirement_is_visible_but_cannot_install(self):
        row = dict(name='reg', tap='homebrew/core', disabled=True, disable_date='2027-08-23',
                   disable_replacement_formula='skopeo')
        result = store_optional.entry('brew', row)
        self.assertIn('skopeo', result['lifecycle'])
        self.assertNotIn('optional_target', result)
        self.assertTrue(store_optional.entry('brew', row, installed=True)['optional_target']['installed'])


class Virtualization(TestCase):
    def test_rates_ignore_counter_reset_and_display_missing_data(self):
        old = dict(timestamp=15, active=True, cpus=2, cpu=100, disk=(0, 3, 0, 2052, 0),
                   net=(2048, 0, 0, 0, 4000, 0, 0, 0))
        now = dict(old, timestamp=17, cpu=2_000_000_100, disk=(0, 2051, 0, 1027, 0),
                   net=(4096, 0, 0, 0, 4970, 0, 0, 0))
        self.assertEqual(observations.rates(old, now),
                         dict(cpu=50, read=1024, write=None, rx=1024, tx=485))

    def test_topology_resolves_vlans_bridge_and_uplink(self):
        machine = '<domain><devices><interface type="network"><source network="lan" portgroup="p"/>' \
                  '<target dev="vnet2"/></interface></devices></domain>'
        network = '<network><forward mode="bridge"/><bridge name="br0"/>' \
                  '<portgroup name="p"><vlan><tag id="42"/></vlan></portgroup></network>'
        member = '<interface><bridge><interface type="ethernet" name="eno1"/></bridge></interface>'
        connection = SimpleNamespace(
            listAllDomains=lambda _: [SimpleNamespace(name=lambda: 'Convidado', XMLDesc=lambda _: machine)],
            interfaceLookupByName=lambda _: SimpleNamespace(XMLDesc=lambda _: member))
        manager = SimpleNamespace(connection=connection, networks=lambda: [dict(name='lan', xml=network)])
        self.assertEqual(observations.topology(manager), [
            dict(vm='Convidado', interface='vnet2', kind='bridge', network='lan', bridge='br0',
                 vlan='42', upstream='eno1')])

    def test_converts_hyperv_and_preserves_checkpoint_chain(self):
        if not shutil.which('qemu-img'):
            self.skipTest('qemu-img indisponível neste ambiente')
        with tempfile.TemporaryDirectory() as folder:
            location = Path(folder)
            for suffix, format_name in (('vhd', 'vpc'), ('vhdx', 'vhdx')):
                source = location / ('origem.' + suffix)
                disks.qemu_img('create', '-f', format_name, str(source), '64M')
                spec = disks.hyperv_preview(source)
                self.assertEqual(spec['format'], format_name)
                output = location / (suffix + '.qcow2')
                disks.convert(source, output, spec['capacity'], spec['format'])
                self.assertEqual(len(disks.chain(output)), 1)
                self.assertTrue(source.exists())
            base, child = location / 'base.qcow2', location / 'checkpoint.qcow2'
            disks.qemu_img('create', '-f', 'qcow2', str(base), '64M')
            disks.qemu_img('create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(child))
            before = disks.chain(child)
            independent = location / 'recuperado.qcow2'
            disks.convert(child, independent, before[0]['capacity'], 'qcow2')
            self.assertEqual(len(disks.chain(independent)), 1)
            self.assertEqual(disks.chain(child), before)
            with self.assertRaises(ValueError):
                disks.convert(child, independent, before[0]['capacity'], 'qcow2')


class RecoveryKey(TestCase):
    def test_openpgp_roundtrip_uses_encryption_and_private_file(self):
        if not shutil.which('gpg'):
            self.skipTest('GnuPG indisponível')
        identifier = 'e9a296c4-b20c-4889-827c-f8762e3392be'
        phrase = 'frase descartável de laboratório'
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, GNUPGHOME=directory):
            location = Path(directory)
            output = location / 'recovery.gpg'
            recovery_keys.export(identifier, phrase, 'exportação de teste', output)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(phrase.encode(), output.read_bytes())
            result = subprocess.check_output(['/usr/bin/gpg', '--batch', '--pinentry-mode', 'loopback',
                                              '--passphrase-fd', '0', '--decrypt', str(output)],
                                             input='exportação de teste\n'.encode(), stderr=subprocess.DEVNULL)
            self.assertEqual(json.loads(result)['recovery_passphrase'], phrase)


if __name__ == '__main__':
    main()
