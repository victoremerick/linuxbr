#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
(cd dist && sha256sum -c SHA256SUMS)
file dist/linuxbr-0.1-amd64.iso
