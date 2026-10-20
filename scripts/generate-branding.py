#!/usr/bin/env python3
"""Generate editable vector artwork from the user-supplied Linux BR geometry.
Run from the repository; rendering PNGs is a separate, deterministic rsvg step.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'packages/linuxbr-branding/files/usr/share'
ART = BASE / 'linuxbr/identity'
ICON = BASE / 'icons/hicolor/scalable/apps'
WALL = BASE / 'wallpapers'

def svg(body, w, h):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>\n'

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)

reference = ET.parse(ROOT / 'branding/source/reference.svg').getroot()
# Preserve the source silhouette, including the half circle clipped at x=0.
def mark(name, mono=None):
    shapes = []
    for index,item in enumerate(reference):
        tag = item.tag.split('}')[-1]
        attrs = dict(item.attrib)
        if mono:
            attrs['fill'] = '#000000' if index == 3 else '#FFFFFF'
            if 'stroke' in attrs:
                attrs['stroke'] = '#000000'
        if tag == 'circle':
            # Qt SVG does not reliably honor clipPath. Express the exact visible
            # half of the source circle directly, without a stroke on the cut.
            shapes.append(f'<path d="M0 338 A668 668 0 0 1 0 1674 Z" fill="{attrs["fill"]}"/>')
            shapes.append(f'<path d="M0 338 A668 668 0 0 1 0 1674" fill="none" stroke="{attrs["stroke"]}" stroke-width="20"/>')
        else:
            shapes.append('<' + tag + ' ' + ' '.join(f'{k}="{v}"' for k,v in attrs.items()) + '/>')
    if mono:
        shapes = [f'<defs><mask id="{name}-mask" x="0" y="0" width="1405" height="2000" maskUnits="userSpaceOnUse">' + ''.join(shapes) + f'</mask></defs><rect width="1405" height="2000" fill="{mono}" mask="url(#{name}-mask)"/>']
    return ''.join(shapes)

def symbol(mono=None, name='symbol'):
    return '<g transform="translate(297.5 0)">'+mark(name, mono)+'</g>'

for name, color in [('color',None),('white','#FFFFFF'),('graphite','#18232B')]:
    save(ART/f'symbol-{name}.svg', svg(symbol(color, name),2000,2000))
    label = '#18232B' if name in ['color','graphite'] else '#F3F5F7'
    body = '<g transform="translate(20 24) scale(.1)">'+mark('wordmark-'+name,color)+'</g>'
    body += f'<text x="196" y="160" fill="{label}" font-family="Noto Sans, sans-serif" font-size="100" font-weight="500" letter-spacing="-3">Linux <tspan font-weight="700">BR</tspan></text>'
    save(ART/f'wordmark-{name}.svg', svg(body,680,248))

# Application icons: a shared neutral tile, with distinct action glyphs.
tile = '<rect x="8" y="8" width="240" height="240" rx="12" fill="#18232B"/><rect x="8.5" y="8.5" width="239" height="239" rx="11.5" fill="none" stroke="#FFFFFF" stroke-opacity=".08"/>'
brand = tile+'<g transform="translate(65 34) scale(.09)">'+mark('app-brand')+'</g>'
save(ICON/'linuxbr.svg',svg(brand,256,256))
save(ART/'icon-brand.svg',svg(brand,256,256))
glyphs = {
 'installer': ('#8EDB91','<path d="M128 63v91m-31-30 31 31 31-31M69 166v27h118v-27"/>'),
 'system': ('#9690D9','<rect x="62" y="69" width="132" height="94" rx="3"/><path d="M102 193h52m-26-30v30M85 112h86m-68-18v36m46-36v36"/>'),
 'files': ('#E4DF91','<path d="M61 91V78q0-9 9-9h41l18 20h57q9 0 9 9v80q0 9-9 9H70q-9 0-9-9Z"/><path d="M61 108h134"/>'),
 'updates': ('#8EDB91','<path d="M76 101a58 58 0 0 1 104-10l13 22m0-39v39h-39M180 155a58 58 0 0 1-104 10l-13-22m0 39v-39h39"/>'),
}
for name,(color,paths) in glyphs.items():
    body=tile+f'<g fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round">{paths}</g>'
    save(ICON/f'linuxbr-{name}.svg',svg(body,256,256))
    save(ART/f'icon-{name}.svg',svg(body,256,256))
save(BASE/'icons/hicolor/symbolic/apps/linuxbr-symbolic.svg', svg(symbol('#232629','symbolic'),2000,2000))

# Restrained, related compositions. Keep the left desktop area quiet.
variants = {
 'graphite': ('Grafite', '#10191F','#1B2832','#E4DF91','#8EDB91','#9690D9'),
 'light': ('Claro', '#F2F4F3','#E5E9E8','#B4AB65','#559C73','#7973AC'),
 'forest': ('Floresta', '#0D211F','#193834','#E4DF91','#8EDB91','#9690D9'),
 'violet': ('Violeta', '#191925','#2B2C42','#E4DF91','#8EDB91','#9690D9'),
}
for key,(name,bg,edge,yellow,green,purple) in variants.items():
    # Solid architectural planes: quiet workspace, crisp edges, no gradients.
    body=f'''<rect width="3840" height="2160" fill="{bg}"/>
<path d="M2560 0H3840V2160H3320L2320 1160Z" fill="{edge}"/>
<path d="M3320 2160L2320 1160L2360 1120L3360 2160Z" fill="{purple}" fill-opacity=".12"/>
<g transform="translate(1856.775 990) scale(.09)">{mark('wall-'+key)}</g>'''
    directory=WALL/f'LinuxBR-{key}'
    save(directory/'contents/images/3840x2160.svg',svg(body,3840,2160))
    save(directory/'metadata.json',json.dumps({'KPlugin':{'Id':f'LinuxBR-{key}','Name':f'Linux BR — {name}','Authors':[{'Name':'Projeto Linux BR'}]}},ensure_ascii=False,indent=2)+'\n')
    save(directory/'CREDITS.txt','Arte vetorial derivada do SVG fornecido pelo usuário para a identidade Linux BR.\nRenderização direta em 3840×2160; sem ampliação e sem fotografia externa.\nFonte editável: contents/images/3840x2160.svg.\n')
save(BASE/'linuxbr/wallpaper.svg', (WALL/'LinuxBR-graphite/contents/images/3840x2160.svg').read_text())
print('SVGs, ícones e quatro wallpapers vetoriais gerados.')
