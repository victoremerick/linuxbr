#!/usr/bin/env bash
# Exercise the actual patched Dolphin widget with Debian's Breeze style.
set -Eeuo pipefail
[[ -f /run/.containerenv || -f /.dockerenv ]] || exit 1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SOURCE=$(realpath "${1:?Patched Dolphin source/build tree required}")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
c++ -std=c++20 -fPIC "$ROOT/tests/dolphin-card-paint-test.cpp" -o "$WORK/probe" \
    -I"$SOURCE/src" -I"$SOURCE/obj-x86_64-linux-gnu/src" \
    -I/usr/include/KF6/KIOCore -I/usr/include/KF6/KIO -I/usr/include/KF6/KCoreAddons \
    $(pkg-config --cflags --libs Qt6Widgets Qt6Network) \
    -L"$SOURCE/obj-x86_64-linux-gnu/bin" \
    -Wl,-rpath-link,"$SOURCE/obj-x86_64-linux-gnu/bin" -ldolphinprivate
HOME="$WORK" XDG_CONFIG_HOME="$WORK/config" XDG_DATA_HOME="$WORK/data" \
    LD_LIBRARY_PATH="$SOURCE/obj-x86_64-linux-gnu/bin" QT_QPA_PLATFORM=offscreen \
    dbus-run-session -- "$WORK/probe"
