"""Verify capacity fills in Qt's actual SVG renderer, not just XML syntax."""
import importlib.util
from pathlib import Path
import tempfile
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication
app=QApplication([])
source=Path(__file__).resolve().parents[1]/'scripts/generate-drive-capacity-icons.py'
spec=importlib.util.spec_from_file_location('icons',source)
icons=importlib.util.module_from_spec(spec);spec.loader.exec_module(icons)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);icons.generate(root)
    for percent,color in ((0,'#e0e6eb'),(50,'#5689bc'),(95,'#c74b50')):
        image=QImage(128,128,QImage.Format.Format_ARGB32);image.fill(0)
        renderer=QSvgRenderer(str(root/f'disk-{percent:03d}.svg'))
        assert renderer.isValid()
        painter=QPainter(image);renderer.render(painter);painter.end()
        assert image.pixelColor(30,103).name()==color
        if percent==50:assert image.pixelColor(100,103).name()=='#e0e6eb'
print('PASS: Qt renders used/free fills and low-space colour')
