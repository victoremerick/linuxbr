#!/usr/bin/env bash
# Requires librsvg2-bin and fonts-noto-core; suitable for a disposable Debian container.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
base=packages/linuxbr-branding/files/usr/share
for name in graphite light forest violet; do
    image="$base/wallpapers/LinuxBR-$name/contents/images/3840x2160"
    rsvg-convert -o "$image.png" "$image.svg"
done
for icon in "$base"/icons/hicolor/scalable/apps/linuxbr*.svg; do
    name=$(basename "$icon" .svg)
    for size in 16 22 24 32 48 64 128 256 512; do
        mkdir -p "$base/icons/hicolor/${size}x${size}/apps"
        rsvg-convert -w "$size" -h "$size" -o "$base/icons/hicolor/${size}x${size}/apps/$name.png" "$icon"
    done
done
for logo in "$base"/linuxbr/identity/*.svg; do
    rsvg-convert -w 1000 -o "${logo%.svg}.png" "$logo"
done
