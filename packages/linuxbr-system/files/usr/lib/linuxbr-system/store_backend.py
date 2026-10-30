"""Local, curated store. Actions are fixed argv, never downloaded commands."""
import json
import os
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


def native_launch(item):
    """Return a fixed local argv, or None; absence is not proof of no installation."""
    if not item or item.get('kind') != 'linux':
        return None
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
        # Discover retains its package source, authorization and confirmation UI.
        return ['plasma-discover', '--search', item['name']]
    if item['kind'] == 'web':
        return ['linuxbr-webapps', '--offer', json.dumps(web.normalize_offer(item), ensure_ascii=False)]
    if item['kind'] == 'windows':
        return ['xdg-open', web.clean_url(item['source'])]
    raise ValueError('Tipo de aplicativo desconhecido.')
