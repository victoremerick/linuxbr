"""Local, curated store. Actions are fixed argv, never downloaded commands."""
import json
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
import webapps_backend as web

CATALOG = Path('/usr/share/linuxbr/store/catalog.json')
KINDS = {'linux': 'Linux', 'web': 'Aplicativo web', 'windows': 'Windows / Wine'}

# Reviewed local launchers, independent of names, URLs or commands in the catalog.
# All paths are system locations; neither PATH nor downloaded metadata is executed.
NATIVE_LAUNCHERS = {
    'libreoffice': (('/usr/bin/libreoffice',),),
    'okular': (('/usr/bin/okular',),),
    'vlc': (('/usr/bin/vlc',),),
    'gimp': (('/usr/bin/gimp',),),
    'inkscape': (('/usr/bin/inkscape',),),
    'krita': (('/usr/bin/krita',),),
    'kdenlive': (('/usr/bin/kdenlive',),),
    'obs': (('/usr/bin/obs',),),
    'firefox': (('/usr/bin/firefox-esr',), ('/usr/bin/firefox',)),
    'chromium': (('/usr/bin/chromium',),),
    'telegram': (('/usr/bin/telegram-desktop',),),
    'discord': (('/usr/bin/discord',),),
    'slack': (('/usr/bin/slack',),),
    'spotify': (('/usr/bin/spotify',),),
    'steam': (('/usr/games/steam',), ('/usr/bin/steam',)),
    'supertux': (('/usr/games/supertux2',), ('/usr/bin/supertux2',)),
    'ark': (('/usr/bin/ark',),),
    'kate': (('/usr/bin/kate',),),
    'kcalc': (('/usr/bin/kcalc',),),
    'kolourpaint': (('/usr/bin/kolourpaint',),),
    'skanpage': (('/usr/bin/skanpage',),),
    'gwenview': (('/usr/bin/gwenview',),),
    'filelight': (('/usr/bin/filelight',),),
    'kde-connect': (('/usr/bin/kdeconnect-app',), ('/usr/bin/kdeconnect-settings',)),
    'keepassxc': (('/usr/bin/keepassxc',),),
    'filezilla': (('/usr/bin/filezilla',),),
    'thunderbird': (('/usr/bin/thunderbird',),),
    'audacity': (('/usr/bin/audacity',),),
    'transmission': (('/usr/bin/transmission-qt',), ('/usr/bin/transmission-gtk',)),
}

# Package identifiers are reviewed with the application, never taken from a URL.
NATIVE_PACKAGES = {
    'libreoffice':'libreoffice', 'okular':'okular', 'vlc':'vlc', 'gimp':'gimp',
    'inkscape':'inkscape', 'krita':'krita', 'kdenlive':'kdenlive', 'obs':'obs-studio',
    'firefox':'firefox-esr', 'chromium':'chromium', 'telegram':'telegram-desktop',
    'steam':'steam-installer', 'supertux':'supertux', 'ark':'ark', 'kate':'kate',
    'kcalc':'kcalc', 'kolourpaint':'kolourpaint', 'skanpage':'skanpage',
    'gwenview':'gwenview', 'filelight':'filelight', 'kde-connect':'kdeconnect',
    'keepassxc':'keepassxc', 'filezilla':'filezilla', 'thunderbird':'thunderbird',
    'audacity':'audacity', 'transmission':'transmission-qt',
}
FLATPAK_PACKAGES = {
    'libreoffice':'org.libreoffice.LibreOffice', 'okular':'org.kde.okular',
    'vlc':'org.videolan.VLC', 'gimp':'org.gimp.GIMP', 'inkscape':'org.inkscape.Inkscape',
    'krita':'org.kde.krita', 'kdenlive':'org.kde.kdenlive', 'obs':'com.obsproject.Studio',
    'firefox':'org.mozilla.firefox', 'telegram':'org.telegram.desktop',
    'discord':'com.discordapp.Discord', 'slack':'com.slack.Slack',
    'spotify':'com.spotify.Client', 'steam':'com.valvesoftware.Steam',
    'keepassxc':'org.keepassxc.KeePassXC', 'thunderbird':'org.mozilla.Thunderbird',
    'audacity':'org.audacityteam.Audacity',
}


