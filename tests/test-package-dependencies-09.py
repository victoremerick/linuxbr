import importlib.util
from pathlib import Path
import sys
import unittest

scripts=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('build_packages',scripts/'build-packages.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class OptionalDependencies(unittest.TestCase):
    def test_merges_existing_recommendations_without_duplicate_fields(self):
        text='Package: sample\nDepends: python3, samba, linuxbr-release (= 0.9.0~beta1), bluedevil\nRecommends: acl, samba\nDescription: sample\n body\n'
        result=builder.optional_metadata(text)
        self.assertEqual(result.count('Recommends:'),1)
        self.assertIn('Depends: python3, linuxbr-release (= 0.9.0~beta1)\n',result)
        self.assertIn('Recommends: samba, bluedevil, acl\n',result)
        self.assertEqual(builder.optional_metadata(result),result)


if __name__=='__main__':unittest.main()
