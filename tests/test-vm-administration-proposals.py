#!/usr/bin/env python3
"""Exercise template ingestion and the read-only migration preflight."""

import json
from contextlib import nullcontext
from datetime import date, timedelta
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Fake
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[1] / 'packages'
sys.path[:0] = [str(SOURCE / 'linuxbr-system/files/usr/lib/linuxbr-system'),
                str(SOURCE / 'linuxbr-boot-tools/files/usr/lib/linuxbr-boot')]

import virtualization_backend as backend
import virtualization_catalog as catalog
import virtualization_guest_access as access
import virtualization_migration_check as migration
import virtual_media_delegate as media


class AdminTemplates(unittest.TestCase):
    def test_revision_stays_in_domain_metadata(self):
        profile = catalog.check(catalog.BUILTIN[0])
        spec = {**profile, 'name': 'Lab', 'pool': 'default', 'volume': 'lab.qcow2',
                'managed_template': (profile['id'], profile['revision'])}
        xml = ET.fromstring(backend.domain_xml(spec, {'kind': 'kvm', 'machine': 'q35'}))
        self.assertEqual(xml.find('metadata/' + backend.TEMPLATE_DEFAULTS).attrib,
                         {'id': profile['id'], 'revision': profile['revision']})
        self.assertEqual(xml.findtext('memory'), '4096')
        with self.assertRaisesRegex(ValueError, 'Recurso fora'):
            catalog.check({**profile, 'memory': True})

    @unittest.skipUnless(os.geteuid() == 0, 'o catálogo de teste requer propriedade administrativa')
    def test_non_admin_template_rejected_and_managed_revision_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            profile = {**catalog.BUILTIN[0], 'revision': '2.0', 'network': 'lab'}
            candidate = target / (profile['id'] + '.json')
            candidate.write_text(json.dumps(profile))
            insecure = target / 'insecure.json'
            insecure.symlink_to(candidate)
            rows, errors = catalog.catalog(False, target)
            self.assertEqual(rows, [profile])
            self.assertIn('proteção administrativa', errors[0])


CAPS = """<domainCapabilities>
    <machine>pc-q35-9.2</machine><arch>x86_64</arch>
    <vcpu max='32'/><os><enum name='firmware'><value>efi</value></enum></os>
    <cpu><mode name='host-model' supported='yes'><model>EPYC</model>
        <feature policy='require' name='xsave'/></mode></cpu>
</domainCapabilities>"""
VM = """<domain type='kvm'><os firmware='efi'><type arch='x86_64' machine='pc-q35-9.2'>hvm</type></os>
    <cpu mode='host-model'/><vcpu>4</vcpu><memory unit='MiB'>2048</memory>
    <devices><interface type='network'><source network='lab'/></interface>
    <disk type='file' device='disk'><target dev='sda'/></disk></devices></domain>"""


def host(name):
    return f'<capabilities><host><uuid>{name}</uuid></host></capabilities>'


def fixtures():
    source = Fake(connection=Fake(getCapabilities=lambda: host('source'),
                  getDomainCapabilities=lambda *_: CAPS))
    guest = Fake(name=lambda: 'VM QA', UUIDString=lambda: 'vm-id', hasManagedSaveImage=lambda _: False,
                 isActive=lambda: True, XMLDesc=lambda _: VM, listAllSnapshots=lambda _: [],
                 blockInfo=lambda *_: [100, 20, 20])
    network = Fake(name=lambda: 'lab', isActive=lambda: True)
    target = Fake(getCapabilities=lambda: host('destination'), listAllDomains=lambda _: [],
                  getDomainCapabilities=lambda *_: CAPS, compareHypervisorCPU=lambda *_: 2,
                  listAllNetworks=lambda _: [network], getInfo=lambda: ['x86_64', 32768],
                  getFreeMemory=lambda: 8192 * 1024 ** 2)
    return source, guest, target


class Migration(unittest.TestCase):
    def test_passes_on_matching_cpu_firmware_and_network(self):
        source, guest, target = fixtures()
        report = migration.evaluate(source, guest, 'qemu+ssh://qa@host/system', target, 'shared')
        states = {item['area']: item['status'] for item in report}
        self.assertEqual(states['CPU'], 'ok')
        self.assertEqual(states['UEFI'], 'ok')
        self.assertEqual(states['Rede da VM'], 'ok')
        self.assertEqual(states['Recursos'], 'ok')
        self.assertEqual(states['Armazenamento'], 'review')
        self.assertIn('xsave', migration.cpu_profile(ET.fromstring(VM), ET.fromstring(CAPS)))

    def test_blocks_duplicate_hardware_identity_and_network_conflict(self):
        source, guest, target = fixtures()
        target.getCapabilities = lambda: host('source')
        target.listAllDomains = lambda _: [guest]
        target.listAllNetworks = lambda _: []
        target.compareHypervisorCPU = lambda *_: 0
        target.getInfo = lambda: ['x86_64', 1024]
        report = migration.evaluate(source, guest, 'qemu+ssh://qa@host/system', target, 'shared')
        for area in ('Conectividade', 'CPU', 'Identidade da VM', 'Recursos', 'Rede da VM'):
            self.assertEqual(next(item['status'] for item in report if item['area'] == area), 'blocked')


