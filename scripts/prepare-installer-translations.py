#!/usr/bin/env python3
"""Correct Portuguese placeholders in the upstream installer translation."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

CORRECTIONS={
    'Keyboard model has been set to %1.':'O modelo de teclado será definido como %1.',
    'Set timezone to %1.':'Definir o fuso horário como %1.',
}


def correct(tree):
    count=0
    for message in tree.findall('.//message'):
        source=message.findtext('source')
        if source in CORRECTIONS:
            translation=message.find('translation')
            if translation is not None:
                translation.text=CORRECTIONS[source]
                translation.attrib.pop('type',None);count+=1
    if count!=len(CORRECTIONS):raise ValueError('As mensagens do instalador mudaram; revise as traduções.')


def prepare(source,output):
    with tempfile.TemporaryDirectory() as directory:
        ts=Path(directory)/'pt_BR.ts'
        tree=ET.parse(source);correct(tree);tree.write(ts,encoding='utf-8',xml_declaration=True)
        destination=output/'usr/share/calamares/lang/calamares_pt_BR.qm'
        destination.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['/usr/lib/qt6/bin/lrelease',str(ts),'-qm',str(destination)],check=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();prepare(args.source,args.output)
