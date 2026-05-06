#!/usr/bin/env bash
# Build a Debian/Ubuntu .deb package from a PyInstaller dist/antheneo directory.
# Run this from the antheneo/ project root AFTER running build.py.
#
# Usage:  bash installer/linux/build_deb.sh [version]
set -euo pipefail

VERSION="${1:-1.0.0}"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
PKG="antheneo_${VERSION}_${ARCH}"
DIST="$(pwd)/dist/antheneo"
DEB_ROOT="/tmp/${PKG}"

if [ ! -d "$DIST" ]; then
    echo "ERROR: $DIST not found. Run build.py first."
    exit 1
fi

echo "Building .deb package: ${PKG}.deb"

# ── Package filesystem layout ─────────────────────────────────────────────
rm -rf "$DEB_ROOT"
mkdir -p "${DEB_ROOT}/opt/antheneo"
mkdir -p "${DEB_ROOT}/usr/share/applications"
mkdir -p "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${DEB_ROOT}/usr/share/doc/antheneo"
mkdir -p "${DEB_ROOT}/usr/bin"
mkdir -p "${DEB_ROOT}/DEBIAN"

# Copy the compiled bundle
cp -a "${DIST}/." "${DEB_ROOT}/opt/antheneo/"

# Launcher wrapper (handles working directory)
cat > "${DEB_ROOT}/usr/bin/antheneo" <<'LAUNCHER'
#!/bin/sh
cd /opt/antheneo
exec ./antheneo "$@"
LAUNCHER
chmod 755 "${DEB_ROOT}/usr/bin/antheneo"

# Desktop entry
cp installer/linux/antheneo.desktop "${DEB_ROOT}/usr/share/applications/"

# Icon
if [ -f "assets/icon.png" ]; then
    cp assets/icon.png "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/antheneo.png"
    cp assets/icon.png "${DEB_ROOT}/opt/antheneo/assets/icon.png" 2>/dev/null || true
fi

# Copyright / changelog
cat > "${DEB_ROOT}/usr/share/doc/antheneo/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Antheneo Browser
Upstream-Contact: hello@antheneo.io
Source: https://antheneo.io

Files: *
Copyright: © 2025 Antheneo
License: Proprietary
 This software is proprietary. Redistribution without written
 permission from Antheneo is not permitted.
EOF

# ── DEBIAN/control ────────────────────────────────────────────────────────
INSTALLED_SIZE=$(du -sk "${DEB_ROOT}/opt/antheneo" | cut -f1)

cat > "${DEB_ROOT}/DEBIAN/control" <<EOF
Package: antheneo
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: Antheneo Team <hello@antheneo.io>
Installed-Size: ${INSTALLED_SIZE}
Depends: libglib2.0-0, libx11-6, libxext6, libxrender1, libdbus-1-3
Recommends: whois
Section: web
Priority: optional
Homepage: https://antheneo.io
Description: Privacy-first browser with ethical hacking tools
 Antheneo is a dark-themed desktop browser built on QtWebEngine.
 It blocks ads/trackers, upgrades HTTP connections to HTTPS,
 strips tracking parameters, and randomizes browser fingerprints.
 .
 Hacker Mode adds a built-in panel with DNS lookup, port scanner,
 HTTP header inspector, JS console, and recon tools — for
 authorized security testing only.
EOF

# ── DEBIAN/postinst ───────────────────────────────────────────────────────
cat > "${DEB_ROOT}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
chmod -R 755 /opt/antheneo
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
fi
EOF
chmod 755 "${DEB_ROOT}/DEBIAN/postinst"

# ── DEBIAN/prerm ──────────────────────────────────────────────────────────
cat > "${DEB_ROOT}/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi
EOF
chmod 755 "${DEB_ROOT}/DEBIAN/prerm"

# ── Build ─────────────────────────────────────────────────────────────────
OUT_DEB="dist/${PKG}.deb"
dpkg-deb --build --root-owner-group "${DEB_ROOT}" "${OUT_DEB}"
echo ""
echo "✔ Package built: ${OUT_DEB}"
echo ""
echo "Install with:  sudo dpkg -i ${OUT_DEB}"
echo "Remove  with:  sudo apt remove antheneo"
