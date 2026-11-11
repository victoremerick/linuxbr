# Keep Snap desktop entries visible when snapd is installed during this session.
XDG_DATA_DIRS=${XDG_DATA_DIRS:-/usr/local/share:/usr/share}
case ":${XDG_DATA_DIRS}:" in
    *:/var/lib/snapd/desktop:*) ;;
    *) XDG_DATA_DIRS="$XDG_DATA_DIRS:/var/lib/snapd/desktop" ;;
esac
export XDG_DATA_DIRS
