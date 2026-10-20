#!/usr/bin/env bash
# Run only inside a disposable Debian container; never touches host favorites.
set -Eeuo pipefail
[[ -f /run/.containerenv || -f /.dockerenv ]] || exit 1
cd /src
cmake -S packages/linuxbr-drive-manager/native -B .cache/drive-native-test >/dev/null
cmake --build .cache/drive-native-test -j2 >/dev/null
mkdir -p /usr/lib/linuxbr-drive-manager /usr/share/linuxbr
cp packages/linuxbr-drive-manager/files/usr/share/linuxbr/dolphin-computer.directory /usr/share/linuxbr/
cp .cache/drive-native-test/linuxbr-places-sync /usr/lib/linuxbr-drive-manager/
c++ -std=c++17 -fPIC tests/drive-kio-probe.cpp -o .cache/drive-kio-probe \
 -I/usr/include/KF6/KIOCore -I/usr/include/KF6/KIO -I/usr/include/KF6/KCoreAddons \
 $(pkg-config --cflags --libs Qt6Core Qt6Network) -lKF6KIOCore -lKF6CoreAddons
PLACES_SYNC=/src/.cache/drive-native-test/linuxbr-places-sync dbus-run-session -- python3 tests/test-drive-service.py
QT_PLUGIN_PATH=/src/.cache/drive-native-test KIO_PROBE=/src/.cache/drive-kio-probe dbus-run-session -- python3 tests/test-drive-session.py
