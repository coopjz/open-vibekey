#!/bin/sh
# Persistent AU05/uinput access for the invoking desktop user.
set -eu
if [ "$(id -u)" -ne 0 ] || [ -z "${SUDO_USER:-}" ] || [ "$SUDO_USER" = root ]; then
    echo 'Run this script with sudo from your desktop user.' >&2
    exit 1
fi
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
id "$SUDO_USER" >/dev/null
getent group vibekey-input >/dev/null || addgroup --system vibekey-input
usermod -aG vibekey-input "$SUDO_USER"
install -m 644 "$task_root/packaging/70-vibekey.rules" /etc/udev/rules.d/70-vibekey.rules
install -m 644 "$task_root/packaging/vibekey.conf" /etc/modules-load.d/vibekey.conf
modprobe uinput
udevadm control --reload-rules
udevadm trigger --subsystem-match=misc --sysname-match=uinput
# Keep this login usable until the newly added group takes effect at next login.
if command -v setfacl >/dev/null; then
    setfacl -m "u:$SUDO_USER:rw" /dev/uinput
fi
echo 'Persistent device access configured. Log out/in to activate group membership.'
