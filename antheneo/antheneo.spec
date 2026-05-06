# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Antheneo Browser
# Usage: pyinstaller antheneo.spec

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
ROOT = Path(SPECPATH)

# ── Collect Qt WebEngine resources ────────────────────────────────────────
# pyinstaller-hooks-contrib handles most of PyQt6/WebEngine automatically,
# but we explicitly add resources to be safe.
qt_datas = collect_data_files('PyQt6', includes=[
    'Qt6/resources/*',
    'Qt6/translations/qtwebengine_locales/*',
])

app_datas = [
    (str(ROOT / 'blocklists'), 'blocklists'),
    (str(ROOT / 'assets'),     'assets'),
]

# ── Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'browser.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=app_datas + qt_datas,
    hiddenimports=[
        # Qt modules that may not be auto-detected
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebChannel',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtNetwork',
        # Our own modules
        'ui.themes',
        'ui.hacker_panel',
        'core.privacy',
        'version',
        # stdlib used at runtime
        'socket',
        'subprocess',
        'json',
        'urllib.request',
        'urllib.error',
        'urllib.parse',
        'pathlib',
        'threading',
        'datetime',
        're',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Remove unused large packages to reduce bundle size
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'tkinter', 'test', 'unittest',
        'email', 'html.parser',
        'distutils', 'setuptools', 'pkg_resources',
        'IPython', 'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ ───────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE ───────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,     # onedir mode — better for Qt WebEngine
    name='antheneo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                  # compress if UPX available
    upx_exclude=[
        # Don't compress Qt libs — can break them
        'Qt6WebEngine*', 'Qt6Core*', 'Qt6Gui*',
        'vcruntime*.dll', 'api-ms-win*.dll',
    ],
    console=False,             # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,    # set to Apple Developer ID for macOS signing
    entitlements_file=None,
    # Windows icon
    icon=str(ROOT / 'assets' / 'icon.ico') if sys.platform == 'win32' else None,
)

# ── COLLECT (onedir bundle) ───────────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['Qt6WebEngine*', 'Qt6Core*', 'Qt6Gui*'],
    name='antheneo',
)

# macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Antheneo Browser.app',
        icon=str(ROOT / 'assets' / 'icon.icns'),
        bundle_identifier='com.antheneo.browser',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
            'CFBundleURLTypes': [{
                'CFBundleURLName': 'Web URL',
                'CFBundleURLSchemes': ['http', 'https'],
            }],
        },
    )
