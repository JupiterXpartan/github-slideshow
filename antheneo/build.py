#!/usr/bin/env python3
"""
Antheneo Browser — Master Build Script
Compiles the browser with PyInstaller and creates a platform installer.

Usage:
    python build.py              # full build for current platform
    python build.py --clean      # remove dist/ and build/ first
    python build.py --icon-only  # regenerate icons only
    python build.py --no-installer  # skip installer creation
"""

import sys
import os
import shutil
import subprocess
import argparse
import platform
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"

# ── ANSI colours ──────────────────────────────────────────────────────────
C = "\033[0;36m"; G = "\033[0;32m"; R = "\033[0;31m"; W = "\033[0;33m"; N = "\033[0m"

def info(msg):  print(f"{C}[build]{N} {msg}")
def ok(msg):    print(f"{G}  ✔{N}  {msg}")
def warn(msg):  print(f"{W}  ⚠{N}  {msg}")
def err(msg):   print(f"{R}  ✘{N}  {msg}"); sys.exit(1)

def run(*cmd, **kwargs):
    """Run a command, streaming output, and raise on failure."""
    info(f"Running: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        err(f"Command failed with exit code {result.returncode}")
    return result


# ── Step 1: Dependency check ──────────────────────────────────────────────

def check_deps():
    info("Checking dependencies…")
    missing = []
    for pkg in ["PyInstaller", "PyQt6", "PyQt6-WebEngine"]:
        try:
            __import__(pkg.replace("-", "_").lower().split(".")[0])
        except ImportError:
            missing.append(pkg)

    if missing:
        warn(f"Missing packages: {', '.join(missing)}")
        info("Installing…")
        run(sys.executable, "-m", "pip", "install", *missing)
    ok("All dependencies present")

    # pyinstaller-hooks-contrib improves Qt WebEngine support
    try:
        import _pyinstaller_hooks_contrib  # noqa: F401
    except ImportError:
        info("Installing pyinstaller-hooks-contrib for better Qt support…")
        run(sys.executable, "-m", "pip", "install", "pyinstaller-hooks-contrib")

    # UPX (optional — compresses the binary)
    if shutil.which("upx"):
        ok("UPX found — binary compression enabled")
    else:
        warn("UPX not found — binaries will not be compressed (optional)")
        warn("  Linux: sudo apt install upx | Windows: https://upx.github.io")


# ── Step 2: Icon generation ───────────────────────────────────────────────

def generate_icons():
    info("Generating application icons…")
    icon_script = ROOT / "assets" / "generate_icon.py"
    icon_png = ROOT / "assets" / "icon.png"

    if not icon_png.exists():
        try:
            import PIL  # noqa: F401
            run(sys.executable, str(icon_script))
        except ImportError:
            warn("Pillow not installed — skipping raster icons.")
            warn("  Install with: pip install Pillow")
            info("Generating SVG icon only…")
            run(sys.executable, str(icon_script))
    else:
        ok("Icons already generated (use --clean to regenerate)")


# ── Step 3: Clean ─────────────────────────────────────────────────────────

def clean():
    info("Cleaning previous build artifacts…")
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            ok(f"Removed {d}")


# ── Step 4: PyInstaller ───────────────────────────────────────────────────

def run_pyinstaller():
    info("Running PyInstaller…")
    spec = ROOT / "antheneo.spec"
    run(
        sys.executable, "-m", "PyInstaller",
        str(spec),
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--noconfirm",
        cwd=str(ROOT),
    )

    bundle = DIST / "antheneo"
    if not bundle.exists():
        err(f"Expected bundle not found at {bundle}")
    ok(f"Bundle created: {bundle}")
    return bundle


# ── Step 5: Platform installer ────────────────────────────────────────────

def build_linux_deb(version: str):
    info("Building Linux .deb package…")
    deb_script = ROOT / "installer" / "linux" / "build_deb.sh"
    if not deb_script.exists():
        warn("build_deb.sh not found — skipping .deb build")
        return
    if not shutil.which("dpkg-deb"):
        warn("dpkg-deb not found — skipping .deb (install dpkg-dev)")
        _build_tarball(version)
        return
    run("bash", str(deb_script), version, cwd=str(ROOT))
    ok("Debian package built")


def _build_tarball(version: str):
    info("Falling back to tarball distribution…")
    tar_name = f"antheneo-{version}-linux-x86_64.tar.gz"
    tar_path = DIST / tar_name
    import tarfile
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(DIST / "antheneo", arcname="antheneo")
        # Include install script
        install_sh = ROOT / "installer" / "linux" / "install.sh"
        if install_sh.exists():
            tar.add(install_sh, arcname="install.sh")
        desktop = ROOT / "installer" / "linux" / "antheneo.desktop"
        if desktop.exists():
            tar.add(desktop, arcname="antheneo.desktop")
    ok(f"Tarball: {tar_path}")
    _print_linux_instructions(tar_name, version)


def _print_linux_instructions(archive: str, version: str):
    print(f"""
{G}Linux distribution:{N}
  Archive:  dist/{archive}
  Install:  tar xf {archive} && sudo bash install.sh
""")


def build_windows_installer(version: str):
    info("Preparing Windows installer…")
    nsis = shutil.which("makensis") or shutil.which("makensis.exe")
    if not nsis:
        warn("makensis not found — NSIS installer script is ready at:")
        warn("  installer/windows/installer.nsi")
        warn("  Install NSIS on Windows and run: makensis installer.nsi")
        _build_windows_zip(version)
        return
    nsi = ROOT / "installer" / "windows" / "installer.nsi"
    run(nsis, str(nsi), cwd=str(ROOT))
    ok("Windows installer built")


def _build_windows_zip(version: str):
    import zipfile
    zip_name = f"Antheneo-{version}-Windows.zip"
    zip_path = DIST / zip_name
    bundle = DIST / "antheneo"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in bundle.rglob("*"):
            zf.write(file, file.relative_to(DIST))
    ok(f"Windows zip: {zip_path}")


def build_macos_dmg(version: str):
    info("Building macOS DMG…")
    script = ROOT / "installer" / "macos" / "build_dmg.sh"
    run("bash", str(script), version, cwd=str(ROOT))
    ok("macOS DMG built")


# ── Step 6: Summary ───────────────────────────────────────────────────────

def print_summary(plat: str, version: str):
    print(f"""
{C}╔═══════════════════════════════════════════════════╗
║  Antheneo Browser v{version} — Build Complete       ║
╚═══════════════════════════════════════════════════╝{N}

  Platform:   {plat}
  Output dir: dist/

""")
    if plat == "linux":
        deb = next(DIST.glob("*.deb"), None)
        tar = next(DIST.glob("*.tar.gz"), None)
        if deb:
            print(f"  {G}Debian package:{N}  {deb.name}")
            print(f"  Install:   sudo dpkg -i dist/{deb.name}")
        if tar:
            print(f"  {G}Tarball:{N}          {tar.name}")
            print(f"  Install:   tar xf dist/{tar.name} && sudo bash install.sh")
    elif plat == "windows":
        exe = next(DIST.glob("*.exe"), None)
        _zip = next(DIST.glob("*.zip"), None)
        if exe:
            print(f"  {G}Installer:{N}  {exe.name}  (run as administrator)")
        if _zip:
            print(f"  {G}Portable:{N}   {_zip.name}  (extract and run antheneo.exe)")
    elif plat == "darwin":
        dmg = next(DIST.glob("*.dmg"), None)
        if dmg:
            print(f"  {G}Disk image:{N}  {dmg.name}")
            print("  Install:   Open DMG → drag to Applications")
    print()


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build Antheneo Browser")
    parser.add_argument("--clean",          action="store_true", help="Remove dist/ and build/ first")
    parser.add_argument("--icon-only",      action="store_true", help="Regenerate icons and exit")
    parser.add_argument("--no-installer",   action="store_true", help="Skip installer creation")
    parser.add_argument("--version",        default="1.0.0",     help="Version string (default: 1.0.0)")
    args = parser.parse_args()

    version = args.version
    plat = platform.system().lower()   # 'linux', 'windows', 'darwin'

    print(f"""
{C}╔═══════════════════════════════════════════════════╗
║   Antheneo Browser — Build System v{version}        ║
║   Platform: {plat:<37}║
╚═══════════════════════════════════════════════════╝{N}
""")

    if args.clean:
        clean()

    generate_icons()

    if args.icon_only:
        ok("Icons generated. Exiting.")
        return

    check_deps()
    run_pyinstaller()

    if not args.no_installer:
        if plat == "linux":
            build_linux_deb(version)
        elif plat == "windows":
            build_windows_installer(version)
        elif plat == "darwin":
            build_macos_dmg(version)
        else:
            warn(f"Unknown platform '{plat}' — skipping installer creation")

    print_summary(plat, version)


if __name__ == "__main__":
    main()
