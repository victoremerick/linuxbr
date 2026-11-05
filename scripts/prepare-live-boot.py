#!/usr/bin/env python3
"""Add Linux BR artwork without replacing live-build's generated boot entries."""
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageOps


def prepare(work, templates=Path('/usr/share/live/build/bootloaders')):
    theme = work / 'packages/linuxbr-boot-theme/boot/grub/themes/linuxbr'
    grub = work / 'config/bootloaders/grub-pc'
    grub.mkdir(parents=True, exist_ok=True)
    shutil.copytree(theme, grub / 'linuxbr-theme', dirs_exist_ok=True)
    (grub / 'theme.cfg').write_text('''set color_normal=white/black
set color_highlight=yellow/black
if [ -e /boot/grub/linuxbr-theme/theme.txt ]; then
    insmod gfxmenu
    set theme=/boot/grub/linuxbr-theme/theme.txt
    export theme
fi
''')
    config = (templates / 'grub-pc/config.cfg').read_text()
    if 'set gfxmode=800x600' not in config:
        raise SystemExit('Revisar template GRUB do live-build: gfxmode mudou')
    (grub / 'config.cfg').write_text(config.replace('set gfxmode=800x600', 'set gfxmode=auto'))
    syslinux = work / 'config/bootloaders/syslinux_common'
    syslinux.mkdir(parents=True, exist_ok=True)
    # ISOLINUX uses a 640x480 image; letterbox rather than distort the penguin.
    with Image.open(theme / 'background.png') as image:
        ImageOps.pad(image.convert('RGB'), (640, 480), color='#10191f').save(syslinux / 'splash.png')
    menu = (templates / 'syslinux_common/menu.cfg').read_text()
    (syslinux / 'menu.cfg').write_text(menu.replace('menu title Boot menu', 'menu title Linux BR'))
    stdmenu = (templates / 'syslinux_common/stdmenu.cfg').read_text()
    stdmenu = stdmenu.replace('#76a1d0ff', '#ff34443e').replace('#ffdddd00', '#ffe4df91')
    (syslinux / 'stdmenu.cfg').write_text(stdmenu)


if __name__ == '__main__':
    prepare(Path(sys.argv[1]))
