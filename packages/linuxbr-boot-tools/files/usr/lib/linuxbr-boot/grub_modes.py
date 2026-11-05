"""Build maintenance entries from the distribution's generated kernel stanza."""
import re
import subprocess
import sys

MODES={
 'normal':('Inicialização normal',''),
 'safe':('Modo de segurança — sem rede','linuxbr.mode=safe systemd.unit=linuxbr-safe.target'),
 'safe-network':('Modo de segurança com rede','linuxbr.mode=safe-network systemd.unit=linuxbr-safe.target'),
 'safe-terminal':('Modo de segurança com terminal','linuxbr.mode=safe-terminal systemd.unit=linuxbr-safe.target'),
 'basic-video':('Vídeo básico','module_blacklist=amdgpu,radeon,nouveau,nvidia,nvidia_drm,nvidia_modeset,i915,xe linuxbr.video=basic'),
 'diagnostic':('Diagnóstico de inicialização','systemd.log_level=debug systemd.log_target=journal-or-kmsg linuxbr.diagnostic=1'),
 'recovery':('Ambiente de manutenção','linuxbr.mode=recovery systemd.unit=linuxbr-safe.target'),
}


def stanza(text):
    lines=text.splitlines();start=next((i for i,line in enumerate(lines) if line.startswith('menuentry ')),None)
    if start is None:raise ValueError('Nenhuma entrada de kernel reconhecida.')
    end=next((i for i in range(start+1,len(lines)) if lines[i]=='}'),None)
    if end is None:raise ValueError('Entrada de kernel incompleta.')
    body=lines[start+1:end]
    kernels=[i for i,line in enumerate(body) if re.match(r'^\s*linux(?:efi)?\s+',line)]
    if len(kernels)!=1 or not any(re.match(r'^\s*initrd(?:efi)?\s+',line) for line in body):
        raise ValueError('Esta configuração de kernel exige manutenção manual.')
    if not re.search(r'\broot=',body[kernels[0]]):raise ValueError('Raiz do sistema não identificada.')
    return body


def render(text):
    body=stanza(text);out=["submenu 'Linux BR — Opções avançadas (F8)' --hotkey=f8 --id=linuxbr-options {"]
    for identifier,(title,flags) in MODES.items():
        out.append("menuentry '"+title+"' --id=linuxbr-"+identifier+" {")
        for line in body:
            if re.match(r'^\s*savedefault\s*$',line):continue
            if re.match(r'^\s*linux(?:efi)?\s+',line):
                # Mode switches belong only to these entries, never to the shared kernel defaults.
                line=re.sub(r'\s+(?:linuxbr\.(?:mode|video|diagnostic)|systemd\.unit)=[^\s]+','',line)
                if flags:line+=' '+flags
            out.append(line)
        out.append('}')
    out.append('}')
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    try:
        generated=subprocess.run(['/etc/grub.d/10_linux'],check=True,capture_output=True,text=True,timeout=90)
        print(render(generated.stdout),end='')
    except (ValueError,subprocess.SubprocessError) as error:
        print('Linux BR: opções avançadas não geradas: '+str(error),file=sys.stderr)
        sys.exit(1)