def package_targets(item):
    """Explicit manager, origin and scope choices using observed local records."""
    if not item or item.get('kind')!='linux':return []
    if item.get('optional_target'):
        from store_optional import enabled
        target = item['optional_target']
        return [target] if enabled(target['manager']) else []
    if item.get('provider_hint') == 'snap':
        return []
    result=[]
    package=NATIVE_PACKAGES.get(item.get('id'))
    candidate=item.get('repository_package','')
    if isinstance(candidate,str) and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',candidate):package=candidate
    filename=item.get('desktop_file')
    if filename and not item.get('flatpak_id'):
        for line in query_local(['/usr/bin/dpkg-query','--search','--',filename]).splitlines():
            owner,separator,path=line.partition(': ')
            if separator and path==filename and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',owner):
                package=owner;break
    if package:
        status=query_local(['/usr/bin/dpkg-query','--show','--showformat=${db:Status-Abbrev}',package])
        result.append(dict(manager='deb',target=package,scope='system',origin='Fontes APT configuradas',
            installed=status.startswith('ii'),label='DEB · sistema · '+package+' · fontes APT configuradas'))
    app_id=item.get('flatpak_id') or FLATPAK_PACKAGES.get(item.get('id'))
    if app_id:
        for scope,title in (('user','sua conta'),('system','sistema')):
            records=query_local(['/usr/bin/flatpak','--'+scope,'list','--app','--columns=application,arch,branch,origin'])
            installed=[]
            for line in records.splitlines():
                values=line.split('\t')
                if len(values)==4 and values[0]==app_id:
                    target='/'.join(values[:3]);installed.append(values[3])
                    result.append(dict(manager='flatpak',target=target,scope=scope,origin=values[3],installed=True,
                        label='Flatpak · '+title+' · '+target+' · '+values[3]))
            remotes=query_local(['/usr/bin/flatpak','--'+scope,'remotes','--columns=name,title,url'])
            for line in remotes.splitlines():
                values=line.split('\t')
                if len(values)==3 and values[0] not in installed:
                    result.append(dict(manager='flatpak',target=app_id,scope=scope,origin=values[0],installed=False,
                        label='Flatpak · '+title+' · '+values[0]+' · '+values[2]))
    return result


def native_launch(item):
    """Return a fixed local argv, or None; absence is not proof of no installation."""
    if not item or item.get('kind') != 'linux':
        return None
    target = item.get('optional_target')
    if target and target['manager'] == 'snap':
        from store_optional import snap_launch
        return snap_launch(target)
    for command in NATIVE_LAUNCHERS.get(item.get('id'), ()):
        executable = Path(command[0])
        if executable.is_file() and os.access(executable, os.X_OK):
            return list(command)
    return None


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))


def catalog():
    entries = json.loads(CATALOG.read_text())['apps']
    for service in web.catalog():
        entries.append(dict(id='web:' + service['hosts'][0], name=service['name'],
                            kind='web', category='Internet e comunicação',
                            description='Use o site em uma janela própria do Chromium.',
                            url=service['url'], source=service['source'],
                            note=('Também oferece versão Linux. Confira a opção Linux antes de escolher o site.'
                                  if service['availability'] == 'native' else
                                  'Exige internet. Login, assinatura e recursos dependem do serviço.')))
    return entries


def search(entries, query='', kind='', category=''):
    words = folded(query).split()
    return sorted((item for item in entries
                   if (not kind or item['kind'] == kind)
                   and (not category or item['category'] == category)
                   and all(word in folded(' '.join(str(item.get(key, '')) for key in
                           ('name', 'description', 'category', 'keywords', 'note')))
                           for word in words)), key=lambda item: (folded(item['name']), item['kind']))


def action(item):
    if item['kind'] == 'linux':
        return ['linuxbr-store', '--search', item['name']]
    if item['kind'] == 'web':
        offer=web.normalize_offer(item)
        for key in ('signed_source','signed_app'):
            if key in item:offer[key]=item[key]
        return ['linuxbr-webapps', '--offer', json.dumps(offer, ensure_ascii=False)]
    if item['kind'] == 'windows':
        return ['xdg-open', web.clean_url(item['source'])]
    raise ValueError('Tipo de aplicativo desconhecido.')


