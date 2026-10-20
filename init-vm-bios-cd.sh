#!/usr/bin/env bash
# Inicia a VM em BIOS, com a ISO.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=scripts/vm-dependencies.sh
source ./scripts/vm-dependencies.sh
linuxbr_ensure_vm_dependencies bios
exec ./tests/test-iso.sh bios live
