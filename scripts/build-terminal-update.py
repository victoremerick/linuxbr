#!/usr/bin/python3
"""Build the terminal/batch update against the original 0.6 Beta 1 packages."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FILES={
    'linuxbr-drive-manager':[
        'usr/share/linuxbr/terminal.bash',
        'usr/lib/linuxbr-drive-manager/windows_commands.py'],
    'linuxbr-system':[
        'usr/lib/linuxbr-system/windows_runner.py',
        'usr/lib/linuxbr-system/windows_compat.py',
        'usr/share/applications/linuxbr-windows.desktop',
        'usr/share/kio/servicemenus/linuxbr-batch.desktop',
        'usr/share/mime/packages/linuxbr-batch.xml',
        'etc/xdg/mimeapps.list']}


def build(base,output):
    output.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for package,files in FILES.items():
        matches=list(base.glob(package+'_0.6.0~beta1_*.deb'))
        if len(matches)!=1:raise ValueError('Selecione exatamente um pacote base: '+package)
        original=matches[0]
        actual=subprocess.check_output(['dpkg-deb','-f',str(original),'Package'],text=True).strip()
        if actual!=package:raise ValueError('Pacote base inválido.')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/package
            subprocess.run(['dpkg-deb','-R',str(original),str(root)],check=True)
            control=root/'DEBIAN/control'
            control.write_text(control.read_text().replace('Version: 0.6.0~beta1\n','Version: 0.6.0~beta1+terminal1\n'))
            for filename in files:
                source=ROOT/'packages'/package/'files'/filename
                dest=root/filename;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,dest)
                dest.chmod(0o755 if source.read_bytes().startswith(b'#!') else 0o644)
            sums=root/'DEBIAN/md5sums'
            if sums.exists():
                sums.write_text(''.join(hashlib.md5(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n'
                    for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink() and 'DEBIAN' not in p.relative_to(root).parts))
            arch=subprocess.check_output(['dpkg-deb','-f',str(original),'Architecture'],text=True).strip()
            target=output/(package+'_0.6.0~beta1+terminal1_'+arch+'.deb')
            subprocess.run(['dpkg-deb','--root-owner-group','--build',str(root),str(target)],check=True)
            manifest.append(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name)
    (output/'SHA256SUMS').write_text('\n'.join(manifest)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    build(args.base,args.output)
