#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
VERSION=$(cat VERSION)
ISO="${ISO:-dist/linuxbr-${VERSION}-amd64.iso}"
[[ -s "$ISO" ]] || { echo "ISO nao encontrada: $ISO" >&2; exit 1; }
ISO=$(realpath "$ISO")
checksum="${CHECKSUM_FILE:-$ISO.sha256}"
[[ -f "$checksum" ]] || checksum="$(dirname "$ISO")/SHA256SUMS"
checksum=$(realpath "$checksum")
# Require an entry for this exact ISO; do not verify a different release.
entry=$(awk -v name="$(basename "$ISO")" '$2 == name || $2 == "*" name' "$checksum")
[[ $(printf '%s\n' "$entry" | wc -l) == 1 && -n "$entry" ]] || { echo 'Checksum ausente ou ambiguo' >&2; exit 1; }
(cd "$(dirname "$ISO")" && printf '%s\n' "$entry" | sha256sum -c -)
file "$ISO"
command -v xorriso >/dev/null || { echo 'Instale xorriso para verificar BIOS/UEFI.' >&2; exit 1; }
report=$(xorriso -indev "$ISO" -report_el_torito plain 2>&1)
printf '%s\n' "$report"
grep -Eq 'El Torito boot img.*BIOS' <<< "$report"
grep -Eq 'El Torito boot img.*UEFI' <<< "$report"
echo 'Integridade e entradas de boot verificadas; inicializacao real exige QEMU/hardware.'
