#!/usr/bin/env bash
# Biblioteca compartilhada pelos atalhos de VM. Nao inicia QEMU nem altera discos.

linuxbr_find_ovmf() {
    local directory suffix
    if [[ -n "${OVMF_CODE:-}" || -n "${OVMF_VARS_TEMPLATE:-}" ]]; then
        [[ -f "${OVMF_CODE:-}" && -f "${OVMF_VARS_TEMPLATE:-}" ]]
        return
    fi
    for directory in /usr/share/edk2/ovmf /usr/share/OVMF /usr/share/edk2/x64; do
        for suffix in _4M ''; do
            if [[ -f "$directory/OVMF_CODE${suffix}.fd" && -f "$directory/OVMF_VARS${suffix}.fd" ]]; then
                export OVMF_CODE="$directory/OVMF_CODE${suffix}.fd"
                export OVMF_VARS_TEMPLATE="$directory/OVMF_VARS${suffix}.fd"
                return 0
            fi
        done
    done
    return 1
}

linuxbr_has_gtk_display() {
    local displays
    displays=$(qemu-system-x86_64 -display help 2>/dev/null) || return 1
    [[ $'\n'"$displays"$'\n' == *$'\ngtk\n'* ]]
}

linuxbr_ensure_vm_dependencies() {
    local mode="${1:?Informe bios ou uefi}" display="${QEMU_DISPLAY:-gtk}" dependency
    local -a packages=() as_root=()
    [[ "$mode" == bios || "$mode" == uefi ]] || { echo 'Modo de VM invalido.' >&2; return 1; }
    if [[ "$mode" == uefi && ( -n "${OVMF_CODE:-}" || -n "${OVMF_VARS_TEMPLATE:-}" ) ]]; then
        linuxbr_find_ovmf || {
            echo 'OVMF_CODE e OVMF_VARS_TEMPLATE devem apontar para arquivos existentes de um par compativel.' >&2
            return 1
        }
    fi
    command -v qemu-system-x86_64 >/dev/null 2>&1 || packages+=(qemu-system-x86)
    command -v qemu-img >/dev/null 2>&1 || packages+=(qemu-img)
    if [[ "${display%%,*}" == gtk ]] && ! linuxbr_has_gtk_display; then
        packages+=(qemu-ui-gtk)
    fi
    if [[ "$mode" == uefi ]] && ! linuxbr_find_ovmf; then
        packages+=(edk2-ovmf)
    fi
    if (( ${#packages[@]} )); then
        if ! (
            [[ -r /etc/os-release ]] || exit 1
            # shellcheck disable=SC1091
            . /etc/os-release
            [[ "${ID:-}" == fedora ]]
        ); then
            printf 'Instalacao automatica disponivel somente no Fedora. Dependencias ausentes: %s\n' "${packages[*]}" >&2
            return 1
        fi
        command -v dnf >/dev/null || { echo 'DNF ausente; instale as dependencias manualmente.' >&2; return 1; }
        if (( EUID != 0 )); then
            command -v sudo >/dev/null || { echo 'sudo ausente; instale as dependencias como administrador.' >&2; return 1; }
            as_root=(sudo)
        fi
        printf 'Instalando dependencias de VM no Fedora: %s\n' "${packages[*]}"
        "${as_root[@]}" dnf install -y "${packages[@]}" || return
        hash -r
    fi
    for dependency in qemu-system-x86_64 qemu-img; do
        command -v "$dependency" >/dev/null 2>&1 || {
            echo "Dependencia ainda ausente: $dependency" >&2
            return 1
        }
    done
    if [[ "${display%%,*}" == gtk ]] && ! linuxbr_has_gtk_display; then
        echo 'Backend GTK do QEMU indisponivel apos instalacao.' >&2
        return 1
    fi
    if [[ "$mode" == uefi ]] && ! linuxbr_find_ovmf; then
        echo 'OVMF nao encontrado; defina OVMF_CODE e OVMF_VARS_TEMPLATE como um par compativel sem Secure Boot.' >&2
        return 1
    fi
}
