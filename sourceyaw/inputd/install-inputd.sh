#!/bin/sh
# The strafe trainer's input service moved to the Strafe Trainer module (strafe-trainer/inputd/) in
# Phase 13. Source Yaw 1.10 and older print this file's URL for removing the service, so removing
# still works from here:
#   curl -fsSL https://raw.githubusercontent.com/Soulmanyes/movement-kit/main/sourceyaw/inputd/install-inputd.sh | sudo sh -s remove
# To install it, use the Strafe Trainer section in the hub (it shows the command).
set -eu
if [ "${1:-}" != "remove" ]; then
    echo "The input service is part of the Strafe Trainer module now: install it from its section in the hub." >&2
    exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "Run this with sudo: sudo sh $0 remove" >&2
    exit 1
fi
systemctl disable --now sourceyaw-inputd.socket 2>/dev/null || true
systemctl stop sourceyaw-inputd.service 2>/dev/null || true
rm -f /etc/systemd/system/sourceyaw-inputd.socket /etc/systemd/system/sourceyaw-inputd.service
rm -f /usr/local/lib/sourceyaw/sourceyaw-inputd.py /etc/sourceyaw-inputd.conf
rmdir /usr/local/lib/sourceyaw 2>/dev/null || true
systemctl daemon-reload
echo "Removed the strafe trainer's input service."
