#!/usr/bin/env bash
# Called inside the Debian builder after apt-get update. Cache by source+patch.
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUTPUT=$(realpath -m "$1")
VERSION=''
while read -r candidate; do
    if [[ -z "$VERSION" ]] || dpkg --compare-versions "$candidate" gt "$VERSION"; then
        VERSION=$candidate
    fi
done < <(apt-cache showsrc dolphin | awk '/^Version:/ {print $2}')
[[ -n "$VERSION" ]] || { echo 'Fonte Debian do Dolphin indisponivel' >&2; exit 1; }
KEY=$( { printf '%s\n' "$VERSION"; cat "$ROOT/scripts/patch-dolphin.py" "$ROOT/packages/linuxbr-dolphin/cards.cpp.inc" "$ROOT/packages/linuxbr-dolphin/sidebar.h" "$ROOT/packages/linuxbr-dolphin/sidebar-state.h" "$ROOT/scripts/build-dolphin.sh"; } | sha256sum)
KEY=${KEY%% *}
CACHE=/src/.cache/dolphin-packages/$KEY
mkdir -p "$OUTPUT"
if [[ ${LINUXBR_NO_CACHE:-0} != 1 && -f "$CACHE/complete" ]]; then
    echo 'Reutilizando Dolphin com cartoes Linux BR.'
    cp "$CACHE"/*.deb "$OUTPUT/"
    exit 0
fi
WORK=$(mktemp -d /src/build/dolphin-cards.XXXXXX)
cd "$WORK"
apt-get source "dolphin=$VERSION"
SOURCE=$(find . -mindepth 1 -maxdepth 1 -type d -name 'dolphin-*' -print -quit)
[[ -n "$SOURCE" ]]
python3 "$ROOT/scripts/patch-dolphin.py" "$SOURCE"
cd "$SOURCE"
DEBFULLNAME='Linux BR' DEBEMAIL='build@linuxbr.local' dch --local '+linuxbr' --distribution trixie 'Drive cards for linuxbr:/; preserve normal Dolphin views.'
DEB_BUILD_OPTIONS='nocheck' dpkg-buildpackage -b -uc -us -j2
cd "$WORK"
# Publish the matching runtime/data/library packages together; exclude symbols.
mkdir -p "$CACHE"
rm -f "$CACHE/complete"
for package in ./dolphin_[0-9]*.deb ./dolphin-data_*.deb ./libdolphinvcs6_*.deb; do
    cp "$package" "$CACHE/"
done
touch "$CACHE/complete"
cp "$CACHE"/*.deb "$OUTPUT/"
