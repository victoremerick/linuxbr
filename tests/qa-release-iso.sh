#!/usr/bin/env bash
# Run from the machine holding the built ISO. QEMU exit status alone is not boot evidence.
set -Eeuo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."

mode=${1:-interactive}
if [[ $# -gt 1 || "$mode" != interactive && "$mode" != integrity && "$mode" != headless ]]; then
    printf 'Uso: bash tests/qa-release-iso.sh [interactive|headless|integrity]\n' >&2
    exit 2
fi

version=$(<VERSION)
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(~(alpha|beta|rc)[1-9][0-9]*)?$ ]] || {
    printf 'Versão inválida em VERSION.\n' >&2
    exit 2
}
expected="linuxbr-$version-amd64.iso"
ISO=${ISO:-dist/$expected}
[[ -s "$ISO" && -f "$ISO" && "$(basename -- "$ISO")" == "$expected" ]] || {
    printf 'Informe a ISO %s já construída neste host.\n' "$expected" >&2
    exit 2
}
ISO=$(realpath -- "$ISO")
export ISO

qa_base=${QA_EVIDENCE_BASE:-$PWD/.cache}
mkdir -p -- "$qa_base"
qa=$(mktemp -d "$(realpath -- "$qa_base")/qa-iso-$version.XXXXXX")
printf 'Diretório de evidências em %s\n' "$qa"
printf '%s\n' "$version" > "$qa/version.txt"
sha256sum -- "$ISO" > "$qa/iso.sha256"
stat --printf='%s\n' -- "$ISO" > "$qa/iso-bytes.txt"
bash tests/verify-iso.sh 2>&1 | tee "$qa/integrity.log"
if [[ "$mode" == integrity ]]; then
    exit 0
fi

export RAM_MB=${RAM_MB:-4096} CPUS=${CPUS:-2} QEMU_DIAGNOSTICS=0
export QEMU_DISPLAY=${QEMU_DISPLAY:-gtk}
if [[ "$mode" == headless ]]; then
    source ./scripts/vm-dependencies.sh
    linuxbr_find_ovmf || { printf 'Instale OVMF ou informe o par de firmware UEFI.\n' >&2; exit 1; }
    python3 tests/qa-live-boot.py "$ISO" "$qa" "$version"
    sha256sum -c -- "$qa/iso.sha256" | tee "$qa/integrity-after-boot.log"
    exit 0
fi

run_vm() {
    local firmware=$1 boot=$2 disk=$3 log=$4
    DISK_IMAGE="$disk" OVMF_VARS="$qa/uefi.vars.fd" \
        bash tests/test-iso.sh "$firmware" "$boot" 2>&1 | tee "$qa/$log.log"
}

printf '%s\n' 'Abra o desktop Live em UEFI, confira a versão e instale pelo Calamares. Desligue a VM após a instalação.'
run_vm uefi live "$qa/desktop-uefi.qcow2" uefi-live

printf '%s\n' 'Entre no desktop instalado e execute as verificações de sessão. Desligue a VM para seguir ao boot BIOS.'
run_vm uefi installed "$qa/desktop-uefi.qcow2" uefi-installed

printf '%s\n' 'Abra o desktop Live em BIOS, confira a versão e desligue a VM.'
run_vm bios live "$qa/live-bios.qcow2" bios-live

sha256sum -c -- "$qa/iso.sha256" | tee "$qa/integrity-after-boot.log"
printf '%s\n' 'As sessões QEMU foram encerradas. Registre o resultado observado de cada cenário com as evidências do guest.'
