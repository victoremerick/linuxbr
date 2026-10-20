#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
VERSION=$(cat VERSION)
MODE="${1:-bios}"
BOOT="${2:-live}"
[[ "$MODE" == bios || "$MODE" == uefi ]] || { echo 'Uso: tests/test-iso.sh [bios|uefi] [live|installed]' >&2; exit 1; }
[[ "$BOOT" == live || "$BOOT" == installed ]] || { echo 'Boot deve ser live ou installed' >&2; exit 1; }
ISO="${ISO:-dist/linuxbr-${VERSION}-amd64.iso}"
DISK="${DISK_IMAGE:-vm/linuxbr-${VERSION}-${MODE}.qcow2}"
command -v qemu-system-x86_64 >/dev/null || { echo 'Instale qemu-system-x86' >&2; exit 1; }
VIDEO="${QEMU_VIDEO_DEVICE:-virtio-vga}"
[[ "$VIDEO" == virtio-vga || "$VIDEO" == VGA ]] || { echo 'Video deve ser virtio-vga ou VGA.' >&2; exit 1; }
ARGS=(-machine q35 -m "${RAM_MB:-8192}" -smp "${CPUS:-4}" -device "$VIDEO" -display "${QEMU_DISPLAY:-gtk}" -nic "user,model=virtio-net-pci")
if [[ -r /dev/kvm && -w /dev/kvm ]]; then
    ARGS+=(-enable-kvm -cpu host)
else
    echo 'KVM indisponivel; usando emulacao (mais lenta).' >&2
fi
if [[ "$BOOT" == live ]]; then
    [[ -s "$ISO" ]] || { echo "ISO nao encontrada: $ISO" >&2; exit 1; }
    ARGS+=(-cdrom "$ISO" -boot order=d)
else
    [[ -s "$DISK" ]] || { echo "Disco instalado nao encontrado: $DISK" >&2; exit 1; }
    ARGS+=(-boot order=c)
fi
if [[ "$MODE" == uefi ]]; then
    # shellcheck source=scripts/vm-dependencies.sh
    source ./scripts/vm-dependencies.sh
    linuxbr_find_ovmf || { echo 'Defina OVMF_CODE e OVMF_VARS_TEMPLATE como um par compativel, sem Secure Boot.' >&2; exit 1; }
    code="$OVMF_CODE"
    template="$OVMF_VARS_TEMPLATE"
    vars="${OVMF_VARS:-${DISK%.qcow2}.vars.fd}"
    [[ "$vars" != "$code" && "$vars" != "$template" ]] || { echo 'Variaveis devem usar uma copia gravavel.' >&2; exit 1; }
    if [[ ! -e "$vars" ]]; then
        [[ "$BOOT" == live ]] || { echo 'NVRAM da instalacao ausente; indique OVMF_VARS correto.' >&2; exit 1; }
        mkdir -p "$(dirname "$vars")"
        cp "$template" "$vars"
        chmod u+w "$vars"
    fi
    ARGS+=(-drive "if=pflash,format=raw,readonly=on,file=$code" -drive "if=pflash,format=raw,file=$vars")
fi
if [[ ! -e "$DISK" ]]; then
    mkdir -p "$(dirname "$DISK")"
    qemu-img create -f qcow2 "$DISK" "${DISK_SIZE:-32G}"
fi
[[ -f "$DISK" && ! -L "$DISK" ]] || { echo 'Use um arquivo regular qcow2, nao dispositivo ou link.' >&2; exit 1; }
ARGS+=(-drive "file=$DISK,format=qcow2,if=virtio")
if [[ ${QEMU_DIAGNOSTICS:-0} == 1 ]]; then
    mkdir -p .cache
    diagnostic_dir=$(mktemp -d "$PWD/.cache/vm-diagnostic.XXXXXX")
    # Snapshot redirects guest writes to temporary storage, preserving the installation.
    ARGS+=(-snapshot -boot menu=on -qmp "unix:$diagnostic_dir/qmp.sock,server=on,wait=off"
           -serial "file:$diagnostic_dir/serial.log" -D "$diagnostic_dir/qemu.log" -d guest_errors)
    printf '%s\n' "$diagnostic_dir" > .cache/current-vm-diagnostic
    printf 'Diagnostico: %s\nDisco em modo snapshot; alteracoes da sessao nao serao salvas.\n' "$diagnostic_dir"
fi
printf 'Modo: %s / %s; disco: %s\n' "$MODE" "$BOOT" "$DISK"
exec qemu-system-x86_64 "${ARGS[@]}"
