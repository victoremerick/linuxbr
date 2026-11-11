"""Exercise opt-in, source validation and native transaction boundaries."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import store_optional as optional
import store_backend
import store_format_tests as evidence
import store_portable as portable
from store_transactions import checked_request


SNAP = dict(name='example-app', type='app', confinement='strict', version='1.2', revision=12)
PARTIAL = {'confinement': 'partial', 'sandbox-features': {
    'apparmor': ['kernel:file', 'parser:unsafe', 'support-level:partial'],
    'confinement-options': ['classic', 'devmode'],
}}
FORMULA = dict(name='example-cli', tap='homebrew/core', versions={'stable': '2.0'},
               bottle={'stable': {'files': {'x86_64_linux': {}}}})


def request(manager, action='install', **values):
    row = SNAP if manager == 'snap' else FORMULA
    origin, scope, _ = optional.PROVIDERS[manager]
    return checked_request(dict(manager=manager, target=row['name'], action=action,
                                scope=scope, origin=origin, confinement='strict') | values)


class OptionalSources11(unittest.TestCase):
    def test_opt_in_is_local_and_org_policy_overrides_it(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)
            policy = config / 'policy.json'
            with (patch.dict(os.environ, XDG_CONFIG_HOME=folder),
                  patch.object(optional, 'POLICY', policy)):
                self.assertFalse(optional.enabled('snap'))
                optional.set_enabled('snap', True)
                self.assertTrue(optional.enabled('snap'))
                self.assertEqual(json.loads(optional.preferences().read_text()), {'snap': True})
                policy.write_text('{malformed')
                self.assertFalse(optional.enabled('snap'))
                with self.assertRaises(ValueError):
                    optional.set_enabled('snap', True)
                policy.unlink()
                policy.symlink_to(config / 'missing')
                self.assertFalse(optional.enabled('snap'))

    def test_disabled_providers_do_not_query_native_or_network(self):
        with (patch.object(optional, 'enabled', return_value=False),
              patch.object(optional, 'snap_get') as snap,
              patch.object(optional, 'brew_api') as brew):
            self.assertEqual(optional.search('example'), ([], []))
            self.assertEqual(optional.inventory(), ([], []))
            self.assertEqual(optional.updates(), ([], []))
            with self.assertRaisesRegex(ValueError, 'não está habilitada'):
                optional.command(request('snap'))
            snap.assert_not_called()
            brew.assert_not_called()

    def test_snap_install_uses_native_stable_on_full_and_supported_partial_hosts(self):
        for info in ({'confinement': 'strict'}, PARTIAL):
            with (self.subTest(info=info), patch.object(optional, 'enabled', return_value=True),
                  patch.object(optional, 'provider_inventory', return_value=[]),
                  patch.object(optional, 'snap_get', side_effect=[[SNAP], info])):
                self.assertEqual(optional.command(request('snap')),
                                 (['/usr/bin/pkexec', '/usr/bin/snap', 'install', '--stable', 'example-app'], None))

    def test_snap_install_rejects_partial_without_usable_apparmor(self):
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', return_value=[]),
              patch.object(optional, 'snap_get', side_effect=[[SNAP], {'confinement': 'partial'}])):
            with self.assertRaisesRegex(ValueError, 'AppArmor'):
                optional.command(request('snap'))

    def test_snap_refresh_checks_support_and_removal_remains_available(self):
        installed = [optional.entry('snap', SNAP, installed=True)]
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', return_value=installed),
              patch.object(optional, 'snap_get', return_value=PARTIAL) as query):
            self.assertEqual(optional.command(request('snap', 'update')),
                             (['/usr/bin/pkexec', '/usr/bin/snap', 'refresh', 'example-app'], None))
            query.return_value = {}
            with self.assertRaisesRegex(ValueError, 'confirmar o suporte'):
                optional.command(request('snap', 'update'))
            self.assertEqual(optional.command(request('snap', 'remove'))[0][-2:], ['remove', 'example-app'])

    def test_snap_classic_confirmation_is_required_and_mode_is_rechecked(self):
        classic = dict(SNAP, confinement='classic')
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', return_value=[]),
              patch.object(optional, 'snap_get', side_effect=lambda path, **_: (
                  PARTIAL if path == '/v2/system-info' else [classic]))):
            with self.assertRaisesRegex(ValueError, 'mudou'):
                optional.command(request('snap'))
            with self.assertRaisesRegex(ValueError, 'confirmação'):
                optional.command(request('snap', confinement='classic'))
            argv, _ = optional.command(request('snap', confinement='classic', classic_confirmed=True))
            self.assertEqual(argv[-3:], ['--stable', '--classic', 'example-app'])

    def test_brew_core_target_is_architecture_specific_and_unprivileged(self):
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', return_value=[]),
              patch.object(optional, 'brew_api', return_value=FORMULA),
              patch.object(optional, 'brew_binary', return_value='/prefix/bin/brew'),
              patch.object(optional.platform, 'machine', return_value='x86_64'),
              patch.dict(os.environ, {'HOMEBREW_API_DOMAIN': 'https://other.test', 'BASH_ENV': '/unexpected'})):
            argv, env = optional.command(request('brew'))
            self.assertEqual(argv, ['/prefix/bin/brew', 'install', '--formula', 'homebrew/core/example-cli'])
            self.assertNotIn('HOMEBREW_API_DOMAIN', env)
            self.assertNotIn('BASH_ENV', env)
            self.assertEqual(env['HOMEBREW_NO_SUDO'], '1')
        with patch.object(optional.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(ValueError, 'proprietária'):
                optional.brew_binary()
        for values in ({'target': 'custom/tap/tool'}, {'target': '--force'}, {'scope': 'system'}):
            with self.assertRaises(ValueError):
                request('brew', **values)

    def test_updates_and_removal_keep_the_original_provider(self):
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', side_effect=lambda manager: [
                  optional.entry(manager, SNAP if manager == 'snap' else FORMULA, installed=True)]),
              patch.object(optional, 'snap_get', return_value=[SNAP]),
              patch.object(optional, 'brew_query', return_value={'formulae': [dict(name=FORMULA['name'])]}),
              patch.object(optional, 'brew_binary', return_value='/prefix/bin/brew')):
            rows, errors = optional.updates()
            self.assertFalse(errors)
            self.assertEqual([(row['manager'], row['scope']) for row in rows], [('snap', 'system'), ('brew', 'user')])
            snap, _ = optional.command(request('snap', 'remove'))
            brew, _ = optional.command(request('brew', 'remove'))
            self.assertEqual(snap[-2:], ['remove', 'example-app'])
            self.assertEqual(brew[-3:], ['uninstall', '--formula', 'homebrew/core/example-cli'])

    def test_snap_desktop_does_not_fall_back_to_removing_snapd(self):
        entry = dict(id='desktop:example-app_main.desktop', kind='linux', name='Example',
                     provider_hint='snap', desktop_file='/var/lib/snapd/desktop/applications/example-app_main.desktop',
                     _executable='/snap/bin/example-app')
        with (patch.object(store_backend, 'query_local') as query,
              patch.object(optional, 'enabled', return_value=False)):
            self.assertEqual(store_backend.package_targets(entry), [])
            query.assert_not_called()
        provider = optional.entry('snap', SNAP, installed=True)
        with (patch.object(store_backend, 'desktop_applications', return_value=[entry]),
              patch.object(optional, 'enabled', return_value=True),
              patch('webapps_backend.installed', return_value=[]),
              patch('windows_runner.programs', return_value=[])):
            rows = store_backend.installed_entries([provider])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['optional_target']['manager'], 'snap')
            self.assertEqual(rows[0]['desktop_file'], entry['desktop_file'])

    def test_removed_desktop_launcher_is_reported_as_unavailable(self):
        from gi.repository import Gio

        with patch.object(Gio.DesktopAppInfo, 'new', side_effect=TypeError('constructor returned NULL')):
            with self.assertRaisesRegex(ValueError, 'aplicativo não está mais disponível'):
                store_backend.local_action({'desktop_id': 'example-app_main.desktop'})

    def test_installed_snap_reports_scheduler_information(self):
        info = {'refresh': {'next': '2026-11-11T01:30:00Z', 'hold': '2026-11-11T01:00:00Z'}}
        with patch.object(optional, 'snap_get', side_effect=[[SNAP], info]):
            row, = optional.provider_inventory('snap')
        self.assertIn('Próxima atualização automática 2026-11-11T01:30:00Z', row['note'])
        self.assertIn('Atualizações adiadas até 2026-11-11T01:00:00Z', row['note'])

    def test_partial_confinement_is_visible_in_sources_and_before_operations(self):
        info = dict(PARTIAL)
        classic = dict(SNAP, name='example-classic', confinement='classic')
        responses = {'/v2/system-info': info, '/v2/snaps': [],
                     '/v2/find': [dict(SNAP, title='Exemplo'), classic]}
        with tempfile.TemporaryDirectory() as directory:
            snap = Path(directory) / 'snap'
            snap.touch()
            with (patch.object(optional, 'SNAP', snap),
                  patch.object(optional, 'SNAP_SOCKET', snap),
                  patch.object(optional, 'allowed', side_effect=lambda manager: manager == 'snap'),
                  patch.object(optional, 'enabled', side_effect=lambda manager: manager == 'snap'),
                  patch.object(optional, 'snap_get', side_effect=lambda path, **_: responses[path]) as query):
                source = optional.sources()[0]
                self.assertIn('Confinamento parcial', source['status'])
                self.assertIn('permissivos', source['content'])
                rows, errors = optional.search('example')
                self.assertEqual(errors, [])
                self.assertEqual(rows[0]['optional_target']['confinement_note'], source['content'])
                self.assertIn(source['content'], rows[0]['note'])
                self.assertTrue(all('blocked_reason' not in row['optional_target'] for row in rows))
                self.assertEqual(store_backend.search(rows, SNAP['name']), [rows[0]])
                self.assertEqual(sum(call.args == ('/v2/system-info',) for call in query.call_args_list), 2)
                info['confinement'] = 'strict'
                rows, errors = optional.search('example')
                self.assertEqual(errors, [])
                self.assertNotIn('confinement_note', rows[0]['optional_target'])
                info.update(confinement='partial', **{'sandbox-features': {}})
                rows, errors = optional.search('example')
                self.assertEqual(errors, [])
                self.assertIn('AppArmor', rows[0]['optional_target']['blocked_reason'])

    def test_portable_mixed_list_preserves_format_version_and_origin(self):
        snap = optional.entry('snap', dict(SNAP, **{'tracking-channel': 'latest/stable'}), installed=True)
        brew = optional.entry('brew', dict(FORMULA, installed=[{'version': '1.9'}]), installed=True)
        flatpak = ('org.example.Editor/x86_64/stable', 'verified', 'a' * 64)
        with (patch.object(optional, 'inventory', return_value=([snap, brew], [])),
              patch.object(portable, 'remotes', return_value={'verified': 'https://example.test/repo/'}),
              patch.object(portable, 'installed', side_effect=lambda scope: [flatpak] if scope == 'user' else []),
              patch.object(portable, 'flatpak', return_value='org.example.Editor\tx86_64\tstable\t3.0'),
              patch.object(portable, 'manual_entries', return_value=[])):
            rows = portable.exportable()
        self.assertEqual([(row['manager'], row['version']) for row in rows],
                         [('snap', '1.2'), ('brew', '1.9'), ('flatpak', '3.0')])
        self.assertEqual(rows[0]['channel'], 'latest/stable')
        self.assertEqual(rows[0]['revision'], '12')
        self.assertEqual(rows[1]['origin'], 'Homebrew Core')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            def write(values):
                path.write_text(json.dumps(dict(schema=2, apps=values)), encoding='utf-8')
            write(rows)
            self.assertEqual(portable.load(path), rows)
            for modified in (dict(rows[1], ref='other/tap/example-cli'),
                             dict(rows[1], origin_sha256='a' * 64), dict(rows[1], command='unexpected')):
                write([modified])
                with self.assertRaises(ValueError):
                    portable.load(path)

    def test_portable_preview_keeps_brew_version_and_existing_installation(self):
        origin, scope, url = optional.PROVIDERS['brew']
        row = dict(manager='brew', ref=FORMULA['name'], scope=scope, origin=origin,
                   origin_sha256=portable.fingerprint(url), version='1.9')
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', return_value=[]) as inventory,
              patch.object(optional, 'available_entry', return_value=optional.entry('brew', FORMULA)) as available):
            self.assertIn('versão disponível 2.0', portable.review([row])[0][1])
            inventory.return_value = [optional.entry('brew', FORMULA, installed=True)]
            available.reset_mock()
            self.assertEqual(portable.review([row])[0][1], 'Já instalado')
            available.assert_not_called()
        request = portable.install_request(row)
        self.assertEqual((request['manager'], request['scope'], request['origin']), ('brew', scope, origin))

    def test_portable_preview_marks_disabled_and_unsupported_formats_as_manual(self):
        origin, scope, url = optional.PROVIDERS['snap']
        row = dict(manager='snap', ref=SNAP['name'], scope=scope, origin=origin,
                   origin_sha256=portable.fingerprint(url), version='1.2',
                   confinement='strict', channel='latest/stable', revision='12')
        with (patch.object(optional, 'enabled', return_value=False),
              patch.object(optional, 'provider_inventory') as inventory,
              patch.object(optional, 'available_entry') as available):
            self.assertIn('habilite a fonte', portable.review([row])[0][1])
            inventory.assert_not_called()
            available.assert_not_called()
        with (patch.object(optional, 'enabled', return_value=True),
              patch.object(optional, 'provider_inventory', return_value=[]),
              patch.object(optional, 'available_entry', return_value=optional.entry('snap', SNAP)),
              patch.object(optional, 'snap_get', return_value={'confinement': 'partial'}) as query):
            self.assertIn('Ação manual', portable.review([row])[0][1])
            self.assertIn('canal registrado', portable.review([dict(row, channel='latest/edge')])[0][1])
            query.return_value = PARTIAL
            state = portable.review([row])[0][1]
            self.assertTrue(state.startswith(portable.INSTALLABLE))
            self.assertIn('confinamento parcial', state)
        classic = dict(row, confinement='classic')
        self.assertFalse(portable.install_request(classic)['classic_confirmed'])
        self.assertTrue(portable.install_request(classic, classic_confirmed=True)['classic_confirmed'])
        with self.assertRaisesRegex(ValueError, 'manualmente'):
            portable.install_request(dict(row, channel='latest/edge'))

    def test_homebrew_laboratory_evidence_does_not_certify_release_or_snap(self):
        records = ROOT / 'packages/linuxbr-system/files/usr/share/linuxbr/store/format-tests.json'
        with (patch.object(evidence, 'RECORDS', records),
              patch.object(evidence.platform, 'machine', return_value='x86_64'),
              patch('store_backend.query_local', return_value='1.1.0')):
            result = evidence.target_assessment(dict(manager='brew', target='hello', scope='user', origin='Homebrew Core'))
            self.assertTrue(result.startswith(evidence.UNKNOWN))
            self.assertIn('Ensaio de laboratório · 2.12.3', result)
            self.assertEqual(evidence.target_assessment(dict(manager='snap', target='hello-world')), evidence.UNKNOWN)

    def test_portable_manual_references_omit_private_fields_and_never_install(self):
        desktop = [dict(name='Editor Linux', kind='linux', desktop_file='/usr/share/applications/editor.desktop')]
        webapps = [dict(name='alice@example.test', session='private-session', url='https://example.test/private-path')]
        programs = [dict(name='Editor Windows', file='/home/alice/private-program.exe', environment='private-prefix'),
                    dict(name='alice@example.test')]
        with (patch.object(store_backend, 'desktop_applications', return_value=desktop),
              patch.object(store_backend, 'package_targets', return_value=[
                  dict(manager='deb', target='editor-linux', installed=True)]),
              patch.object(store_backend, 'query_local', return_value='3.4'),
              patch('webapps_backend.installed', return_value=webapps),
              patch('webapps_backend.service_for', return_value={'name': 'Serviço Web'}),
              patch('windows_runner.programs', return_value=programs)):
            rows = portable.manual_entries()
        self.assertEqual([row['manager'] for row in rows], ['deb', 'web', 'windows'])
        self.assertEqual(rows[0]['version'], '3.4')
        document = json.dumps(dict(schema=2, apps=rows))
        for private in ('alice', 'example.test', 'private', '/usr/share', 'environment'):
            self.assertNotIn(private, document)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            path.write_text(document, encoding='utf-8')
            self.assertEqual(portable.load(path), rows)
            path.write_text(json.dumps(dict(schema=2, apps=[dict(rows[2], installer='file:///private.exe')])),
                            encoding='utf-8')
            with self.assertRaises(ValueError):
                portable.load(path)
        self.assertTrue(all(state.startswith('Ação manual') for _, state in portable.review(rows)))
        for row in rows:
            with self.assertRaisesRegex(ValueError, 'escolha manual'):
                portable.install_request(row)


if __name__ == '__main__':
    unittest.main()
