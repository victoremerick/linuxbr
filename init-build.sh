#!/usr/bin/env bash
# Compila a versao atual e valida checksum e entradas de boot da ISO gerada.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

source scripts/build-output.sh

# Carrega todo o fluxo antes de executar o build: edicoes neste arquivo durante
# uma compilacao longa nao devem alterar os comandos lidos ao retornar dela.
main() {
    build_parse_args "$@"
    BUILD_ARGS=()
    (( VERBOSE == 0 )) || BUILD_ARGS+=(--verbose)
    (( NO_CACHE == 0 )) || BUILD_ARGS+=(--no-cache)
    VERSION=$(cat VERSION)
    build_banner "$VERSION"
    ENGINE="${CONTAINER_ENGINE:-podman}"
    # Dependencias usadas pelo build no host e pela verificacao da ISO.
    DEPENDENCIES=("$ENGINE" cat dirname mkdir sha256sum realpath basename wc flock file xorriso awk grep tail tee mktemp chmod chown)
    PACKAGES=()
    MISSING=()
    for dependency in "${DEPENDENCIES[@]}"; do
        if command -v "$dependency" >/dev/null 2>&1; then
            continue
        fi
        MISSING+=("$dependency")
        case "$dependency" in
            podman) package=podman ;;
            docker) package=/usr/bin/docker ;;
            cat|dirname|mkdir|sha256sum|realpath|basename|wc|tail|tee|mktemp|chmod|chown) package=coreutils ;;
            file|xorriso|grep) package="$dependency" ;;
            awk) package=gawk ;;
            flock) package=util-linux ;;
            *)
                echo "Motor personalizado ausente: $dependency. Instale-o ou use CONTAINER_ENGINE=podman." >&2
                exit 1
                ;;
        esac
        # Evitar repetir coreutils quando mais de um comando estiver ausente.
        if [[ ! " ${PACKAGES[*]} " == *" $package "* ]]; then
            PACKAGES+=("$package")
        fi
    done

    AS_ROOT=()
    if (( EUID != 0 )); then
        command -v sudo >/dev/null || {
            echo 'sudo ausente. Execute este script como root para instalar as dependencias e compilar.' >&2
            exit 1
        }
        AS_ROOT=(sudo)
    fi

    if (( ${#MISSING[@]} )); then
        if ! (
            [[ -r /etc/os-release ]] || exit 1
            # shellcheck disable=SC1091
            . /etc/os-release
            [[ "${ID:-}" == fedora ]]
        ); then
            printf 'Instalacao automatica disponivel somente no Fedora. Dependencias ausentes: %s\n' "${MISSING[*]}" >&2
            exit 1
        fi
        command -v dnf >/dev/null || { echo 'DNF ausente; nao foi possivel instalar dependencias.' >&2; exit 1; }
        printf 'Instalando dependencias ausentes no Fedora: %s\n' "${PACKAGES[*]}"
        run_logged dependencias "${AS_ROOT[@]}" dnf install -y "${PACKAGES[@]}"
        hash -r
        for dependency in "${DEPENDENCIES[@]}"; do
            command -v "$dependency" >/dev/null 2>&1 || {
                echo "Dependencia ainda indisponivel apos instalacao: $dependency" >&2
                exit 1
            }
        done
    fi

    mkdir -p .cache/logs
    printf 'Compilando Linux BR %s Alpha...\n' "$VERSION"
    "${AS_ROOT[@]}" env LINUXBR_BANNER_SHOWN=1 CONTAINER_ENGINE="$ENGINE" ./build.sh "${BUILD_ARGS[@]}"

    printf '\nValidando a ISO gerada...\n'
    run_logged validacao env ISO="dist/linuxbr-${VERSION}-amd64.iso" \
    CHECKSUM_FILE="dist/linuxbr-${VERSION}-amd64.iso.sha256" \
        ./tests/verify-iso.sh
    printf '\nCompilacao e verificacao da ISO concluidas. Teste o boot e a instalacao usando:\n'
    printf '  ./init-vm-bios-cd.sh\n  ./init-vm-uefi-cd.sh\n'
}

main "$@"; exit "$?"