class TemporaryGuest(unittest.TestCase):
    def test_expired_account_created_then_activated_with_one_secret(self):
        trace = []
        known = ('guest-get-osinfo', 'guest-exec', 'guest-exec-status', 'guest-set-user-password')
        domain = Fake(isActive=lambda: True, setUserPassword=lambda *params: trace.append(('password', params)))
        manager = Fake(domain=lambda _: domain)
        valid_until = (date.today() + timedelta(days=5)).isoformat()

        def qga(domain, action, arguments=None):
            if action == 'guest-info':
                return {'supported_commands': [{'name': name, 'enabled': True} for name in known]}
            if action == 'guest-get-osinfo':
                return {'kernel-release': '6.12.0', 'id': 'debian'}
            if action == 'guest-exec':
                trace.append((arguments['path'], arguments['arg']))
                return {'pid': 10}
            return {'exited': True, 'exitcode': 0}

        result = access.create(manager, 'lab', valid_until, qga)
        self.assertTrue(result['username'].startswith('laboratorio-'))
        self.assertIn('1970-01-02', trace[0][1])
        self.assertEqual(trace[1][1], (result['username'], result['password'], 0))
        self.assertIn(valid_until, trace[2][1])
        self.assertNotIn(result['password'], str(trace[0] + trace[2]))
        with self.assertRaisesRegex(ValueError, 'a partir|amanhã'):
            access.expiration(date.today().isoformat())

    def test_revoke_created_account_if_password_install_fails(self):
        known = ('guest-get-osinfo', 'guest-exec', 'guest-exec-status', 'guest-set-user-password')
        qga = lambda _, action: ({'supported_commands': [{'name': name, 'enabled': True} for name in known]}
                                 if action == 'guest-info' else {'kernel-release': '6.12.0'})
        with patch.object(access, 'guest_exec', return_value=True) as invoke:
            def unsupported(*_):
                raise RuntimeError('private backend data')
            manager = Fake(domain=lambda _: Fake(isActive=lambda: True, setUserPassword=unsupported))
            with self.assertRaisesRegex(RuntimeError, 'não confirmou'):
                access.create(manager, 'lab', (date.today() + timedelta(days=3)).isoformat(), qga)
            self.assertEqual([call.args[2] for call in invoke.call_args_list], ['create', 'remove'])


class DelegatedMedia(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0, 'a mídia sintética usa a propriedade administrativa')
    def test_one_operator_one_iso_one_vm_one_use(self):
        identifier = 'ba518afa-e628-4ee7-8a08-9a4595a97cae'
        device_xml = ("<domain><devices><disk type='file' device='cdrom'><driver name='qemu' type='raw'/>"
                      "<target dev='sdb' bus='sata'/><readonly/></disk></devices></domain>")
        changes = []
        domain = Fake(name=lambda: 'Lab', isPersistent=lambda: True, isActive=lambda: False,
                      hasManagedSaveImage=lambda _: False, XMLDesc=lambda _: device_xml,
                      updateDeviceFlags=lambda xml, flags: changes.append((ET.fromstring(xml), flags)))

        def only_domain(vm):
            self.assertEqual(vm, identifier)
            return domain

        connection = Fake(lookupByUUIDString=only_domain)
        with tempfile.TemporaryDirectory(dir='/root') as directory:
            root = Path(directory)
            images = root / 'media'
            images.mkdir(0o755)
            grants = root / 'grants'
            iso = images / 'approved.iso'
            iso.write_bytes(b'\0' * 32769 + b'CD001')
            digest = hashlib.sha256(iso.read_bytes()).hexdigest()
            with (patch.object(media, 'MEDIA', images), patch.object(media, 'GRANTS', grants),
                  patch.object(media, 'connect', return_value=nullcontext(connection)),
                  patch.object(media.pwd, 'getpwnam', return_value=Fake(pw_uid=1000, pw_name='tester')),
                  patch.object(media.pwd, 'getpwuid', return_value=Fake(pw_name='tester')),
                  patch.object(media.time, 'time', return_value=1_000_000),
                  patch.object(media, 'audit')):
                code = media.issue('tester', identifier, iso.name, digest, 1)['code']
                self.assertEqual(len(code), 32)
                self.assertNotIn(code, media.path_for(code).read_text())
                with self.assertRaisesRegex(ValueError, 'atribuído'):
                    media.redeem(code, 1002)
                with patch.object(media.time, 'time', return_value=1_003_600):
                    with self.assertRaisesRegex(ValueError, 'expirado'):
                        media.redeem(code, 1000)
                iso.write_bytes(iso.read_bytes() + b'altered')
                with self.assertRaisesRegex(ValueError, 'mudou'):
                    media.redeem(code, 1000)
                iso.write_bytes(b'\0' * 32769 + b'CD001')
                media.redeem(code, 1000)
                with self.assertRaisesRegex(ValueError, 'usado'):
                    media.redeem(code, 1000)
            self.assertEqual(len(changes), 1)
            disk, flags = changes[0]
            self.assertEqual(flags, 2)
            self.assertEqual(disk.find('source').get('file'), str(iso))
            self.assertEqual(disk.find('target').get('dev'), 'sdb')


if __name__ == '__main__':
    unittest.main(verbosity=2)
