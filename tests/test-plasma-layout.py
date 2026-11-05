#!/usr/bin/python3
"""Reversible patches and upstream drift, without touching the host session."""
import hashlib,importlib.util,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('layout',ROOT/'packages/linuxbr-desktop/files/usr/lib/linuxbr-desktop/plasma-layout.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Patches(unittest.TestCase):
 def test_background_and_program_menus_have_one_action_without_applet_duplicate(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);base=root/'usr/share/plasma/plasmoids'
   panel='org.kde.panel/contents/ui/main.qml'
   applet='org.kde.plasma.taskmanager/contents/ui/main.qml'
   context='org.kde.plasma.taskmanager/contents/ui/ContextMenu.qml'
   originals={panel:'Item {\n    id: root\n}\n',
              applet:'Item {\n    id: tasks\n    TasksModel {\n        id: tasksModel\n    }\n}\n',
              context:'Menu {\n    id: menu\n}\n'}
   for name,text in originals.items():
    file=base/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text)
   module.apply(root)
   self.assertEqual((base/applet).read_text(),originals[applet])
   self.assertNotIn(applet,module.patches())
   for name in (panel,context):
    changed=(base/name).read_text()
    self.assertEqual(changed.count('Gerenciador de Tarefas'),1)
    self.assertEqual(changed.count('linuxbr-action:///tasks'),1)
   once={name:(base/name).read_text() for name in originals}
   module.apply(root);self.assertEqual(once,{name:(base/name).read_text() for name in originals})
   module.apply(root,restore=True)
   self.assertEqual(originals,{name:(base/name).read_text() for name in originals})
 def test_upgrade_retires_old_applet_action_using_saved_upstream_only(self):
  for external_edit in (False,True):
   with self.subTest(external_edit=external_edit),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);name=module.RETIRED_PATCHES[0]
    file=root/'usr/share/plasma/plasmoids'/name;file.parent.mkdir(parents=True)
    original='Item {\n    id: tasks\n    TasksModel {\n        id: tasksModel\n    }\n}\n'
    previous=original.replace('    id: tasks\n','    id: tasks\n    Plasmoid.contextualActions: [ /* previous action */ ]\n')
    state=root/'var/lib/linuxbr/plasma-layout';state.mkdir(parents=True)
    manifest=state/'manifest.json'
    manifest.write_text(json.dumps({name:{'original':original,'patched':hashlib.sha256(previous.encode()).hexdigest()}}))
    current='upstream changed externally\n' if external_edit else previous
    file.write_text(current)
    module.apply(root)
    self.assertEqual(file.read_text(),current if external_edit else original)
    self.assertNotIn(name,json.loads(manifest.read_text()))
    module.apply(root);self.assertEqual(file.read_text(),current if external_edit else original)
 def test_restore_also_retires_previous_applet_action(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);name=module.RETIRED_PATCHES[0]
   file=root/'usr/share/plasma/plasmoids'/name;file.parent.mkdir(parents=True)
   original='upstream';previous='previous patched applet'
   state=root/'var/lib/linuxbr/plasma-layout';state.mkdir(parents=True)
   (state/'manifest.json').write_text(json.dumps({name:{'original':original,'patched':hashlib.sha256(previous.encode()).hexdigest()}}))
   file.write_text(previous);module.apply(root,restore=True)
   self.assertEqual(file.read_text(),original)
 def test_patch_definition_updates_keep_the_upstream_backup(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);name='fixture/main.qml';file=root/'usr/share/plasma/plasmoids'/name
   file.parent.mkdir(parents=True);file.write_text('upstream')
   with patch.object(module,'patches',return_value={name:[('upstream','revision one')]}):module.apply(root)
   self.assertEqual(file.read_text(),'revision one')
   with patch.object(module,'patches',return_value={name:[('upstream','revision two')]}):
    module.apply(root);self.assertEqual(file.read_text(),'revision two')
    module.apply(root,restore=True)
   self.assertEqual(file.read_text(),'upstream')
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
   self.assertIn('Component.onCompleted: Qt.callLater',kickoff)
   module.apply(root);self.assertEqual(once,{name:(base/name).read_text() for name in originals})
   first=next(iter(originals));(base/first).write_text('upstream update with unknown layout')
   module.apply(root);self.assertEqual((base/first).read_text(),'upstream update with unknown layout')
   module.apply(root,restore=True)
   for name in originals:
    self.assertEqual((base/name).read_text(),'upstream update with unknown layout' if name==first else originals[name])
if __name__=='__main__':unittest.main()
