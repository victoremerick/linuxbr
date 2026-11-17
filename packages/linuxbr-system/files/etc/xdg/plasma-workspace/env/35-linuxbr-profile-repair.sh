#!/bin/sh
# Apply any repair requested by this user before Plasma reads the preferences.
if [ -f "${XDG_STATE_HOME:-$HOME/.local/state}/linuxbr/profile-repair/pending.json" ]; then
    /usr/bin/python3 /usr/lib/linuxbr-system/profile_repair.py apply >&2 || true
fi
