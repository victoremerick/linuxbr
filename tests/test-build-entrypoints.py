#!/usr/bin/env python3
"""Build orchestration regression tests; no container or privileged commands run."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BuildEntrypoints(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'bin').mkdir()
        for name in ['build.sh', 'init-build.sh', 'VERSION', 'scripts/build-output.sh', 'scripts/build-in-container.sh', 'scripts/Containerfile.build']:
            shutil.copy2(ROOT / name, self.root / name)
        self.env = {**os.environ, 'PATH': str(self.root / 'bin') + ':' + os.environ['PATH'],
                    'CONTAINER_ENGINE': 'fake-engine'}
        self.stub('fake-engine', 'echo full-detail-marker\nexit "${FAKE_EXIT:-0}"')

    def stub(self, name, body):
        p = self.root / 'bin' / name
        p.write_text('#!/bin/bash\nset -eu\n' + body + '\n')
        p.chmod(0o755)

    def run_build(self, *args):
        return subprocess.run(['bash', str(self.root / 'build.sh'), *args], env=self.env,
                              capture_output=True, text=True)

    def test_quiet_logs_details(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('full-detail-marker', result.stdout)
        log = next((self.root / '.cache/logs').glob('*.log'))
        self.assertIn('full-detail-marker', log.read_text())

    def test_progress_tracks_stage_and_failure_does_not_complete(self):
        self.stub('fake-engine', 'echo "LINUXBR_STAGE 4"\nsleep 1.2\nexit 7')
        result = self.run_build()
        self.assertEqual(result.returncode, 7)
        self.assertIn('Validando sistema live (4/6 etapas)', result.stdout)
        self.assertNotIn('6/6 etapas', result.stdout)
        self.assertNotIn('\x1b', result.stdout)

    def test_banner_version_and_success(self):
        result = self.run_build()
        self.assertIn((self.root / 'VERSION').read_text().strip() + ' Alpha', result.stdout)
        self.assertIn('[######] 6/6 etapas', result.stdout)

    def test_banner_art_is_literal_and_plain_output_has_no_escape_codes(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0)
        self.assertIn('LLLLL III  N   N', result.stdout)
        self.assertNotIn('\x1b', result.stdout)
        self.assertNotIn('\\\\', result.stdout)

    def test_verbose_aliases(self):
        for arg in ['-v', '--verbose']:
            result = self.run_build(arg)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('full-detail-marker', result.stdout)

    def test_failure_is_visible_and_preserves_exit_code(self):
        self.env['FAKE_EXIT'] = '7'
        for args in [[], ['-v']]:
            result = self.run_build(*args)
            self.assertEqual(result.returncode, 7)
            self.assertIn('full-detail-marker', result.stdout + result.stderr)
            self.assertNotIn('ISO pronta', result.stdout)

    def test_cached_image_skips_tool_installation(self):
        self.stub('fake-engine', 'echo "$*" >> engine-calls\nexit 0')
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.root / 'engine-calls').read_text().splitlines()
        self.assertTrue(any(line.startswith('image inspect localhost/linuxbr-builder:') for line in calls))
        self.assertFalse(any(line.startswith('build ') for line in calls))
        self.assertTrue(any(line.startswith('run ') for line in calls))

    def test_no_cache_refreshes_builder_and_disables_archives(self):
        self.stub('fake-engine', 'echo "$*" >> engine-calls\nexit 0')
        result = self.run_build('--no-cache')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.root / 'engine-calls').read_text().splitlines()
        self.assertTrue(any(line.startswith('pull docker.io/library/debian:trixie') for line in calls))
        self.assertTrue(any(line.startswith('build --no-cache ') for line in calls))
        self.assertTrue(any('LINUXBR_NO_CACHE=1' in line for line in calls))

    def test_builder_failure_does_not_start_iso(self):
        self.stub('fake-engine', 'echo "$1" >> engine-calls\ncase "$1" in image) exit 1;; build) exit 42;; esac')
        result = self.run_build()
        self.assertEqual(result.returncode, 42)
        self.assertNotIn('run', (self.root / 'engine-calls').read_text().splitlines())
        self.assertNotIn('ISO pronta', result.stdout)

    def test_firmware_selection_uses_explicit_payloads(self):
        build = (ROOT / 'scripts/build-in-container.sh').read_text()
        self.assertIn('--firmware-chroot false', build)
        self.assertIn('--firmware-binary false', build)
        packages = {line.strip() for line in (ROOT / 'config/package-lists/linuxbr.list.chroot').read_text().splitlines() if line.strip() and not line.startswith('#')}
        self.assertFalse({'firmware-b43-installer', 'firmware-b43legacy-installer'} & packages)
        self.assertTrue({'firmware-linux', 'firmware-brcm80211', 'firmware-iwlwifi', 'firmware-realtek', 'firmware-atheros', 'firmware-mediatek'} <= packages)

    def test_unknown_option(self):
        self.assertEqual(self.run_build('--invalid').returncode, 2)

    def test_init_forwards_verbosity_and_hides_validation_details(self):
        (self.root / 'tests').mkdir()
        verify = self.root / 'tests/verify-iso.sh'
        verify.write_text('#!/bin/sh\necho validation-detail-marker\n')
        verify.chmod(0o755)
        self.stub('sudo', 'exec "$@"')
        self.stub('xorriso', 'exit 0')
        for args in [[], ['-v'], ['--verbose']]:
            result = subprocess.run(['bash', str(self.root / 'init-build.sh'), *args],
                                    env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual('full-detail-marker' in result.stdout, bool(args))
            self.assertEqual('validation-detail-marker' in result.stdout, bool(args))
            self.assertEqual(result.stdout.count('Alpha · amd64'), 1)

    def test_container_script_can_be_rewritten_while_lb_runs(self):
        for folder in ['packages', 'config', 'tests']:
            (self.root / folder).mkdir()
        script = self.root / 'scripts/build-in-container.sh'
        script.write_text(script.read_text().replace('/src', str(self.root)))
        self.env['RUNNING_SCRIPT'] = str(script)
        (self.root / 'scripts/build-dolphin.sh').write_text('#!/bin/sh\nexit 0\n')
        self.stub('apt-get', 'exit 0')
        self.stub('python3', '''if [[ "$1" == *build-packages.py ]]; then
    mkdir -p "$3"
    touch "$3/UPSTREAM-SHA256SUMS"
fi''')
        self.stub('lb', '''if [[ "$1" == build ]]; then
    printf 'blisher: invalid replacement )\n' > "$RUNNING_SCRIPT"
    printf 'fake ISO\n' > live-image-amd64.hybrid.iso
fi''')
        result = subprocess.run(['bash', str(script)], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / ('dist/linuxbr-' + (self.root / 'VERSION').read_text().strip() + '-amd64.iso.sha256')).exists())
        self.assertIn('ISO pronta', result.stdout)

if __name__ == '__main__':
    unittest.main()
