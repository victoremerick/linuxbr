#!/usr/bin/env bash
# Alternate display adapter and QMP access, without persisting guest disk writes.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mode="${1:-bios}"
[[ "$mode" == bios || "$mode" == uefi ]] || { echo 'Uso: ./init-vm-diagnostico.sh [bios|uefi]' >&2; exit 2; }
source scripts/vm-dependencies.sh
linuxbr_ensure_vm_dependencies "$mode"
export QEMU_VIDEO_DEVICE=VGA QEMU_DIAGNOSTICS=1
exec ./tests/test-iso.sh "$mode" installed
