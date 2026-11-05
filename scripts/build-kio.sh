#!/usr/bin/env bash
# Run only inside the Debian builder. Keep the native dialog's apply sequence.
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUTPUT=$(realpath -m "$1")
SOURCE_VERSION=${LINUXBR_KIO_SOURCE_VERSION:-6.13.0-6}
[[ "$SOURCE_VERSION" =~ ^6\.13\.0-[0-9]+$ ]] || { echo 'Fonte KIO fora da base 6.13.0' >&2; exit 1; }
apt-cache showsrc kf6-kio | awk '/^Version:/ { print $2 }' | grep -Fx "$SOURCE_VERSION" >/dev/null || {
    echo "Fonte oficial Debian kf6-kio=$SOURCE_VERSION indisponivel" >&2
    exit 1
}
LOCAL_VERSION="${SOURCE_VERSION}+linuxbr0.9.1"
PATCH="$ROOT/packages/linuxbr-file-properties/patches/kio-6.13-apply.patch"
KEY=$( { printf '%s\n' "$SOURCE_VERSION" "$LOCAL_VERSION"; cat "$PATCH" "$ROOT/scripts/build-kio.sh"; } | sha256sum)
KEY=${KEY%% *}
CACHE=/src/.cache/kio-properties-packages/$KEY
mkdir -p "$OUTPUT"
if [[ ${LINUXBR_NO_CACHE:-0} != 1 && -f "$CACHE/complete" ]]; then
    echo 'Reutilizando KIO com propriedades Linux BR.'
    cp "$CACHE"/*.deb "$OUTPUT/"
    cp "$CACHE/KIO-SOURCE-SHA256SUMS" "$OUTPUT/"
    cp "$CACHE/KIO-BINARY-SHA256SUMS" "$OUTPUT/"
    cp "$CACHE/KIO-PROVENANCE.txt" "$OUTPUT/"
    exit 0
fi
mkdir -p /src/build
WORK=$(mktemp -d /src/build/kio-properties.XXXXXX)
cd "$WORK"
apt-get source "kf6-kio=$SOURCE_VERSION"
SOURCE=$(find . -mindepth 1 -maxdepth 1 -type d -name 'kio-*' -print -quit)
if [[ -z "$SOURCE" ]]; then
    SOURCE=$(find . -mindepth 1 -maxdepth 1 -type d -name 'kf6-kio-*' -print -quit)
fi
[[ -n "$SOURCE" && -f "$SOURCE/debian/control" ]]
sha256sum ./*.dsc ./*.orig.tar.* ./*.debian.tar.* > KIO-SOURCE-SHA256SUMS
patch --batch --forward --fuzz=0 -d "$SOURCE" -p1 < "$PATCH"
cd "$SOURCE"
# Register the single added public slot while retaining every existing symbol.
python3 - "$LOCAL_VERSION" <<'PY'
from pathlib import Path
import sys
path = Path('debian/libkf6kiowidgets6.symbols')
text = path.read_text()
symbol = ' _ZN17KPropertiesDialog5applyEv@Base ' + sys.argv[1]
if '_ZN17KPropertiesDialog5applyEv@Base' not in text:
    lines = text.splitlines()
    candidates = [index for index, line in enumerate(lines) if line.startswith(' _ZN17KPropertiesDialog')]
    if not candidates:
        raise SystemExit('Tabela de simbolos KPropertiesDialog nao encontrada')
    insertion = next((index for index in candidates if lines[index].split('@', 1)[0] > symbol.split('@', 1)[0]), candidates[-1] + 1)
    lines.insert(insertion, symbol)
    path.write_text('\n'.join(lines) + '\n')
PY
DEBFULLNAME='Linux BR' DEBEMAIL='build@linuxbr.local' dch --newversion "$LOCAL_VERSION" --distribution trixie \
    'Expose Apply in native properties while preserving asynchronous KIO changes.'
DEB_BUILD_OPTIONS='nocheck' dpkg-buildpackage -b -uc -us -j2
cd "$WORK"
mkdir -p "$CACHE"
rm -f "$CACHE/complete"
for name in kio6 libkf6kiocore6 libkf6kiogui6 libkf6kiowidgets6 libkf6kiofilewidgets6; do
    matches=(./"${name}_${LOCAL_VERSION}_"*.deb)
    [[ ${#matches[@]} == 1 && -s "${matches[0]}" ]]
    cp "${matches[0]}" "$CACHE/"
done
cp KIO-SOURCE-SHA256SUMS "$CACHE/"
printf 'Source: kf6-kio\nDebian-Version: %s\nLocal-Version: %s\nPatch-SHA256: %s\n' \
    "$SOURCE_VERSION" "$LOCAL_VERSION" "$(sha256sum "$PATCH" | cut -d' ' -f1)" > "$CACHE/KIO-PROVENANCE.txt"
(cd "$CACHE" && sha256sum ./*.deb > KIO-BINARY-SHA256SUMS)
touch "$CACHE/complete"
cp "$CACHE"/*.deb "$OUTPUT/"
cp "$CACHE/KIO-SOURCE-SHA256SUMS" "$CACHE/KIO-BINARY-SHA256SUMS" "$CACHE/KIO-PROVENANCE.txt" "$OUTPUT/"
