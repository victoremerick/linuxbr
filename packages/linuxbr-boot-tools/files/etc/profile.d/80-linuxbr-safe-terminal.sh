#!/bin/sh
# Authentication is completed by login before this interactive profile runs.
case "$-" in *i*) ;; *) return ;; esac
[ -n "${BASH_VERSION:-}" ] || return
case " $(/usr/bin/cat /proc/cmdline) " in
    *" linuxbr.mode=safe-terminal "*) exec /bin/bash --noprofile --rcfile /usr/share/linuxbr/bashrc -i ;;
esac
