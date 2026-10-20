#!/usr/bin/env python3
"""A self-contained presentation of the generated identity assets."""
from pathlib import Path
import base64
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'packages/linuxbr-branding/files/usr/share'
parts=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1920" height="1540" viewBox="0 0 1920 1540"><rect width="1920" height="1540" fill="#0C1318"/>']
def text(x,y,value,size=24,color='#E9EEF1'):
 parts.append(f'<text x="{x}" y="{y}" font-family="Noto Sans, sans-serif" font-size="{size}" fill="{color}">{value}</text>')
def rect(x,y,w,h,color):
 parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{color}"/>')
def image(path,x,y,w,h):
 data=base64.b64encode(path.read_bytes()).decode()
 mime='image/svg+xml' if path.suffix=='.svg' else 'image/png'
 parts.append(f'<image x="{x}" y="{y}" width="{w}" height="{h}" xlink:href="data:{mime};base64,{data}"/>')
text(72,86,'Linux BR',38)
text(72,130,'Identidade visual • Geometria brasileira, espaço para trabalhar',22,'#A5B1BB')
rect(72,174,862,238,'#F2F4F3'); image(BASE/'linuxbr/identity/wordmark-color.svg',120,204,680,174)
rect(958,174,890,238,'#18232B'); image(BASE/'linuxbr/identity/wordmark-white.svg',1000,204,680,174)
text(72,462,'Sistema de ícones',23)
for i,name in enumerate(['brand','installer','system','files','updates']):
 image(BASE/f'linuxbr/identity/icon-{name}.svg',72+i*146,480,108,108)
for i,(name,color) in enumerate([('Amarelo','#E4DF91'),('Verde','#8EDB91'),('Violeta','#9690D9'),('Grafite','#18232B')]):
 x=958+i*222
 rect(x,484,198,52,color); text(x,564,name,19); text(x,593,color,16,'#A5B1BB')
text(72,658,'Wallpapers 4K • 3840 × 2160 • Fontes vetoriais editáveis',23)
for i,(key,label) in enumerate([('graphite','Grafite — padrão'),('light','Claro'),('forest','Floresta'),('violet','Violeta')]):
 x=72+(i%2)*902; y=690+(i//2)*410
 image(BASE/f'wallpapers/LinuxBR-{key}/contents/images/3840x2160.svg',x,y,874,352)
 text(x,y+382,label,20,'#CBD4DA')
parts.append('</svg>')
(ROOT/'branding/overview.svg').write_text(''.join(parts))
