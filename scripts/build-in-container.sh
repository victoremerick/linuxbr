#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends live-build debootstrap ca-certificates xorriso squashfs-tools dosfstools git
cd /src
mkdir -p build dist
cp -a config/. build/config/
cd build
lb config \
  --distribution trixie \
  --architectures amd64 \
  --binary-images iso-hybrid \
  --debian-installer none \
  --archive-areas 'main contrib non-free non-free-firmware' \
  --bootappend-live 'boot=live components locales=pt_BR.UTF-8 keyboard-layouts=br' \
  --iso-application 'Linux BR Live' \
  --iso-publisher 'Projeto Linux BR' \
  --iso-volume 'LINUXBR_0_1'
lb build
iso="$(find . -maxdepth 1 -type f -name '*.iso' -print -quit)"
if [[ -z "$iso" ]]; then echo 'ERRO: ISO nao encontrada' >&2; exit 1; fi
cp "$iso" /src/dist/linuxbr-0.1-amd64.iso
(cd /src/dist && sha256sum linuxbr-0.1-amd64.iso > SHA256SUMS)
echo 'ISO pronta em dist/linuxbr-0.1-amd64.iso'
