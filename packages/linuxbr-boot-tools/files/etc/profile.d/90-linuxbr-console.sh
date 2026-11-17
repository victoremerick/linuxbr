# Present the configuration menu once per authenticated local text login.
case "$-" in
    *i*)
        if [ -t 0 ] && [ -t 1 ] && [ -z "${SSH_CONNECTION:-}" ]; then
            case "$(tty)" in
                /dev/tty[1-9]|/dev/tty[1-9][0-9])
                    /usr/bin/linuxbr-console --server-login
                    ;;
            esac
        fi
        ;;
esac
