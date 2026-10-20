#!/usr/bin/env python3
"""Compare the Qt-rendered logo with the supplied SVG rendered by librsvg."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageChops, ImageStat
from PyQt6.QtWidgets import QApplication
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import Qt

root = Path(__file__).resolve().parents[1]
app = QApplication([])
with tempfile.TemporaryDirectory() as temp:
    temp = Path(temp)
    reference = temp / 'reference.png'
    subprocess.run(['rsvg-convert', '-w', '4000', '-h', '4000', '-o', str(reference), str(root / 'branding/source/reference.svg')], check=True)
    original = Image.open(reference).convert('RGBA')
    expected = Image.new('RGBA', (4000, 4000))
    # Center the 1405-unit visible mark without changing its geometry.
    expected.paste(original.crop((0, 0, 2810, 4000)), (595, 0))
    source = root / 'packages/linuxbr-branding/files/usr/share/linuxbr/identity/symbol-color.svg'
    renderer = QSvgRenderer(str(source))
    assert renderer.isValid()
    canvas = QImage(4000, 4000, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    renderer.render(painter)
    painter.end()
    target = temp / 'qt.png'
    assert canvas.save(str(target))
    actual = Image.open(target).convert('RGBA')
    assert actual.getbbox()[0] >= 594, 'Qt drew the circle outside the original left edge'
    error = max(ImageStat.Stat(ImageChops.difference(expected, actual)).rms)
    assert error < 3, f'Logo differs from original: RMS={error}'
    preview = root / '.cache/logo-qt-corrected.png'
    preview.parent.mkdir(exist_ok=True)
    actual.resize((600, 600), Image.Resampling.LANCZOS).save(preview)
    print(f'PASS: Qt matches original SVG silhouette, color and placement (RMS={error:.3f})')
