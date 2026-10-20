#!/usr/bin/env bash
# Fixture D-Bus session only: never mount host devices or contact a real SMB server.
set -Eeuo pipefail
[[ -f /run/.containerenv || -f /.dockerenv ]] || exit 1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
HOME="$WORK" XDG_CONFIG_HOME="$WORK/config" XDG_DATA_HOME="$WORK/data" XDG_RUNTIME_DIR="$WORK" \
    dbus-run-session -- bash -c '
        set -e
        python3 "$1/tests/dolphin-navigation-fixture.py" &
        fixture=$!
        trap "kill $fixture; wait $fixture || true" EXIT
        sleep 2
        helper="$1/packages/linuxbr-drive-manager/files/usr/lib/linuxbr-drive-manager/terminal.py"
        python3 "$helper" list | grep "D:"
        test "$(python3 "$helper" resolve D:/folder)" = /tmp/folder
        test "$(python3 "$helper" resolve C:/etc)" = /etc
        python3 "$helper" mode linux
        test "$(python3 "$helper" mode)" = linux
        python3 "$helper" mode letras
        test "$(python3 "$helper" prompt /tmp/folder | tail -1)" = D:/folder
    ' bash "$ROOT"
echo 'PASS: terminal consulta e resolve letras pelo servico D-Bus real com discos simulados'
