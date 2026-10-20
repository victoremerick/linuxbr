#!/usr/bin/env python3
"""Finite SVG set used by Dolphin's native KIO icon renderer (0..100%)."""
from pathlib import Path
import sys


def generate(root):
    root.mkdir(parents=True, exist_ok=True)
    for kind in ('disk', 'usb'):
        for percent in range(101):
            color = '#c74b50' if percent >= 90 else '#5689bc'
            device = ('<rect x="23" y="18" width="82" height="60" rx="8" fill="#bac7d1" stroke="#506477" stroke-width="3"/><path d="M28 60h72" stroke="#506477" stroke-width="3"/><circle cx="91" cy="69" r="3" fill="#468356"/>' if kind == 'disk' else
                      '<rect x="48" y="7" width="32" height="20" rx="2" fill="#bac7d1" stroke="#506477" stroke-width="3"/><rect x="40" y="27" width="48" height="52" rx="7" fill="#7c98b0" stroke="#506477" stroke-width="3"/><path d="M58 12v9m12-9v9" stroke="#506477" stroke-width="4"/>')
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<title>Espaço usado: {percent}%</title>
{device}
<rect x="4" y="93" width="120" height="20" rx="4" fill="#e0e6eb" stroke="#506477" stroke-width="2"/>
<rect x="6" y="95" width="{116*percent/100:.2f}" height="16" fill="{color}"/>
</svg>'''
            (root/f'{kind}-{percent:03d}.svg').write_text(svg)

if __name__ == '__main__': generate(Path(sys.argv[1]))
