import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import startup_backend as backend


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.user = self.root / 'user'
        self.system = self.root / 'system'
        for path in (self.user, self.system):
            (path / 'autostart').mkdir(parents=True)
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.user), XDG_CONFIG_DIRS=str(self.system), XDG_CURRENT_DESKTOP='KDE')
        env.start();self.addCleanup(env.stop)
        self.original = b'[Desktop Entry]\nType=Application\nName=Example\nName[pt_BR]=Exemplo\nExec=/usr/bin/true\nOnlyShowIn=KDE;\n\n[Desktop Action Test]\nName=Action\nExec=/usr/bin/false\n'
        self.file = self.system / 'autostart/example.desktop'
        self.file.write_bytes(self.original)

    def row(self):
        return next(r for r in backend.inventory() if r['id'] == 'example.desktop')

    def test_system_override_restore(self):
        row = self.row()
        self.assertEqual(row['name'], 'Exemplo')
        backend.change(row['id'], row['sha256'], False)
        self.assertTrue(self.row()['hidden'])
        self.assertEqual(self.file.read_bytes(), self.original)
        self.assertEqual(backend.entry((self.user / 'autostart/example.desktop').read_bytes())['Exec'], '/usr/bin/true')
        row = self.row();backend.change(row['id'], row['sha256'], restore=True)
        self.assertFalse((self.user / 'autostart/example.desktop').exists())
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_personal_exact_restore(self):
        personal = self.user / 'autostart/example.desktop'
        personal.write_bytes(self.original.replace(b'Example', b'Personal'))
        before = personal.read_bytes()
        row = self.row();backend.change(row['id'], row['sha256'], False)
        row = self.row();backend.change(row['id'], row['sha256'], restore=True)
        self.assertEqual(personal.read_bytes(), before)

    def test_stale_read_and_external_edit(self):
        row = self.row()
        self.file.write_bytes(self.original + b'# changed\n')
        with self.assertRaises(ValueError):
            backend.change(row['id'], row['sha256'], False)
        row = self.row();backend.change(row['id'], row['sha256'], False)
        personal = self.user / 'autostart/example.desktop'
        personal.write_bytes(personal.read_bytes() + b'# external\n')
        row = self.row()
        with self.assertRaises(ValueError):
            backend.change(row['id'], row['sha256'], restore=True)

    def test_conditions_and_priority(self):
        self.file.write_bytes(self.original.replace(b'KDE;', b'GNOME;'))
        self.assertIn('outro ambiente', self.row()['status'])
        personal = self.user / 'autostart/example.desktop'
        personal.write_bytes(self.original + b'\n')
        self.assertEqual(len(backend.inventory()), 1)
        self.assertEqual(self.row()['origin'], 'Minha conta')

    def test_symlink_and_path_guard(self):
        (self.user / 'autostart/example.desktop').symlink_to(self.file)
        self.assertFalse(self.row()['editable'])
        with self.assertRaises(ValueError):
            backend.change('../example.desktop', '', False)
        with self.assertRaises(ValueError):
            backend.change('org.kde.plasmashell.desktop', '', False)

    def test_tryexec_and_duplicate_hidden(self):
        self.file.write_bytes(self.original.replace(b'OnlyShowIn=KDE;', b'TryExec=/nonexistent/linuxbr-test'))
        self.assertIn('não encontrado', self.row()['status'])
        self.file.write_bytes(b'[Desktop Entry]\nHidden=true\nHidden=false\n')
        self.assertFalse(self.row()['editable'])


if __name__ == '__main__':
    unittest.main()
