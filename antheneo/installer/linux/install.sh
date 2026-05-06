#!/usr/bin/env bash
# Antheneo Browser — Universal Linux Installer
# Works on Debian/Ubuntu (dpkg) and other distros (tarball fallback).
# Run as root or with sudo.
set -euo pipefail

VERSION="1.0.0"
INSTALL_DIR="/opt/antheneo"
BIN_LINK="/usr/local/bin/antheneo"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons/hicolor/256x256/apps"

# ── Colour helpers ────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[Antheneo]${NC} $*"; }
ok()    { echo -e "${GREEN}  ✔${NC} $*"; }
err()   { echo -e "${RED}  ✘${NC} $*" >&2; }

# ── Root check ────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    echo "Re-running with sudo…"
    exec sudo "$0" "$@"
fi

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Antheneo Browser v${VERSION} Installer      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$(cd "${SCRIPT_DIR}/../../dist/antheneo" 2>/dev/null && pwd)" || {
    err "dist/antheneo not found. Run build.py first."
    exit 1
}

# ── Install files ─────────────────────────────────────────────────────────
info "Installing to ${INSTALL_DIR}…"
rm -rf "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
cp -a "${DIST_DIR}/." "${INSTALL_DIR}/"
chmod -R 755 "${INSTALL_DIR}"
ok "Application files installed"

# ── Symlink ───────────────────────────────────────────────────────────────
cat > "${BIN_LINK}" <<WRAPPER
#!/bin/sh
cd /opt/antheneo
exec ./antheneo "\$@"
WRAPPER
chmod 755 "${BIN_LINK}"
ok "Launcher created at ${BIN_LINK}"

# ── Desktop entry ─────────────────────────────────────────────────────────
cp "${SCRIPT_DIR}/antheneo.desktop" "${DESKTOP_DIR}/" 2>/dev/null || true
ok "Desktop entry installed"

# ── Icon ──────────────────────────────────────────────────────────────────
if [ -f "${INSTALL_DIR}/assets/icon.png" ]; then
    mkdir -p "${ICON_DIR}"
    cp "${INSTALL_DIR}/assets/icon.png" "${ICON_DIR}/antheneo.png"
    ok "Icon installed"
fi

# ── Update caches ─────────────────────────────────────────────────────────
command -v update-desktop-database &>/dev/null && \
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
command -v gtk-update-icon-cache &>/dev/null && \
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true

# ── Optional: whois for Recon tools ──────────────────────────────────────
if ! command -v whois &>/dev/null; then
    info "Installing optional 'whois' tool…"
    apt-get install -y whois 2>/dev/null || \
    dnf install -y whois 2>/dev/null || \
    pacman -S --noconfirm whois 2>/dev/null || \
    info "Could not auto-install whois — install manually for full Recon features."
fi

echo ""
echo -e "${GREEN}✔ Antheneo Browser installed successfully!${NC}"
echo ""
echo "  Launch from your app menu, or run:  antheneo"
echo "  Uninstall:  sudo bash ${SCRIPT_DIR}/uninstall.sh"
echo ""
