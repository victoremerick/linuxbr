"""Conservative NVIDIA provider using Debian's installed PCI support database."""
from pathlib import Path
import platform
import re
from hardware import command, package_status

NVIDIA_PACKAGES={'nvidia-driver','nvidia-tesla-535-driver'}

def secure_boot_ready(runner=command,efi=Path('/sys/firmware/efi'),key=Path('/var/lib/dkms/mok.pub')):
    if not efi.exists():return ''
    code,out,err=runner(['/usr/bin/mokutil','--sb-state'])
    if code==0 and 'SecureBoot disabled' in out:return ''
    if code==0 and 'SecureBoot enabled' in out:
        if key.is_file() and runner(['/usr/bin/mokutil','--test-key',str(key)])[0]==0:return ''
        return 'Secure Boot ativo: cadastre a chave DKMS/MOK antes de instalar. Consulte Ajuda NVIDIA.'
    return 'Não foi possível verificar Secure Boot; consulte Ajuda NVIDIA antes de instalar.'

def prerequisites(runner=command,release=None,live=Path('/run/live/medium')):
    if live.exists():return [],'Instale no sistema instalado, não na sessão Live.'
    if platform.machine() not in ('x86_64','amd64'):return [],'Instalação automática NVIDIA disponível somente em amd64.'
    release=release or platform.release()
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+_-]*',release):return [],'Kernel não reconhecido.'
    header='linux-headers-'+release
    state=package_status(header,runner)
    if not state['candidate'] and not state['installed_version']:
        return [],'Headers do kernel em execução indisponíveis. Inicie com um kernel Debian suportado e atualize os índices.'
    return [header,'linux-headers-amd64','dkms'],secure_boot_ready(runner)

def nvidia_options(rows,runner=command,checks=prerequisites):
    cards=[r for r in rows if r.get('bus')=='PCI' and r.get('category')=='Vídeo' and re.fullmatch(r'0x10de:0x[0-9a-fA-F]{4}',r.get('hardware_id',''))]
    if not cards:return []
    matches={};unknown=[];outputs=[]
    for card in cards:
        pci='10de:'+card['hardware_id'].split(':')[1][2:]
        code,out,err=runner(['/usr/bin/nvidia-detect',pci])
        outputs.append(card['name']+':\n'+(out or err).strip())
        # Only the exact recommendation, never mentions of alternative/legacy branches.
        recommendation=re.search(r'It is recommended to install the\s+([a-z0-9-]+)\s+package\.',out)
        package=recommendation.group(1) if code==0 and recommendation else None
        if package not in NVIDIA_PACKAGES:unknown.append(card);continue
        matches.setdefault(package,[]).append(card)
    deps,blocked=checks(runner)
    if unknown or len(matches)>1:
        blocked='Compatibilidade não confirmada para todas as GPUs NVIDIA. Não será feita troca automática de ramo; consulte Ajuda NVIDIA.'
    detector=package_status('nvidia-detect',runner)
    result=[]
    for package,cards_for_package in matches.items():
        state=package_status(package,runner)
        reason=blocked
        if package=='nvidia-driver' and state['candidate'] and detector['installed_version']!=state['candidate']:
            reason='Atualize nvidia-detect para a versão correspondente ao driver antes de instalar.'
        if package=='nvidia-tesla-535-driver' and state['candidate'] and not state['candidate'].split(':')[-1].startswith('535.'):
            reason='Versão Tesla fora do ramo 535 validado pelo detector.'
        if reason:state.update(action='',status=reason)
        result.append(dict(package=package,description='NVIDIA — driver proprietário Debian',type='Proprietário',related=True,
             devices=[dict(id=r['id'],name=r['name'],reason='Recomendação do nvidia-detect para o ID PCI') for r in cards_for_package],
             notes='\n'.join(outputs),prerequisites=deps,**state))
    if unknown:
        result.append(dict(package='nvidia-unsupported',description='NVIDIA — análise necessária',type='Proprietário',related=True,
             devices=[dict(id=r['id'],name=r['name'],reason='Sem recomendação compatível no detector local') for r in unknown],
             installed='',installed_version='',candidate='',action='',status=blocked,notes='\n'.join(outputs)))
    if detector['action']:
        result.append(dict(package='nvidia-detect',description='Atualizar detector NVIDIA',type='Ferramenta',related=True,
             devices=[dict(id=r['id'],name=r['name'],reason='Base de compatibilidade do Debian') for r in cards],**detector))
    return result
