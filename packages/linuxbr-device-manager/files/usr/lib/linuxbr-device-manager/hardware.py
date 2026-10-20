"""Read-only hardware discovery. Never loads/unloads modules or changes devices."""
import glob
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess

B43_PACKAGES = {'firmware-b43-installer': 'b43', 'firmware-b43legacy-installer': 'b43legacy'}
B43_NOTES = ('Baixa firmware adicional de servidores externos durante a instalação. '
             'É necessária internet funcionando (use cabo ou outro adaptador). Falhas de DNS '
             'ou download serão exibidas no log; tente novamente após corrigir a conexão. '
             'Reinicie após instalar. Não é o driver Broadcom STA/wl.')

FIRMWARE_PACKAGES = {
    'firmware-b43-installer': ('Wi-Fi Broadcom b43', ('b43',)),
    'firmware-b43legacy-installer': ('Wi-Fi Broadcom b43legacy', ('b43legacy',)),
    'firmware-iwlwifi': ('Wi-Fi Intel', ('iwlwifi',)),
    'firmware-realtek': ('Rede Realtek', ('r8169','r8152','rtl','rtw')),
    'firmware-atheros': ('Wi-Fi Qualcomm/Atheros', ('ath',)),
    'firmware-brcm80211': ('Wi-Fi Broadcom', ('brcmfmac','brcmsmac')),
    'firmware-mediatek': ('Wi-Fi MediaTek', ('mt76','mt79')),
    'firmware-amd-graphics': ('Vídeo AMD', ('amdgpu','radeon')),
    'firmware-intel-graphics': ('Vídeo Intel', ('i915','xe')),
}

def command(args, timeout=5):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,env={**os.environ,'LC_ALL':'C'})
        return p.returncode,p.stdout,p.stderr
    except (OSError,subprocess.TimeoutExpired) as e:return 1,'',str(e)

def read(path):
    try:return path.read_text(errors='replace').strip()
    except OSError:return ''

def link_name(path):
    try:return path.resolve(strict=True).name
    except OSError:return ''

def category(code):
    try: code=int(code,16)>>16
    except ValueError:return 'Outros'
    return {1:'Armazenamento',2:'Rede',3:'Vídeo',4:'Áudio e multimídia',6:'Pontes e controladores',
            8:'Sistema',9:'Entrada',12:'Controladores de barramento'}.get(code,'Outros')

def discover(sysroot=Path('/sys'), runner=command):
    rows=[]; warnings=[]
    names={}
    code,out,err=runner(['lspci','-D','-mm'])
    if code:warnings.append('Nomes PCI indisponíveis; IDs técnicos continuam disponíveis.')
    else:
        for line in out.splitlines():
            try:
                fields=shlex.split(line)
                if len(fields)>=4:names[fields[0]]=fields[2:4]
            except ValueError:continue
    for bus in ('pci','usb','platform','virtio','ssb','bcma'):
        directory=sysroot/'bus'/bus/'devices'
        try:devices=sorted(directory.iterdir())
        except OSError:continue
        for device in devices:
            if bus=='usb' and ':' in device.name:continue  # interfaces are collected below
            vendor=model=identifier=''
            if bus=='pci':
                vendor,model=names.get(device.name,('', ''))
                identifier=read(device/'vendor')+':'+read(device/'device')
                group=category(read(device/'class'))
            elif bus=='usb':
                vendor=read(device/'manufacturer');model=read(device/'product')
                identifier=read(device/'idVendor')+':'+read(device/'idProduct')
                group='USB'
            elif bus in ('ssb','bcma'):
                identifier=read(device/'modalias')
                vendor='Broadcom' if read(device/'vendor') in ('0x4243','0x04bf') else 'Não informado'
                group='Controladores de barramento'
            else:group='Dispositivos virtuais' if bus=='virtio' else 'Plataforma'
            drivers=set();modules=set();unbound_aliases=[]
            interfaces=[device]
            if bus=='usb':interfaces+=list(directory.glob(device.name+':*'))
            for interface in interfaces:
                driver=link_name(interface/'driver')
                module=link_name(interface/'driver/module')
                if driver:drivers.add(driver)
                if module:modules.add(module)
                if not driver and read(interface/'modalias'):unbound_aliases.append(read(interface/'modalias'))
            # A driver can be built into the kernel and have no module symlink.
            rows.append(dict(id=bus+':'+device.name,bus=bus.upper(),category=group,
                             name=model or device.name,vendor=vendor or 'Não informado',
                             hardware_id=identifier,driver=', '.join(sorted(drivers)),
                             modules=sorted(modules),modalias=read(device/'modalias'),unbound_aliases=unbound_aliases,
                             status=('Há interfaces sem driver (ver detalhes)' if unbound_aliases else 'Driver associado') if drivers else 'Sem driver associado (ver detalhes)'))
    return rows,warnings

