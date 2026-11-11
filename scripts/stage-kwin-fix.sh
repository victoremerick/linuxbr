#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

# Stage the Debian fix for a compositor crash during output changes (Debian #1147212).
version='4:6.3.6-1+deb13u1'
packages=(kwin-common kwin-data kwin-wayland libkwin6 kwin-x11)
keyring=/usr/share/keyrings/debian-archive-keyring.gpg

fail() {
    printf 'KWin: %s\n' "$*" >&2
    exit 1
}

[[ $# -eq 1 && -d $1 ]] || fail 'Informe a pasta de pacotes do build.'
output=$(realpath -- "$1")
manifest="$output/UPSTREAM-SHA256SUMS"
[[ -f $manifest && ! -L $manifest ]] || fail 'O manifesto de entradas do build está ausente.'
[[ $(dpkg --print-architecture) == amd64 ]] || fail 'Esta imagem é construída para amd64.'

fixed=0
for package in "${packages[@]}"; do
    candidate=$(apt-cache -o Dir::State::status=/dev/null policy "$package" |
        awk '$1 == "Candidate:" { print $2 }')
    if [[ -n $candidate && $candidate != '(none)' ]] &&
        dpkg --compare-versions "$candidate" ge "$version"; then
        fixed=$((fixed + 1))
    fi
done
if [[ $fixed -eq ${#packages[@]} ]]; then
    printf 'KWin: os cinco candidatos da base Debian já incluem a correção.\n'
    exit 0
fi

[[ -r $keyring ]] || fail 'O chaveiro oficial do Debian está ausente.'
workspace=$(mktemp -d /tmp/linuxbr-kwin.XXXXXXXX)
manifest_temp=''
cleanup() {
    if [[ -n $manifest_temp ]]; then
        rm -f -- "$manifest_temp"
    fi
    rm -rf -- "$workspace"
}
trap cleanup EXIT
chmod 0755 "$workspace"
mkdir -p "$workspace/lists/partial" "$workspace/cache/archives/partial" \
    "$workspace/download" "$workspace/verified" "$workspace/empty"
if [[ $EUID -eq 0 ]] && getent passwd _apt >/dev/null; then
    chown _apt "$workspace/download"
fi
: > "$workspace/status"

cat > "$workspace/kwin.sources" <<EOF
Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie-proposed-updates
Components: main
Architectures: amd64
Signed-By: $keyring
EOF

# Load no global apt.conf.d hooks, sources, lists, installed state or cache.
cat > "$workspace/apt.conf" <<EOF
Dir::Etc::Main "/dev/null";
Dir::Etc::Parts "$workspace/empty";
Dir::Etc::sourcelist "$workspace/kwin.sources";
Dir::Etc::sourceparts "$workspace/empty";
Dir::Etc::preferences "/dev/null";
Dir::Etc::preferencesparts "$workspace/empty";
Dir::State::Lists "$workspace/lists";
Dir::State::status "$workspace/status";
Dir::Cache "$workspace/cache";
Acquire::AllowInsecureRepositories "false";
Acquire::AllowDowngradeToInsecureRepositories "false";
Acquire::AllowWeakRepositories "false";
Acquire::Check-Valid-Until "true";
Acquire::Languages "none";
APT::Get::AllowUnauthenticated "false";
EOF

specs=()
for package in "${packages[@]}"; do
    specs+=("$package=$version")
done
APT_CONFIG="$workspace/apt.conf" apt-get update --error-on=any
(
    cd "$workspace/download"
    APT_CONFIG="$workspace/apt.conf" apt-get download "${specs[@]}"
)

shopt -s nullglob
declare -A digest_by_file
for package in "${packages[@]}"; do
    metadata=$(APT_CONFIG="$workspace/apt.conf" apt-cache show "$package=$version")
    digest=$(awk '$1 == "SHA256:" { print $2 }' <<< "$metadata")
    path=$(awk '$1 == "Filename:" { print $2 }' <<< "$metadata")
    arch=amd64
    if [[ $package == kwin-data ]]; then
        arch=all
    fi
    filename=${path##*/}
    [[ $digest =~ ^[0-9a-f]{64}$ && $path == "pool/main/k/kwin/$filename" &&
        $filename == "${package}_"*"_${arch}.deb" ]] || fail "Metadados assinados inválidos para $package."

    archives=("$workspace/download/${package}_"*.deb)
    [[ ${#archives[@]} -eq 1 ]] || fail "Arquivo ausente ou repetido para $package."
    install -m 0644 -- "${archives[0]}" "$workspace/verified/$filename"
    (
        cd "$workspace/verified"
        printf '%s  %s\n' "$digest" "$filename" | sha256sum --check --strict
    )
    archive="$workspace/verified/$filename"
    [[ $(dpkg-deb -f "$archive" Package) == "$package" &&
        $(dpkg-deb -f "$archive" Version) == "$version" &&
        $(dpkg-deb -f "$archive" Architecture) == "$arch" ]] ||
        fail "Cabeçalho do pacote não confere para $package."
    for staged in "$output/${package}_"*.deb; do
        [[ $staged == "$output/$filename" && ! -L $staged ]] &&
            cmp -s -- "$archive" "$staged" || fail "Outro pacote $package já foi preparado."
    done
    digest_by_file[$filename]=$digest
done

manifest_temp=$(mktemp "$output/.kwin-sha256.XXXXXXXX")
cp -- "$manifest" "$manifest_temp"
for archive in "$workspace/verified/"*.deb; do
    filename=${archive##*/}
    digest=${digest_by_file[$filename]}
    existing=$(awk -v filename="$filename" '$2 == filename { print $1 }' "$manifest")
    [[ -z $existing || $existing == "$digest" ]] || fail "Checksum conflitante para $filename."
    if [[ -z $existing ]]; then
        printf '%s  %s\n' "$digest" "$filename" >> "$manifest_temp"
    fi
done
for archive in "$workspace/verified/"*.deb; do
    filename=${archive##*/}
    install -m 0644 -- "$archive" "$output/$filename"
done
chmod 0644 "$manifest_temp"
mv -T -- "$manifest_temp" "$manifest"
manifest_temp=''
printf 'KWin: cinco pacotes Debian %s preparados e verificados.\n' "$version"
