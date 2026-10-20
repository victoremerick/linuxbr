#!/usr/bin/env bash
# Disposable Debian container only: installs a test kernel and builds its initramfs.
set -Eeuo pipefail
[[ -f /run/.containerenv || -f /.dockerenv ]] || exit 1
cd /src
export DEBIAN_FRONTEND=noninteractive
# This container tests theme inclusion, not hardware drivers or booting its kernel.
mkdir -p /etc/initramfs-tools/conf.d
printf 'MODULES=list\nCOMPRESS=gzip\n' > /etc/initramfs-tools/conf.d/linuxbr-smoke
apt-get update -qq
apt-get install -y -qq --no-install-recommends python3 python3-yaml python3-pil librsvg2-bin cmake build-essential dpkg-dev qt6-base-dev libkf6kio-dev libkf6bookmarks-dev live-build plymouth plymouth-themes plymouth-x11 xvfb xauth x11-apps linux-image-amd64 grub-common > /tmp/boot-dependencies.log 2>&1
work=$(mktemp -d /src/.cache/boot-test.XXXXXX)
mkdir -p "$work/upstream"
(cd "$work/upstream" && apt-get download calamares-settings-debian=13.0.13-1 sddm-theme-breeze)
python3 scripts/build-packages.py --output "$work/debs" --work "$work/packages" \
 --calamares-deb "$work"/upstream/calamares-settings-debian_*.deb \
 --breeze-deb "$work"/upstream/sddm-theme-breeze_*.deb
python3 scripts/prepare-live-boot.py "$work"
grep -q 'linuxbr-theme/theme.txt' "$work/config/bootloaders/grub-pc/theme.cfg"
# No generated boot entry templates are replaced.
test ! -e "$work/config/bootloaders/grub-pc/grub.cfg"
test ! -e "$work/config/bootloaders/syslinux_common/live.cfg"
previous=$(plymouth-set-default-theme)
dpkg -i "$work"/debs/linuxbr-boot-theme_*.deb
[[ $(plymouth-set-default-theme) == linuxbr ]]
initrd=$(find /boot -maxdepth 1 -name 'initrd.img-*' | head -1)
lsinitramfs "$initrd" > "$work/initramfs-files.txt"
grep -q 'usr/share/plymouth/themes/linuxbr/linuxbr.script' "$work/initramfs-files.txt"
grep -q 'usr/share/plymouth/themes/linuxbr/logo.png' "$work/initramfs-files.txt"
grep -q '/plymouth/script.so' "$work/initramfs-files.txt"
# Exercise actual Plymouth script rendering and prompt callbacks using an X11 renderer.
Xvfb :99 -screen 0 1280x720x24 > "$work/xvfb.log" 2>&1 &
xvfb_pid=$!
export DISPLAY=:99
sleep 1
plymouthd --debug --debug-file="$work/plymouth.log" --kernel-command-line='splash plymouth.ignore-serial-consoles' --mode=boot
plymouth show-splash
sleep 2
plymouth display-message --text='MENSAGEM DE ROTINA NAO DEVE APARECER'
xwd -root -silent -out "$work/loading-1.xwd"
sleep 0.3
xwd -root -silent -out "$work/loading-2.xwd"
plymouth ask-for-password --prompt='Senha do disco de teste:' > /dev/null &
sleep 1
xwd -root -silent -out "$work/password.xwd"
plymouth quit
kill "$xvfb_pid"
wait || true
grep -q 'executing script file' "$work/plymouth.log"
if grep -Ei 'parse error|syntax error|script.*error' "$work/plymouth.log"; then exit 1; fi
dpkg -i "$work"/debs/linuxbr-boot-theme_*.deb
[[ $(plymouth-set-default-theme) == linuxbr ]]
plymouth-set-default-theme text
dpkg -i "$work"/debs/linuxbr-boot-theme_*.deb
[[ $(plymouth-set-default-theme) == text ]]
plymouth-set-default-theme linuxbr
dpkg --remove linuxbr-boot-theme
[[ $(plymouth-set-default-theme) == "$previous" ]]
dpkg --purge linuxbr-boot-theme
printf 'PASS: boot assets, real initramfs, Plymouth rendering, reinstall and removal. Artifacts: %s\n' "$work"
