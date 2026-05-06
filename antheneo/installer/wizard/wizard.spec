# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Antheneo Installation Wizard
# The wizard is compiled as a SINGLE-FILE executable that contains
# the entire browser bundle (browser_bundle.zip) inside it.
#
# Build process (handled automatically by build.py):
#   1. PyInstaller compiles the browser → dist/antheneo/
#   2. build.py zips dist/antheneo/ → dist/browser_bundle.zip
#   3. This spec compiles the wizard with the zip as embedded data
#   4. Output: dist/Antheneo-Setup-1.0.0[.exe]

import sys
from pathlib import Path

WIZARD_DIR  = Path(SPECPATH)
ROOT        = WIZARD_DIR.parent.parent        # antheneo/
BUNDLE_ZIP  = ROOT / "dist" / "browser_bundle.zip"
ASSETS_DIR  = ROOT / "assets"

block_cipher = None

a = Analysis(
    [str(WIZARD_DIR / "installer_wizard.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Embedded browser bundle — extracted to install location at runtime
        (str(BUNDLE_ZIP), "."),
        # Wizard assets (icon shown in taskbar/title bar during install)
        (str(ASSETS_DIR), "assets"),
    ],
    hiddenimports=[
        "PyQt6.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "zipfile",
        "shutil",
        "subprocess",
        "platform",
        "pathlib",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Wizard does NOT need WebEngine — keep it tiny
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebChannel",
        "matplotlib", "numpy", "pandas",
        "tkinter", "test", "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── ONEFILE: single executable — the ideal "double-click to install" ──────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="Antheneo-Setup-1.0.0",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,        # no console window
    onefile=True,
    icon=str(ASSETS_DIR / "icon.ico") if sys.platform == "win32" else None,
)
