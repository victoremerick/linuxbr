#!/usr/bin/env python3
"""Generate original flat Aurorae assets, following KDE's SVG theme format."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'packages/linuxbr-desktop/files/usr/share/aurorae/themes'
for mode,bg,fg,hover in [('Light','#e8ebef','#1e252c','#d6dbe2'),('Dark','#242b33','#edf0f4','#3b4552')]:
    name='LinuxBRClean-'+mode; out=ROOT/name;out.mkdir(parents=True,exist_ok=True)
    (out/'metadata.desktop').write_text('[Desktop Entry]\nName=Linux BR Clean '+mode+'\nX-KDE-PluginInfo-Name='+name+'\nX-KDE-PluginInfo-Author=Linux BR\nX-KDE-PluginInfo-Version=1\nX-KDE-PluginInfo-License=GPL-3.0-or-later\n')
    (out/(name+'rc')).write_text(f'''[General]
TitleAlignment=Left
ActiveTextColor={','.join(str(int(fg[i:i+2],16)) for i in (1,3,5))},255
InactiveTextColor=128,136,145,255
UseTextShadow=false
Shadow=false
LeftButtons=M
RightButtons=IAX
Animation=80
[Layout]
BorderLeft=1
BorderRight=1
BorderBottom=1
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft=0
TitleEdgeRight=0
TitleBorderLeft=8
TitleBorderRight=8
TitleHeight=32
ButtonHeight=32
ButtonWidth=44
ButtonWidthMenu=32
ButtonSpacing=0
''')
    parts=[]
    for prefix in ('decoration','decoration-inactive'):
        for part,x,y,w,h in [('center',1,1,30,30),('top',1,0,30,1),('bottom',1,31,30,1),('left',0,1,1,30),('right',31,1,1,30),('topleft',0,0,1,1),('topright',31,0,1,1),('bottomleft',0,31,1,1),('bottomright',31,31,1,1)]:
            parts.append(f'<rect id="{prefix}-{part}" x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}"/>')
    (out/'decoration.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'+''.join(parts)+'</svg>')
    shapes={'minimize':'M17 17H27','maximize':'M17 11H27V21H17Z','restore':'M19 11H28V20M16 14H25V23H16Z','close':'M17 11L27 21M27 11L17 21'}
    for button,path in shapes.items():
        groups=[]
        for index,state in enumerate(('active','inactive','hover','hover-inactive','pressed','pressed-inactive','deactivated','deactivated-inactive')):
            colored=state.startswith(('hover','pressed'));fill=('#c42b32' if button=='close' else hover) if colored else bg
            stroke='#ffffff' if button=='close' and colored else fg
            groups.append(f'<g id="{state}-center" transform="translate(0,{index*32})"><rect width="44" height="32" fill="{fill}"/><path d="{path}" stroke="{stroke}" stroke-width="1.2" fill="none"/></g>')
        (out/(button+'.svg')).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="256">'+''.join(groups)+'</svg>')
