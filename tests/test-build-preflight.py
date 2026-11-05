"""Reject insufficient space before any expensive build operation."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from build_preflight import GIB, check


class BuildSpace(unittest.TestCase):
    def test_threshold_and_failure_leave_workspace_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            for free in (32*GIB-1, 32*GIB, 40*GIB):
                with self.subTest(free=free), patch('build_preflight.shutil.disk_usage', return_value=SimpleNamespace(free=free)):
                    if free < 32*GIB:
                        with self.assertRaisesRegex(ValueError,'Espaço insuficiente'):check(folder)
                    else:
                        self.assertEqual(check(folder)['free_bytes'],free)
                self.assertEqual(list(Path(folder).iterdir()),[])

    def test_invalid_thresholds_and_missing_path_are_rejected(self):
        for value in ('', '0', '-1', '1.5', '1025', 'invalid', '３２'):
            with self.subTest(value=value), self.assertRaises(ValueError):check(Path.cwd(),value)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):check(Path(folder)/'missing')


if __name__ == '__main__':unittest.main()
