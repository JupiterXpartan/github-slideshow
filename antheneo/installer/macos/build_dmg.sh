#!/usr/bin/env bash
# Antheneo Browser — macOS .app bundle + DMG builder
# Run from the antheneo/ project root AFTER build.py completes.
# Requirements: macOS with Xcode CLI tools, create-dmg (brew install create-dmg)
set -euo pipefail

VERSION="${1:-1.0.0}"
APP_NAME="Antheneo Browser"
BUNDLE="dist/${APP_NAME}.app"
DIST="dist/antheneo"
DMG_OUT="dist/Antheneo-${VERSION}.dmg"
ICON="assets/icon.icns"

if [ ! -d "$DIST" ]; then
    echo "ERROR: $DIST not found. Run build.py first."
    exit 1
fi

echo "Building macOS .app bundle…"

# ── .app structure ────────────────────────────────────────────────────────
rm -rf "$BUNDLE"
mkdir -p "${BUNDLE}/Contents/MacOS"
mkdir -p "${BUNDLE}/Contents/Resources"

# Copy PyInstaller output
cp -a "${DIST}/." "${BUNDLE}/Contents/MacOS/"

# Info.plist
cat > "${BUNDLE}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>             <string>Antheneo Browser</string>
    <key>CFBundleDisplayName</key>      <string>Antheneo Browser</string>
    <key>CFBundleIdentifier</key>       <string>com.antheneo.browser</string>
    <key>CFBundleVersion</key>          <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key><string>${VERSION}</string>
    <key>CFBundlePackageType</key>      <string>APPL</string>
    <key>CFBundleSignature</key>        <string>ANTH</string>
    <key>CFBundleExecutable</key>       <string>antheneo</string>
    <key>CFBundleIconFile</key>         <string>icon</string>
    <key>NSHighResolutionCapable</key>  <true/>
    <key>NSRequiresAquaSystemAppearance</key> <false/>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key>    <string>Web URL</string>
            <key>CFBundleURLSchemes</key>
            <array><string>http</string><string>https</string></array>
        </dict>
    </dict>
    </array>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key><true/>
    </dict>
</dict>
</plist>
PLIST

# Copy icon
if [ -f "$ICON" ]; then
    cp "$ICON" "${BUNDLE}/Contents/Resources/icon.icns"
elif [ -f "assets/icon.png" ]; then
    # Fallback: convert PNG to icns using sips
    sips -s format icns "assets/icon.png" --out "${BUNDLE}/Contents/Resources/icon.icns" 2>/dev/null || true
fi

echo "  .app bundle → ${BUNDLE}"

# ── Ad-hoc code signing ───────────────────────────────────────────────────
if command -v codesign &>/dev/null; then
    echo "Signing (ad-hoc)…"
    codesign --force --deep --sign - "${BUNDLE}" 2>/dev/null && echo "  Signed (ad-hoc)" || echo "  Signing skipped"
fi

# ── DMG ───────────────────────────────────────────────────────────────────
echo "Creating DMG…"
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "Antheneo Browser ${VERSION}" \
        --background "assets/dmg_background.png" \
        --window-size 660 420 \
        --icon-size 128 \
        --icon "${APP_NAME}.app" 180 200 \
        --app-drop-link 480 200 \
        --hide-extension "${APP_NAME}.app" \
        "${DMG_OUT}" \
        "dist/"
else
    # Fallback: plain hdiutil DMG
    hdiutil create -volname "Antheneo Browser ${VERSION}" \
        -srcfolder "dist/${APP_NAME}.app" \
        -ov -format UDZO "${DMG_OUT}"
fi

echo ""
echo "✔ macOS release ready:"
echo "  App bundle: ${BUNDLE}"
echo "  Disk image: ${DMG_OUT}"
echo ""
echo "Distribute ${DMG_OUT} to users."
echo "They drag 'Antheneo Browser.app' to their Applications folder."
