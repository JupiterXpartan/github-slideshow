#!/usr/bin/env bash
# Antheneo Browser — Uninstaller (Linux)
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    exec sudo "$0" "$@"
fi

echo "Removing Antheneo Browser…"

rm -rf /opt/antheneo
rm -f  /usr/local/bin/antheneo
rm -f  /usr/share/applications/antheneo.desktop
rm -f  /usr/share/icons/hicolor/256x256/apps/antheneo.png

command -v update-desktop-database &>/dev/null && \
    update-desktop-database /usr/share/applications 2>/dev/null || true

# Remove user data (optional — ask first)
read -r -p "Remove user settings (~/.antheneo)? [y/N] " ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
    rm -rf ~/.antheneo
    echo "User data removed."
fi

echo "Antheneo has been uninstalled."
