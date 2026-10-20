#!/usr/bin/env bash
set -Eeuo pipefail
# Parse the entire workflow before running commands that may take hours.
main() {
    export DEBIAN_FRONTEND=noninteractive
    cd /src
    VERSION=$(cat VERSION)
    [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Versao invalida' >&2; exit 1; }
    echo "LINUXBR_STAGE 0"
    # Unique workspaces prevent live-build stamps/cache from hiding source changes.
    mkdir -p build dist
    WORK=$(mktemp -d "/src/build/linuxbr-${VERSION}.XXXXXX")
    # Freeze package inputs and validation together before the long live-build run.
    # Edits in the checkout apply only to the next build.
    mkdir -p "$WORK/upstream" "$WORK/config" "$WORK/source"
    cp -a VERSION packages scripts tests config "$WORK/source/"
    cp -a "$WORK/source/config/." "$WORK/config/"
    # Reuse only downloaded archives, never chroot trees or live-build stamps.
    PACKAGE_CACHE=/src/.cache/build-downloads/trixie-amd64
    mkdir -p "$WORK/cache"
    save_downloads() {
        local directory
        for directory in "$WORK"/cache/packages.*; do
            [[ -d "$directory" ]] || continue
            mkdir -p "$PACKAGE_CACHE/${directory##*/}"
            cp -a --reflink=auto "$directory/." "$PACKAGE_CACHE/${directory##*/}/" || true
        done
    }
    if [[ ${LINUXBR_NO_CACHE:-0} != 1 ]]; then
        mkdir -p "$PACKAGE_CACHE"
        for directory in "$PACKAGE_CACHE"/packages.*; do
            [[ -d "$directory" ]] || continue
            cp -a --reflink=auto "$directory" "$WORK/cache/"
        done
        # Local package versions may stay unchanged between source edits.
        # Never restore their old payload from an archive cache.
        find "$WORK/cache" -type f \( -name 'linuxbr-*.deb' -o -name 'dolphin_*.deb' -o -name 'dolphin-data_*.deb' -o -name 'libdolphinvcs6_*.deb' \) -delete
        trap save_downloads EXIT
    fi
    # Always refresh repository metadata, including the upstream theme version.
    apt-get update

    (
        cd "$WORK/upstream"
        apt-get download calamares-settings-debian=13.0.13-1 sddm-theme-breeze
    )
    echo "LINUXBR_STAGE 1"
    python3 "$WORK/source/scripts/build-packages.py" --output "$WORK/config/packages.chroot" \
        --work "$WORK/packages" \
        --calamares-deb "$WORK"/upstream/calamares-settings-debian_*.deb \
        --breeze-deb "$WORK"/upstream/sddm-theme-breeze_*.deb
    bash "$WORK/source/scripts/build-dolphin.sh" "$WORK/config/packages.chroot"
    python3 "$WORK/source/scripts/prepare-live-boot.py" "$WORK"
    cd "$WORK"
    echo "LINUXBR_STAGE 2"
    lb config \
      --distribution trixie \
      --architectures amd64 \
      --binary-images iso-hybrid \
      --debian-installer none \
      --firmware-chroot false \
      --firmware-binary false \
      --archive-areas 'main contrib non-free non-free-firmware' \
      --bootappend-live 'boot=live components locales=pt_BR.UTF-8 keyboard-layouts=br keyboard-model=abnt2 timezone=America/Sao_Paulo quiet splash loglevel=3 systemd.show_status=false rd.systemd.show_status=false udev.log_level=3 vt.global_cursor_default=0' \
      --iso-application 'Linux BR Live' \
      --iso-publisher 'Projeto Linux BR' \
      --iso-volume "LINUXBR_${VERSION//./_}"
    echo "LINUXBR_STAGE 3"
    lb build
    iso=live-image-amd64.hybrid.iso
    [[ -s "$iso" ]] || { echo 'ERRO: ISO nao encontrada' >&2; exit 1; }
    echo "LINUXBR_STAGE 4"
    python3 "$WORK/source/tests/check-rootfs.py" chroot --mode live
    echo "LINUXBR_STAGE 5"
    install -m 0644 "$iso" "/src/dist/linuxbr-${VERSION}-amd64.iso"
    cp config/packages.chroot/UPSTREAM-SHA256SUMS "/src/dist/linuxbr-${VERSION}-upstream.sha256"
    cd /src/dist
    sha256sum "linuxbr-${VERSION}-amd64.iso" > "linuxbr-${VERSION}-amd64.iso.sha256"
    # Preserve historical checksums and refresh only the current entry.
    if [[ -f SHA256SUMS ]]; then
        awk -v name="linuxbr-${VERSION}-amd64.iso" '$2 != name' SHA256SUMS > SHA256SUMS.tmp
    else
        : > SHA256SUMS.tmp
    fi
    cat "linuxbr-${VERSION}-amd64.iso.sha256" >> SHA256SUMS.tmp
    mv SHA256SUMS.tmp SHA256SUMS
    echo "LINUXBR_STAGE 6"
    printf 'ISO pronta: dist/linuxbr-%s-amd64.iso\nWorkspace preservado: %s\n' "$VERSION" "$WORK"
}
main "$@"; exit "$?"
