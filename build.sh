#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ENGINE="${CONTAINER_ENGINE:-podman}"
command -v "$ENGINE" >/dev/null || { echo "Instale $ENGINE primeiro." >&2; exit 1; }
mkdir -p build dist
# Execute com sudo para que o container tenha permissoes de mount/chroot.
# SELinux: label=disable evita relabel recursivo do repositorio; monte apenas repos confiaveis.
"$ENGINE" run --rm --privileged --security-opt label=disable \
  --network host \
  -v "$PWD:/src:rw" \
  -w /src debian:trixie bash /src/scripts/build-in-container.sh
