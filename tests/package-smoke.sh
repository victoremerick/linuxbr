#!/usr/bin/env bash
# Run ONLY in a disposable Debian container, never on the development host.
set -Eeuo pipefail
[[ -f /run/.containerenv || -f /.dockerenv ]] || { echo 'Execute em container descartavel.' >&2; exit 1; }
cd /src
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-yaml python3-pil librsvg2-bin cmake build-essential dpkg-dev qt6-base-dev libkf6kio-dev libkf6bookmarks-dev >/dev/null
work=$(mktemp -d /src/.cache/package-test.XXXXXX)
mkdir -p "$work/upstream"
(cd "$work/upstream" && apt-get download calamares-settings-debian=13.0.13-1 sddm-theme-breeze)
python3 scripts/build-packages.py --output "$work/debs" --work "$work/work" \
    --calamares-deb "$work"/upstream/calamares-settings-debian_*.deb \
    --breeze-deb "$work"/upstream/sddm-theme-breeze_*.deb
# Compare installation sequence and helper contents against the tested Debian version.
python3 tests/test-packages.py "$work"
cp /usr/lib/os-release "$work/original-os-release"
cp -a /etc/os-release "$work/original-etc-os-release"
dpkg -i "$work"/debs/linuxbr-branding_*.deb "$work"/debs/linuxbr-release_*.deb
grep -qx 'ID=linuxbr' /etc/os-release
# Reconfigure/reinstall and base-files upgrades must retain our identity.
dpkg -i "$work"/debs/linuxbr-release_*.deb
apt-get install --reinstall -y base-files >/dev/null
grep -qx 'ID=linuxbr' /etc/os-release
grep -qx 'ID=linuxbr' /usr/lib/os-release
apt-get update -qq
dpkg --remove linuxbr-release
cmp /usr/lib/os-release "$work/original-os-release"
[[ -L /etc/os-release ]]
dpkg --purge linuxbr-release
printf 'PASS: pacotes gerados, identidade instalada/reinstalada, base-files atualizado, APT e restauracao Debian.\nArtefatos: %s\n' "$work"

# Reproduce bootstrap_debootstrap + chroot_dpkg in live-build Trixie.
# The ordinary Debian container above does not contain this LOCAL diversion.
touch /.live-build
dpkg-divert --quiet --local --add --no-rename \
    --divert /etc/os-release.debootstrap /etc/os-release
rm /etc/os-release
cp /usr/lib/os-release /etc/os-release
printf 'IMAGE_ID=live\nBUILD_ID=regression-test\n' >> /etc/os-release
dpkg -i "$work"/debs/linuxbr-release_*.deb
test "$(dpkg-divert --listpackage /etc/os-release)" = linuxbr-release
test "$(dpkg-divert --truename /etc/os-release)" = /etc/os-release.debian
# chroot_hacks must not match/remove the package's permanent diversion.
if dpkg-divert --list /etc/os-release | grep -q os-release.debootstrap; then
    echo 'Desvio temporario do live-build ainda ativo' >&2
    exit 1
fi
dpkg -i "$work"/debs/linuxbr-release_*.deb
apt-get install --reinstall -y base-files >/dev/null
grep -qx 'ID=linuxbr' /etc/os-release
grep -qx 'ID=linuxbr' /usr/lib/os-release
rm /.live-build
dpkg --purge linuxbr-release
cmp /usr/lib/os-release "$work/original-os-release"
# Reinstalling base-files refreshes the diverted original to its Debian symlink.
cmp /etc/os-release "$work/original-os-release"
[[ -L /etc/os-release ]]
# Unrelated local diversions must still be rejected, even during live-build.
touch /.live-build
dpkg-divert --quiet --local --add --no-rename \
    --divert /etc/os-release.admin /etc/os-release
if dpkg -i "$work"/debs/linuxbr-release_*.deb > "$work/conflict.log" 2>&1; then
    echo 'ERRO: desvio administrativo aceito indevidamente' >&2
    exit 1
fi
grep -q 'Diversion conflitante: /etc/os-release (LOCAL)' "$work/conflict.log"
test "$(dpkg-divert --truename /etc/os-release)" = /etc/os-release.admin
dpkg --purge linuxbr-release
dpkg-divert --quiet --local --remove --no-rename /etc/os-release
rm /.live-build
printf 'PASS: desvio live-build, reinstalacao, base-files, restauracao e rejeicao de desvio administrativo.\n'

if [[ "${FULL_INTEGRATION:-0}" == 1 ]]; then
    printf '%s\n' 'deb-src [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] http://deb.debian.org/debian trixie main' > /etc/apt/sources.list.d/linuxbr-test-src.list
    apt-get update -qq
    apt-get build-dep -y dolphin > "$work/dolphin-build.log" 2>&1
    apt-get install -y --no-install-recommends devscripts >> "$work/dolphin-build.log" 2>&1
    mkdir -p /src/build
    bash scripts/build-dolphin.sh "$work/debs" >> "$work/dolphin-build.log" 2>&1
    apt-get install -y --no-install-recommends "$work"/debs/*.deb > "$work/integration.log" 2>&1
    python3 tests/check-rootfs.py / --mode live
    apt-get remove -y linuxbr-calamares-settings >> "$work/integration.log" 2>&1
    python3 tests/check-rootfs.py / --mode installed
    test -f /usr/share/applications/calamares.desktop
    echo 'PASS: instalacao conjunta e remocao da configuracao do instalador'
fi
