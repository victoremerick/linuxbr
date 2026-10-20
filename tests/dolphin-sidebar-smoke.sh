#!/usr/bin/env bash
set -Eeuo pipefail
[[ -f /run/.containerenv || -f /.dockerenv ]] || exit 1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp "$ROOT/packages/linuxbr-dolphin/sidebar.h" "$WORK/linuxbr-sidebar.h"
cp "$ROOT/packages/linuxbr-dolphin/sidebar-state.h" "$WORK/linuxbr-sidebar-state.h"
c++ -std=c++20 -fPIC "$ROOT/tests/dolphin-sidebar-test.cpp" -o "$WORK/probe" -I"$WORK" \
    -I/usr/include/KF6/KIOCore -I/usr/include/KF6/KIOWidgets -I/usr/include/KF6/KIO \
    -I/usr/include/KF6/KWidgetsAddons -I/usr/include/KF6/KCoreAddons -I/usr/include/KF6/KJobWidgets \
    $(pkg-config --cflags --libs Qt6Widgets Qt6DBus Qt6Network) \
    -lKF6KIOCore -lKF6KIOWidgets -lKF6CoreAddons -lKF6JobWidgets -lKF6WidgetsAddons
HOME="$WORK" XDG_CONFIG_HOME="$WORK/config" XDG_DATA_HOME="$WORK/data" \
    QT_QPA_PLATFORM=offscreen dbus-run-session -- "$WORK/probe"
