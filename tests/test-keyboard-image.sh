#!/bin/sh
# Run in a disposable Debian container with console-setup and initramfs-tools.
set -eu
[ -f /run/.containerenv ] || [ -f /.dockerenv ] || {
    echo 'Execute somente em container descartavel.' >&2
    exit 1
}
cd /src
sh config/hooks/live/0200-linuxbr-keyboard.hook.chroot
. /etc/default/keyboard
[ "$XKBLAYOUT" = br ]
[ "$XKBMODEL" = abnt2 ]
keymap=$(mktemp)
trap 'rm -f "$keymap"' EXIT
setupcon --save-keyboard "$keymap"
zgrep -qi ccedilla "$keymap"
echo 'PASS: ABNT2/br e mapa de console com cedilha.'
