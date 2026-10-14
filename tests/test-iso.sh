#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ISO="${ISO:-dist/linuxbr-0.1-amd64.iso}"
[[ -s "$ISO" ]] || { echo "ISO nao encontrada: $ISO" >&2; exit 1; }
command -v qemu-system-x86_64 >/dev/null || { echo 'Instale qemu-system-x86' >&2; exit 1; }
MODE="${1:-bios}"
ARGS=(-m "${RAM_MB:-4096}" -smp 2 -cdrom "$ISO" -boot d -drive "file=${DISK_IMAGE:-vm/test-disk.qcow2},format=qcow2,if=virtio" -nic user,model=virtio-net-pci)
mkdir -p build
if [[ ! -e "${DISK_IMAGE:-vm/test-disk.qcow2}" ]]; then
  qemu-img create -f qcow2 "${DISK_IMAGE:-vm/test-disk.qcow2}" 32G
fi
if [[ "$MODE" == uefi ]]; then
  OVMF="$(find /usr/share/edk2/ovmf /usr/share/OVMF -name 'OVMF_CODE*.fd' 2>/dev/null | head -n 1 || true)"
  [[ -n "$OVMF" ]] || { echo 'Firmware OVMF nao encontrado (instale edk2-ovmf).' >&2; exit 1; }
  ARGS+=(-drive "if=pflash,format=raw,readonly=on,file=$OVMF")
elif [[ "$MODE" != bios ]]; then
  echo 'Uso: tests/test-iso.sh [bios|uefi]' >&2; exit 1
fi
exec qemu-system-x86_64 "${ARGS[@]}"
