#!/usr/bin/env bash
# Sourced by the two entry points before any long-running command.
build_parse_args() {
    VERBOSE=0
    NO_CACHE=0
    for arg in "$@"; do
        case "$arg" in
            --no-cache) NO_CACHE=1 ;;
            -v|--verbose) VERBOSE=1 ;;
            -h|--help) printf 'Uso: %s [-v|--verbose] [--no-cache]\n--no-cache: recria as ferramentas e ignora downloads anteriores.\nSem -v: resumo e logs completos em .cache/logs/.\n' "$0"; exit 0 ;;
            *) printf 'Parametro desconhecido: %s\n' "$arg" >&2; exit 2 ;;
        esac
    done
}
build_banner() {
    [[ ${LINUXBR_BANNER_SHOWN:-0} == 1 ]] && return 0
    local yellow='' green='' purple='' reset=''
    if [[ -t 1 && -z ${NO_COLOR:-} && ${TERM:-dumb} != dumb ]]; then
        yellow=$'\e[38;2;228;223;145m'; green=$'\e[38;2;142;219;145m'
        purple=$'\e[38;2;150;144;217m'; reset=$'\e[0m'
    fi
    # Keep artwork as literal arguments: printf must not interpret its backslashes.
    local -a logo=('  |\       ' '  | \      ' '  ( * )>   ' '  (   )>   ' '  | /      ' '  |/       ')
    # Block lettering stays readable at typical terminal widths.
    local -a wordmark=(
        'L     III  N   N  U   U  X   X    BBBB   RRRR '
        'L      I   NN  N  U   U   X X     B   B  R   R'
        'L      I   N N N  U   U    X      BBBB   RRRR '
        'L      I   N  NN  U   U   X X     B   B  R  R '
        'LLLLL III  N   N   UUU   X   X    BBBB   R   R'
    )
    local i color
    printf '\n'
    for ((i=0; i<5; i++)); do
        color=$yellow
        (( i != 2 && i != 3 )) || color=$purple
        printf '  %s%s%s%s\n' "$color" "${logo[$i]}" "$reset" "${wordmark[$i]}"
    done
    printf '  %s%s%s%s Alpha · amd64 · KDE Plasma\n' "$yellow" "${logo[5]}" "$reset" "$1"
    printf '  %s%s%s\n\n' "$green" '--------------------------------------------------------' "$reset"

}

# Stages measure completed work, not elapsed time or a predicted percentage.
build_progress() {
    local log=$1 label=$2 stage=0 last=-1 tick=0 name bar spin i
    local -a names=('Preparando ambiente' 'Gerando pacotes e identidade' 'Configurando live-build' 'Construindo sistema live' 'Validando sistema live' 'Publicando ISO e checksum' 'Finalizando')
    local -a frames=('|' '/' '-' '\\')
    while :; do
        stage=$(awk '/^LINUXBR_STAGE [0-6]$/ {s=$2} END {print s+0}' "$log")
        name=${names[$stage]}
        if [[ -t 1 && ${TERM:-dumb} != dumb ]]; then
            bar=''; for ((i=0; i<6; i++)); do
                if (( i < stage )); then bar+='#'; else bar+='.'; fi
            done
            spin=${frames[$((tick % 4))]}
            printf '\r\033[2K%s [%s] %s/6 etapas · %s %s' "$label" "$bar" "$stage" "$name" "$spin"
        elif (( stage != last )); then
            printf '%s: %s (%s/6 etapas).\n' "$label" "$name" "$stage"
        fi
        last=$stage; tick=$((tick + 1))
        sleep 1
    done
}
run_logged() (
    local label=$1 log rc monitor=''
    shift
    # The monitor is UI only. Keep the build in the foreground and reap the UI
    # on success, failure or interruption without changing the caller's traps.
    trap 'if [[ -n $monitor ]]; then kill "$monitor" 2>/dev/null || :; wait "$monitor" 2>/dev/null || :; fi' EXIT
    if [[ ! -d .cache/logs ]]; then
        mkdir -p .cache/logs
        if (( EUID == 0 )) && [[ ${SUDO_UID:-} =~ ^[0-9]+$ && ${SUDO_GID:-} =~ ^[0-9]+$ ]]; then
            chown "$SUDO_UID:$SUDO_GID" .cache/logs
        fi
    fi
    log=$(mktemp ".cache/logs/${label}.XXXXXX.log")
    chmod 0644 "$log"
    printf '%s — log: %s\n' "$label" "$log"
    if (( VERBOSE )); then
        if "$@" 2>&1 | tee "$log"; then return 0; else rc=$?; fi
    else
        if [[ $label == compilacao ]]; then
            build_progress "$log" "$label" & monitor=$!
        fi
        if "$@" > "$log" 2>&1; then rc=0; else rc=$?; fi
        if [[ -n $monitor ]]; then
            kill "$monitor" 2>/dev/null || :; wait "$monitor" 2>/dev/null || :; monitor=''
            if [[ -t 1 && ${TERM:-dumb} != dumb ]]; then printf '\r\033[2K'; fi
        fi
        if (( rc == 0 )); then
            [[ $label != compilacao ]] || printf '[######] 6/6 etapas · '
            printf '%s: concluido.\n' "$label"
            return 0
        fi
        printf '\nFalha em %s (codigo %s). Ultimas mensagens:\n' "$label" "$rc" >&2
        tail -n 40 "$log" >&2
    fi
    printf 'Log completo: %s\n' "$log" >&2
    return "$rc"
)