def installed_entries(entries):
    result=desktop_applications()
    snap_entries = {item['optional_target']['target']: item for item in entries
                    if item.get('optional_target') and item['optional_target']['manager'] == 'snap'
                    and item['optional_target']['installed']}
    linked_snaps = set()
    for item in result:
        if item.get('provider_hint') == 'snap':
            name = Path(item['desktop_file']).name.split('_', 1)[0]
            if name in snap_entries:
                source = snap_entries[name]
                for field in ('optional_target', 'version', 'publisher', 'source', 'note', 'keywords'):
                    item[field] = source[field]
                linked_snaps.add(name)
    # Desktop entries can share an executable but select different components
    # through arguments (Writer, Calc, Impress). Preserve every visible entry.
    known={item.pop('_executable',None) for item in result}
    for item in entries:
        if item.get('optional_target'):
            from store_optional import enabled
            target = item['optional_target']
            if (target['installed'] and enabled(target['manager']) and
                    not (target['manager'] == 'snap' and target['target'] in linked_snaps)):
                result.append(dict(item, local=True))
            continue
        command=native_launch(item)
        if command and str(Path(command[0]).resolve()) not in known:
            result.append(dict(item,local=True))
    for item in web.installed():
        result.append(dict(id='profile:'+item['id'],name=web.display_name(item),
            kind='web',category='Internet e comunicação',description='Perfil web salvo neste computador.',
            url=item['url'],source=item['url'],profile_id=item['id'],local=True,
            note='Os dados e o login pertencem a este perfil. Remover do menu preserva os dados.'))
    from windows_runner import programs, read_environment, program_icon
    for item in programs():
        result.append(dict(id='program:'+item['id'],name=item['name'],kind='windows',
            category='Programas Windows',description='Ambiente: '+read_environment(item['environment'])['name'],
            source='https://www.winehq.org/',program_id=item['id'],local=True,icon=program_icon(item['id']),
            note='Atalho salvo. Para desinstalar o programa, abra Programas Windows e jogos no ambiente correspondente.'))
    return result


def desktop_applications():
    """Use the desktop's application registry, including exported Flatpak entries."""
    try:
        from gi.repository import Gio
        applications=Gio.AppInfo.get_all()
    except (ImportError,ValueError):return []
    result=[];seen=set()
    for app in applications:
        identifier=app.get_id()
        if not identifier or identifier in seen or not app.should_show():continue
        if identifier.startswith(('linuxbr-webapp-','linuxbr-windows-')):continue
        filename=app.get_filename() if hasattr(app,'get_filename') else None
        if not filename or not Path(filename).is_file():continue
        seen.add(identifier)
        executable=app.get_executable() or ''
        result.append(dict(id='desktop:'+identifier,desktop_id=identifier,name=app.get_display_name(),
            kind='linux',category='Aplicativos instalados',description=app.get_description() or 'Aplicativo deste computador.',
            source='Registro de aplicativos deste computador',local=True,
            desktop_file=filename,provider_hint='snap' if Path(filename).parent == Path('/var/lib/snapd/desktop/applications') else '',
            flatpak_id=app.get_string('X-Flatpak') if hasattr(app,'get_string') else None,
            icon=app.get_string('Icon') if hasattr(app,'get_string') else None,
            _executable=str(Path(shutil.which(executable) or executable).resolve()),
            note='Inclui aplicativos registrados pelo sistema e pelo Flatpak. Escolha a origem e o alcance para gerenciar a instalação.'))
    return result


def query_local(argv):
    """Read local package metadata without network access or package changes."""
    try:
        result=subprocess.run(argv,capture_output=True,text=True,timeout=3,
            env={**os.environ,'LC_ALL':'C'},check=False)
        return result.stdout.strip() if result.returncode==0 else ''
    except (OSError,subprocess.TimeoutExpired):return ''


