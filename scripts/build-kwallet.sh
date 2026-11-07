#!/usr/bin/env bash
# Commit wallet mutations before acknowledging them to applications.
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUTPUT=$(realpath -m "$1")
SOURCE_VERSION=6.13.0-1
LOCAL_VERSION="${SOURCE_VERSION}+linuxbr2"
PATCH="$ROOT/packages/linuxbr-system/patches/kwallet-6.13-sync.patch"
KEY=$( { printf '%s\n' "$SOURCE_VERSION" "$LOCAL_VERSION"; cat "$PATCH" "$ROOT/scripts/build-kwallet.sh"; } | sha256sum)
KEY=${KEY%% *}
CACHE=/src/.cache/kwallet-packages/$KEY
mkdir -p "$OUTPUT"
export_packages() {
    (cd "$CACHE" && sha256sum -c KWALLET-BINARY-SHA256SUMS)
    cp "$CACHE"/*.deb "$OUTPUT/"
    cp "$CACHE/KWALLET-BINARY-SHA256SUMS" "$CACHE/KWALLET-PROVENANCE.txt" "$OUTPUT/"
    mkdir -p "$OUTPUT/kwallet-upstream"
    cp "$CACHE/upstream/"* "$OUTPUT/kwallet-upstream/"
}
if [[ ${LINUXBR_NO_CACHE:-0} != 1 && -f "$CACHE/complete" ]]; then
    echo 'Reutilizando KWallet com gravação persistente Linux BR.'
    export_packages
    exit 0
fi
apt-cache showsrc kf6-kwallet | awk '/^Version:/ { print $2 }' | grep -Fx "$SOURCE_VERSION" >/dev/null || {
    echo "Fonte oficial Debian kf6-kwallet=$SOURCE_VERSION indisponivel" >&2
    exit 1
}
apt-get build-dep -y kf6-kwallet
WORK=$(mktemp -d /src/build/kwallet.XXXXXX)
cd "$WORK"
apt-get source "kf6-kwallet=$SOURCE_VERSION"
SOURCE=$(find . -mindepth 1 -maxdepth 1 -type d -name 'kf6-kwallet-*' -print -quit)
[[ -n "$SOURCE" && -f "$SOURCE/debian/control" ]]
sha256sum ./*.dsc ./*.orig.tar.* ./*.debian.tar.* > KWALLET-SOURCE-SHA256SUMS
patch --batch --forward --fuzz=0 -d "$SOURCE" -p1 < "$PATCH"
cd "$SOURCE"
DEBFULLNAME='Linux BR' DEBEMAIL='build@linuxbr.local' dch --newversion "$LOCAL_VERSION" --distribution trixie \
    'Commit wallet changes before acknowledging mutation requests.'
DEB_BUILD_OPTIONS='nocheck' dpkg-buildpackage -b -uc -us -j2
cd "$WORK"
mkdir -p "$CACHE/upstream"
rm -f "$CACHE/complete"
for name in kwallet6 libkf6wallet-data libkf6wallet6 libkf6walletbackend6; do
    matches=(./"${name}_${LOCAL_VERSION}_"*.deb)
    [[ ${#matches[@]} == 1 && -s "${matches[0]}" ]]
    cp "${matches[0]}" "$CACHE/"
done
cp ./*.dsc ./*.orig.tar.* ./*.debian.tar.* KWALLET-SOURCE-SHA256SUMS "$CACHE/upstream/"
printf 'Source: kf6-kwallet\nDebian-Version: %s\nLocal-Version: %s\nPatch-SHA256: %s\n' \
    "$SOURCE_VERSION" "$LOCAL_VERSION" "$(sha256sum "$PATCH" | cut -d' ' -f1)" > "$CACHE/KWALLET-PROVENANCE.txt"
(cd "$CACHE" && sha256sum ./*.deb > KWALLET-BINARY-SHA256SUMS)
touch "$CACHE/complete"
export_packages
