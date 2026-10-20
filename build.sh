#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source scripts/build-output.sh
main() {
    build_parse_args "$@"
    local version
    version=$(cat VERSION)
    build_banner "$version"
    local engine="${CONTAINER_ENGINE:-podman}"
    command -v "$engine" >/dev/null || { echo "Instale $engine primeiro." >&2; exit 1; }
    mkdir -p build dist
    # Keep the whole container program in memory, even if the checkout is edited.
    local program
    program=$(cat scripts/build-in-container.sh)
    mkdir -p .cache
    # Protect shared downloads and ISO publication from simultaneous builds.
    exec 9>.cache/build.lock
    flock -n 9 || { echo 'Outro build esta em andamento neste projeto.' >&2; exit 1; }
    local image digest
    digest=$(sha256sum scripts/Containerfile.build); digest=${digest%% *}
    image="localhost/linuxbr-builder:${digest:0:20}"
    compile_iso() {
        if (( NO_CACHE )) || ! "$engine" image inspect "$image" >/dev/null 2>&1; then
            local -a refresh=()
            if (( NO_CACHE )); then
                refresh=(--no-cache)
                "$engine" pull docker.io/library/debian:trixie || return $?
            fi
            echo 'Preparando imagem reutilizavel de compilacao...'
            "$engine" build "${refresh[@]}" -t "$image" -f scripts/Containerfile.build scripts || return $?
        else
            echo 'Reutilizando ferramentas de compilacao.'
        fi
        "$engine" run --rm --privileged --security-opt label=disable \
          --network host -e LINUXBR_NO_CACHE="$NO_CACHE" -v "$PWD:/src:rw" -w /src "$image" \
          bash -c "$program"
    }
    run_logged compilacao compile_iso
    printf 'ISO pronta: dist/linuxbr-%s-amd64.iso\n' "$version"
}
main "$@"; exit "$?"
