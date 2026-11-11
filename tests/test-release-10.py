"""Release evidence must match the exact version and artifacts being published."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from release_info import release_info
from release_gate import REQUIRED, VERSION_11_CHECKS, verify, publication_acceptance


class ReleaseAcceptance(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest = self.root/'release.json'
        self.version = '1.0.0~rc1'
        self.artifacts = {}
        for name in ('iso', 'source', 'packages'):
            data = ('fixture-'+name).encode()
            (self.root/name).write_bytes(data)
            self.artifacts[name] = dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        evidence = b'fixture-only: no actual release validation'
        (self.root/'evidence.txt').write_bytes(evidence)
        self.value = dict(schema=1, version=self.version, artifacts=self.artifacts,
            checks=[dict(id=name, status='PASS', version=self.version, artifact='iso',
                artifact_sha256=self.artifacts['iso']['sha256'], evidence='evidence.txt',
                evidence_sha256=hashlib.sha256(evidence).hexdigest()) for name in sorted(REQUIRED)],
            support=dict(maintainer='fixture', maintenance_policy='fixture', supported_hardware=['fixture']))

    def run_manifest(self, value=None):
        self.manifest.write_text(json.dumps(self.value if value is None else value))
        return verify(self.manifest, self.version)

    def test_complete_fixture_checks_all_artifacts(self):
        self.assertEqual(self.run_manifest()['scenarios'], len(REQUIRED))

    def test_11_requires_screen_sharing_evidence_from_the_iso(self):
        self.version = self.value['version'] = '1.1.0'
        for row in self.value['checks']:
            row['version'] = self.version
        with self.assertRaisesRegex(ValueError, 'screen-sharing-first-login'):
            self.run_manifest()

        template = self.value['checks'][0]
        self.value['checks'].extend(dict(template, id=name) for name in sorted(VERSION_11_CHECKS))
        self.assertEqual(self.run_manifest()['scenarios'], len(REQUIRED | VERSION_11_CHECKS))

        next(row for row in self.value['checks'] if row['id'] == 'screen-sharing-first-login').update(
            artifact='packages', artifact_sha256=self.artifacts['packages']['sha256'])
        with self.assertRaisesRegex(ValueError, 'Compartilhamento de tela precisa identificar a ISO'):
            self.run_manifest()

    def test_modified_iso_and_modified_evidence_are_rejected(self):
        (self.root/'iso').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError, 'Artefato alterado'):self.run_manifest()
        (self.root/'iso').write_bytes(b'fixture-iso')
        (self.root/'evidence.txt').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError, 'Evidência alterada'):self.run_manifest()

    def test_missing_failed_old_or_duplicate_results_are_rejected(self):
        variants = []
        value = copy.deepcopy(self.value);value['checks'].pop();variants.append(value)
        for key, entry in [('status', 'FAIL'), ('version', '0.9.0~beta1'), ('artifact_sha256', '0'*64)]:
            value = copy.deepcopy(self.value);value['checks'][0][key] = entry;variants.append(value)
        value = copy.deepcopy(self.value);value['checks'].append(value['checks'][0]);variants.append(value)
        for value in variants:
            with self.subTest(value=value['checks'][0]), self.assertRaises(ValueError):self.run_manifest(value)

    def test_paths_cannot_escape_release_directory(self):
        for name in ('../outside', '/etc/passwd'):
            self.value['artifacts']['source']['file'] = name
            with self.assertRaises(ValueError):self.run_manifest()

    def test_installed_probe_cannot_replace_exact_iso_install(self):
        value = copy.deepcopy(self.value)
        row = next(row for row in value['checks'] if row['id'] == 'install-server-uefi')
        row.update(artifact='packages', artifact_sha256=self.artifacts['packages']['sha256'])
        with self.assertRaisesRegex(ValueError, 'identificar a ISO'):self.run_manifest(value)

    def test_support_cannot_be_omitted(self):
        self.value['support'] = {}
        with self.assertRaisesRegex(ValueError, 'manutenção'):self.run_manifest()

    def test_publication_cannot_swap_accepted_package_archives(self):
        deb=self.root/'release.deb';deb.write_bytes(b'fixture package')
        rows=[dict(Package='linuxbr-release',Version=self.version,Architecture='all',sha256=hashlib.sha256(deb.read_bytes()).hexdigest())]
        data=json.dumps(rows).encode();(self.root/'packages').write_bytes(data)
        self.value['artifacts']['packages'].update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        self.run_manifest()
        publication_acceptance(self.manifest,self.version,[(deb,'linuxbr-release',self.version,'all')])
        deb.write_bytes(b'different archive')
        with self.assertRaisesRegex(ValueError,'diferem'):publication_acceptance(self.manifest,self.version,[(deb,'linuxbr-release',self.version,'all')])
        with self.assertRaisesRegex(ValueError,'aceitação'):publication_acceptance(None,self.version,[])

    def test_release_stages_and_invalid_versions(self):
        for value, channel, display in [('1.0.0~rc1', 'rc', '1.0.0 RC 1'),
                ('1.0.0~beta2', 'beta', '1.0.0 Beta 2'), ('1.0.0', 'stable', '1.0.0')]:
            (self.root/'VERSION').write_text(value)
            info = release_info(self.root)
            self.assertEqual((info['channel'], info['display_version']), (channel, display))
        for value in ('1.0.0~rc0', '1.0.0~rc1;id', '1.0', '../1.0.0', '1.0.0~rc-1'):
            (self.root/'VERSION').write_text(value)
            with self.assertRaises(ValueError):release_info(self.root)


if __name__ == '__main__':unittest.main()
