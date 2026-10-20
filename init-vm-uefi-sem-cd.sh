#!/usr/bin/env bash
# Inicia a VM em UEFI, pelo disco instalado, sem ISO.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=scripts/vm-dependencies.sh
source ./scripts/vm-dependencies.sh
linuxbr_ensure_vm_dependencies uefi
exec ./tests/test-iso.sh uefi installed
