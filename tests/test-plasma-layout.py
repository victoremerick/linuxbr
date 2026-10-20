#!/usr/bin/python3
"""Reversible patches and upstream drift, without touching the host session."""
import importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('layout',ROOT/'packages/linuxbr-desktop/files/usr/lib/linuxbr-desktop/plasma-layout.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Patches(unittest.TestCase):
 def test_idempotence_restore_and_upstream_drift(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);base=root/'usr/share/plasma/plasmoids';originals={}
   for name,edits in module.patches().items():
    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);originals[name]='\n'.join(old for old,new in edits);p.write_text(originals[name])
   module.apply(root);once={name:(base/name).read_text() for name in originals}
   kickoff=once['org.kde.plasma.kickoff/contents/ui/main.qml']
   self.assertEqual(kickoff.count('Plasmoid.contextualActions:'),1)
   self.assertIn('linuxbr-action:///run',kickoff)
   self.assertIn('text: i18n("Edit Applications…")',kickoff)
   module.apply(root);self.assertEqual(once,{name:(base/name).read_text() for name in originals})
   first=next(iter(originals));(base/first).write_text('upstream update with unknown layout')
   module.apply(root);self.assertEqual((base/first).read_text(),'upstream update with unknown layout')
   module.apply(root,restore=True)
   for name in originals:
    self.assertEqual((base/name).read_text(),'upstream update with unknown layout' if name==first else originals[name])
if __name__=='__main__':unittest.main()