def alias_candidates(alias, runner=command):
    if not alias or len(alias)>1024 or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_:*?.-]*',alias):
        return dict(candidates=[],support_note='Sem modalias consultável.')
    code,out,err=runner(['modprobe','--resolve-alias',alias])
    candidates=[m for m in out.splitlines() if re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*',m)]
    if candidates:note='Há módulos candidatos na tabela local; isso não confirma compatibilidade ou funcionamento.'
    elif code and err:note='Não foi possível resolver o modalias na tabela local: '+err.strip()[:250]
    else:note='Nenhum módulo candidato encontrado na tabela local; suporte não identificado.'
    return dict(candidates=candidates,support_note=note)


def module_details(module, runner=command, firmware_root=Path('/lib/firmware')):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*',module):return dict(error='Nome de módulo inválido.')
    code,out,err=runner(['modinfo','-F','firmware',module])
    if code:return dict(error='Metadados indisponíveis para o kernel em execução.')
    declared=[]
    for name in sorted(set(out.splitlines())):
        if not name or name.startswith('/') or '..' in Path(name).parts:continue
        present=any(glob.glob(str(firmware_root/name)+suffix) for suffix in ('','.xz','.zst'))
        declared.append(dict(name=name,present=present))
    return dict(firmware=declared)

def package_status(package, runner=command):
    code,installed,_=runner(['dpkg-query','-W','-f=${db:Status-Status} ${Version}',package])
    installed=installed.strip() if not code and installed.startswith('installed ') else ''
    version=installed.removeprefix('installed ') if installed else ''
    code,policy,_=runner(['apt-cache','policy',package])
    match=re.search(r'^\s*Candidate:\s*(\S+)',policy,re.M) if not code else None
    candidate=match.group(1) if match and match.group(1)!='(none)' else ''
    action='';status='Indisponível nos índices locais'
    if candidate:
        if not version:action='install';status='Disponível para instalar'
        else:
            comparison,_,_=runner(['dpkg','--compare-versions',version,'lt',candidate])
            if comparison==0:action='upgrade';status='Atualização disponível'
            elif comparison==1:
                status='Atualizado' if version==candidate else 'Versão instalada mantida'
            else:status='Não foi possível comparar versões'
    return dict(installed=installed,installed_version=version,candidate=candidate,action=action,status=status)


def firmware_catalog(rows,runner=command):
    result=[]
    for package,(description,prefixes) in FIRMWARE_PACKAGES.items():
        matches=[]
        for row in rows:
            active=row['modules']+[d.strip() for d in row.get('driver','').split(',') if d.strip()]
            candidates=row.get('candidates',[])
            matches_module = (lambda m: m == B43_PACKAGES[package]) if package in B43_PACKAGES else (lambda m: m.startswith(prefixes))
            if any(matches_module(m) for m in active+candidates):
                matches.append(dict(id=row.get('id',''),name=row.get('name',description),
                                    reason='Driver detectado' if any(matches_module(m) for m in active) else 'Módulo candidato local'))
        option=dict(package=package,description=description,type='Firmware',
                    related=bool(matches),devices=matches,**package_status(package,runner))
        if package in B43_PACKAGES:
            option['notes']=B43_NOTES
            if not matches:
                option.update(action='', status='Nenhum dispositivo b43 compatível identificado')
        result.append(option)
    return result


def driver_options(rows,runner=command):
    from proprietary import nvidia_options
    result=firmware_catalog(rows,runner) + nvidia_options(rows,runner)
    # Debian's metapackage follows supported kernel updates, including in-tree drivers.
    # Its version is not the version of every individual driver.
    if platform.machine() in ('x86_64','amd64'):
        result.append(dict(package='linux-image-amd64',description='Kernel e drivers integrados',type='Kernel',
                           related=True,devices=[],**package_status('linux-image-amd64',runner)))
    return result

def resolve_candidates(rows,runner=command):
    for row in rows:
        aliases=row.get('unbound_aliases',[]) or ([row['modalias']] if not row['driver'] else [])
        if aliases:
            resolved=[alias_candidates(alias,runner) for alias in dict.fromkeys(aliases)]
            row['candidates']=sorted({m for result in resolved for m in result['candidates']})
            row['support_note']=' '.join(dict.fromkeys(result['support_note'] for result in resolved))


def collect(runner=command):
    rows,warnings=discover(runner=runner)
    resolve_candidates(rows,runner)
    modules={m:module_details(m,runner) for m in sorted({m for r in rows for m in r['modules']})}
    code,out,err=runner(['journalctl','-k','-b','-n','600','--no-pager','-o','cat'],timeout=8)
    diagnostics=[line for line in out.splitlines() if re.search(r'firmware|failed|error|timeout',line,re.I)][-100:]
    if code or 'permission' in err.lower() or 'not seeing messages' in err.lower():
        warnings.append('O usuário não tem acesso completo ao journal; ausência de mensagens não confirma ausência de falhas.')
    if not rows:warnings.append('Nenhum dispositivo acessível no sysfs.')
    return dict(kernel=platform.release(),architecture=platform.machine(),devices=rows,modules=modules,
                firmware=driver_options(rows,runner),diagnostics=diagnostics,warnings=warnings)

if __name__=='__main__':
    try:print(json.dumps(collect(),ensure_ascii=False))
    except Exception as error:print(json.dumps({'error':str(error)}));raise SystemExit(1)
