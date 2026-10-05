#!/usr/bin/env bash
# Install udev rule so non-root users can access the Siglent oscilloscope over USB.
set -euo pipefail

RULE="99-siglent-usbtmc.rules"
DEST="/etc/udev/rules.d/$RULE"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (sudo)." >&2
    echo "Usage: sudo ./install-udev.sh" >&2
    exit 1
fi

install -m 0644 "$RULE" "$DEST"
echo "Installed $DEST"
udevadm control --reload-rules
udevadm trigger
echo "Rules reloaded. Unplug/replug the oscilloscope if it is not detected."