def package_metadata(item):
    """Report observed metadata; never guess a version or a download size."""
    kind=item['kind']
    result={'type':KINDS[kind],'origin':item.get('source','Não informada'),
            'version':'Não informada; consulte o fornecedor ou a origem da instalação.',
            'size':'Não informado; confira antes de instalar.',
            'publisher':'Não informado nos metadados locais.','license':'Consulte a licença fornecida pelo aplicativo.'}
    if item.get('optional_target'):
        target = item['optional_target']
        result.update(type='Snap' if target['manager'] == 'snap' else 'Fórmula Homebrew',
                      origin=target['label'], version=item['version'],
                      publisher=item['publisher'] or 'Não informado pela fonte.')
        return result
    if item.get('provider_hint') == 'snap':
        result.update(type='Snap', origin='Snap instalado. Habilite a fonte para gerenciar pela Loja.')
        return result
    if kind=='web':
        result.update(version='Serviço online; atualizado pelo fornecedor.',
            size='Variável: dados de cada perfil e cache; Chromium compartilhado.',license='Termos do serviço disponíveis no site oficial.')
        return result
    if kind=='windows':
        result['version']='Consulte Sobre / Ajuda no próprio programa.'
        if item.get('recipe_id'):
            try:
                from windows_recipes import recipe
                from compatibility_records import assessment
                entry=recipe(item['recipe_id']);result['compatibility']=assessment(entry)['label']
                result['version']=entry['application_version']+' (receita; confira a versão do instalador)'
            except (OSError,ValueError,KeyError):
                result['compatibility']='Registro de compatibilidade indisponível.'
        if item.get('program_id'):
            from windows_runner import read_program
            try:
                program=read_program(item['program_id']);path=Path(program['file'])
                result['origin']='EXE local escolhido pelo usuário; ambiente Wine separado.'
                result['size']=format_size(path.stat().st_size)+' (somente o EXE; ambiente e dados adicionais).'
            except (OSError,ValueError):result['size']='EXE não encontrado; revise o atalho.'
        return result
    flatpak=item.get('flatpak_id')
    if flatpak:
        # Flatpak prints tab-separated columns on a pipe. Include the installation
        # so a user installation is not silently confused with a system one.
        records=query_local(['/usr/bin/flatpak','list','--app',
            '--columns=application,version,size,origin,installation'])
        matches=[line.split('\t') for line in records.splitlines() if line.split('\t')[0]==flatpak]
        if matches:
            versions=[];sizes=[];origins=[]
            for row in matches:
                if len(row)!=5:continue
                versions.append(row[1] or 'Não informada');sizes.append(row[2] or 'Não informado')
                origins.append((row[3] or 'Origem não informada')+' ('+row[4]+')')
            if versions:
                result.update(type='Linux / Flatpak',version='; '.join(versions),
                    size='; '.join(sizes)+' (instalação; runtimes podem ser compartilhados).',
                    origin='; '.join(origins))
                return result
        result.update(type='Linux / Flatpak',origin='Registro Flatpak local; detalhes indisponíveis.')
        return result
    filename=item.get('desktop_file')
    if filename:
        # The owner may contain :amd64. Split only on the separator before the path.
        owners=query_local(['/usr/bin/dpkg-query','--search','--',filename])
        for line in owners.splitlines():
            package,separator,owner_path=line.partition(': ')
            if not separator or owner_path!=filename or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',package):continue
            value=query_local(['/usr/bin/dpkg-query','--show',
                '--showformat=${db:Status-Abbrev}\t${Version}\t${Installed-Size}',package]).split('\t')
            if len(value)==3 and value[0].startswith('ii') and value[2].isdigit():
                result.update(type='Linux / pacote DEB',version=value[1],
                    origin='Pacote instalado: '+package+'; fontes APT configuradas, gerenciamento na Loja.',
                    size=format_size(int(value[2])*1024)+' (pacote; bibliotecas e dados adicionais).')
                return result
        result['origin']='Registro local; pacote de origem não identificado.'
    package=item.get('repository_package') or NATIVE_PACKAGES.get(item.get('id'))
    if package and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',package):
        raw=query_local(['/usr/bin/apt-cache','show','--no-all-versions',package]);fields={}
        for line in raw.splitlines():
            key,separator,value=line.partition(': ')
            if separator and not line.startswith(' '):fields[key]=value
        result.update(type='Linux / pacote DEB',origin='Fontes APT configuradas',version=fields.get('Version','Não informada'))
        if fields.get('Size','').isdigit():result['size']=format_size(int(fields['Size']))+' (download; dependências adicionais serão apresentadas).'
        result['publisher']=fields.get('Maintainer','Mantenedor não informado nos índices locais.')
        copyright=Path('/usr/share/doc')/package.split(':')[0]/'copyright'
        if copyright.is_file():result.update(license='Licenças detalhadas no arquivo copyright do pacote.',copyright_file=str(copyright))
    return result


def format_size(value):
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if value<1024 or unit=='TiB':return f'{value:.1f} {unit}'
        value/=1024


def manage_action(item):
    if item['kind']=='linux':return action(item)
    if item.get('program_id'):
        from windows_runner import read_program
        read_program(item['program_id'])
        return ['linuxbr-windows','--program',item['program_id']]
    return None


def local_action(item):
    if not item:return None
    if item.get('desktop_id'):
        from gi.repository import Gio
        try:
            app = Gio.DesktopAppInfo.new(item['desktop_id'])
        except TypeError:
            # PyGObject raises when the launcher disappears during package removal.
            app = None
        if not app or not app.should_show():raise ValueError('Este aplicativo não está mais disponível.')
        return ['/usr/bin/gio','launch',app.get_filename()]
    if item.get('profile_id'):return ['linuxbr-webapps','--launch',web.checked_id(item['profile_id'])]
    if item.get('program_id'):
        from windows_runner import read_program
        read_program(item['program_id'])
        return ['linuxbr-windows','--launch',item['program_id']]
    return native_launch(item)
