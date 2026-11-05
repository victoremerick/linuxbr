# Only sourced by the Linux BR Konsole profile (interactive Bash).
[[ $- == *i* && -z ${_LINUXBR_TERMINAL_LOADED:-} ]] || return
_LINUXBR_TERMINAL_LOADED=1
_LINUXBR_ORIGINAL_PS1=${PS1-}
_LINUXBR_TERMINAL_MODE=linux
_linuxbr_terminal_helper() { /usr/bin/python3 /usr/lib/linuxbr-drive-manager/terminal.py "$@"; }
_linuxbr_apply_mode() {
    _LINUXBR_TERMINAL_MODE=$1
    if [[ $1 == letras ]]; then
        LINUXBR_TERMINAL_PATH=${LINUXBR_TERMINAL_PATH:-C:\\}
        PS1='${LINUXBR_TERMINAL_PATH}> '
    else
        PS1=$_LINUXBR_ORIGINAL_PS1
    fi
}
terminal-modo() {
    if (( $# == 0 )); then printf '%s\n' "$_LINUXBR_TERMINAL_MODE"; return; fi
    (( $# == 1 )) || { printf 'Use terminal-modo letras ou terminal-modo linux.\n' >&2; return 2; }
    [[ $1 == letras || $1 == linux ]] || { printf 'Use terminal-modo letras ou terminal-modo linux.\n' >&2; return 2; }
    _linuxbr_apply_mode "$1"
}
unidades() { _linuxbr_terminal_helper list; }
unidade() { (( $# == 1 )) || { printf 'Use unidade D:/caminho\n' >&2; return 2; }; _linuxbr_terminal_helper resolve "$1"; }
_linuxbr_cd() {
    if [[ $_LINUXBR_TERMINAL_MODE == letras && ${1:-} == /[dD] ]]; then
        shift
        (( $# == 1 )) || { printf 'Use cd /d "D:/pasta".\n' >&2; return 2; }
    fi
    local -a options=() original=("$@")
    local target
    while (( $# )); do
        case $1 in
            --) shift; break ;;
            -L|-P|-e|-@) options+=("$1"); shift ;;
            *) break ;;
        esac
    done
    if [[ $_LINUXBR_TERMINAL_MODE == letras && $# == 1 && $1 =~ ^[A-Za-z]: ]]; then
        target=$(_linuxbr_terminal_helper resolve "$1") || return
        builtin cd "${options[@]}" -- "$target"
    else
        builtin cd "${original[@]}"
    fi
}
# Preserve any user's existing custom cd function. Drive shortcuts still work.
if ! declare -F cd >/dev/null; then
    function cd { _linuxbr_cd "$@"; }
fi
_linuxbr_drive() {
    [[ $_LINUXBR_TERMINAL_MODE == letras ]] || { printf 'Modo Linux ativo. Use terminal-modo letras para habilitar unidades.\n' >&2; return 127; }
    (( $# == 1 )) || return 2
    _linuxbr_cd "$1"
}
_linuxbr_prompt() {
    local previous=$? output fallback
    if [[ $_LINUXBR_TERMINAL_MODE == letras ]]; then
        if output=$(_linuxbr_terminal_helper prompt "$PWD" 2>/dev/null); then
            LINUXBR_TERMINAL_PATH=${output#*$'\n'}
        else
            fallback=${PWD//\//\\}
            LINUXBR_TERMINAL_PATH="C:${fallback//[[:cntrl:]]/?}"
        fi
    fi
    return "$previous"
}
# Append without evaluating/replacing the user's existing prompt hooks.
if [[ $(declare -p PROMPT_COMMAND 2>/dev/null) == 'declare -a '* ]]; then
    PROMPT_COMMAND+=(_linuxbr_prompt)
else
    PROMPT_COMMAND=("${PROMPT_COMMAND-}" _linuxbr_prompt)
fi
_linuxbr_apply_mode letras
function C: { _linuxbr_drive C: "$@"; }
function D: { _linuxbr_drive D: "$@"; }
function E: { _linuxbr_drive E: "$@"; }
function F: { _linuxbr_drive F: "$@"; }
function G: { _linuxbr_drive G: "$@"; }
function H: { _linuxbr_drive H: "$@"; }
function I: { _linuxbr_drive I: "$@"; }
function J: { _linuxbr_drive J: "$@"; }
function K: { _linuxbr_drive K: "$@"; }
function L: { _linuxbr_drive L: "$@"; }
function M: { _linuxbr_drive M: "$@"; }
function N: { _linuxbr_drive N: "$@"; }
function O: { _linuxbr_drive O: "$@"; }
function P: { _linuxbr_drive P: "$@"; }
function Q: { _linuxbr_drive Q: "$@"; }
function R: { _linuxbr_drive R: "$@"; }
function S: { _linuxbr_drive S: "$@"; }
function T: { _linuxbr_drive T: "$@"; }
function U: { _linuxbr_drive U: "$@"; }
function V: { _linuxbr_drive V: "$@"; }
function W: { _linuxbr_drive W: "$@"; }
function X: { _linuxbr_drive X: "$@"; }
function Y: { _linuxbr_drive Y: "$@"; }
function Z: { _linuxbr_drive Z: "$@"; }

function c: { _linuxbr_drive C: "$@"; }
function d: { _linuxbr_drive D: "$@"; }
function e: { _linuxbr_drive E: "$@"; }
function f: { _linuxbr_drive F: "$@"; }
function g: { _linuxbr_drive G: "$@"; }
function h: { _linuxbr_drive H: "$@"; }
function i: { _linuxbr_drive I: "$@"; }
function j: { _linuxbr_drive J: "$@"; }
function k: { _linuxbr_drive K: "$@"; }
function l: { _linuxbr_drive L: "$@"; }
function m: { _linuxbr_drive M: "$@"; }
function n: { _linuxbr_drive N: "$@"; }
function o: { _linuxbr_drive O: "$@"; }
function p: { _linuxbr_drive P: "$@"; }
function q: { _linuxbr_drive Q: "$@"; }
function r: { _linuxbr_drive R: "$@"; }
function s: { _linuxbr_drive S: "$@"; }
function t: { _linuxbr_drive T: "$@"; }
function u: { _linuxbr_drive U: "$@"; }
function v: { _linuxbr_drive V: "$@"; }
function w: { _linuxbr_drive W: "$@"; }
function x: { _linuxbr_drive X: "$@"; }
function y: { _linuxbr_drive Y: "$@"; }
function z: { _linuxbr_drive Z: "$@"; }

_linuxbr_windows_command() { /usr/bin/python3 /usr/lib/linuxbr-drive-manager/windows_commands.py "$@"; }
# Keep the original Linux command available through `command name`.
function dir { _linuxbr_windows_command dir "$@"; }
function cls { _linuxbr_windows_command cls "$@"; }
function copy { _linuxbr_windows_command copy "$@"; }
function move { _linuxbr_windows_command move "$@"; }
function del { _linuxbr_windows_command del "$@"; }
function rd { _linuxbr_windows_command rd "$@"; }
function md { _linuxbr_windows_command md "$@"; }
function type { _linuxbr_windows_command type "$@"; }
function explorer { _linuxbr_windows_command explorer "$@"; }
function ipconfig { _linuxbr_windows_command ipconfig "$@"; }
function tasklist { _linuxbr_windows_command tasklist "$@"; }
function where { _linuxbr_windows_command where "$@"; }
function bat {
    (( $# == 1 )) || { printf 'Use bat "C:/pasta/arquivo.bat".\n' >&2; return 2; }
    local target=$1
    target=${target//\\//}
    if [[ $target =~ ^[A-Za-z]: ]]; then target=$(_linuxbr_terminal_helper resolve "$target") || return; fi
    /usr/bin/linuxbr-windows "$target"
}
function comandos-windows {
    printf '%s\n' 'Comandos: dir [/s] [/b] [/a], cls, copy [/y], move [/y], del, rd, md, type, explorer, ipconfig, tasklist, where, bat.' \
      'Use aspas e barras normais: copy "C:/Minha pasta/a.txt" "D:/Backup/a.txt".' \
      'copy/move perguntam antes de substituir; del pergunta antes de apagar; rd remove apenas pastas vazias.' \
      'BAT/CMD abre a confirmação do ambiente Windows; para editar use Abrir com > Editor de texto.' \
      'Este terminal usa sintaxe Bash; comandos nativos continuam disponíveis, por exemplo: command dir.'
}
