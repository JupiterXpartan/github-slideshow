#!/usr/bin/env python3
"""
Antheneo Browser — Master Build Script

Two-stage build:
  Stage 1 → Compile the browser        (PyInstaller → dist/antheneo/)
  Stage 2 → Zip the browser bundle     (dist/browser_bundle.zip)
  Stage 3 → Compile the wizard         (PyInstaller onefile → dist/Antheneo-Setup-<ver>)

The final deliverable is a single installer executable that end-users
double-click to launch the GUI installation wizard.

Usage:
    python build.py                   # full build
    python build.py --clean           # remove dist/ and build/ first
    python build.py --icon-only       # regenerate icons only, then exit
    python build.py --browser-only    # stages 1–2, skip wizard
    python build.py --wizard-only     # stage 3 only (browser must be pre-built)
    python build.py --version 1.2.0   # override version string
"""

import sys
import os
import shutil
import subprocess
import zipfile
import argparse
import platform
from pathlib import Path

ROOT    = Path(__file__).parent
DIST    = ROOT / "dist"
BUILD   = ROOT / "build"
ASSETS  = ROOT / "assets"
WIZARD  = ROOT / "installer" / "wizard"

# ── ANSI colours ──────────────────────────────────────────────────────────
C = "\033[0;36m"; G = "\033[0;32m"; R = "\033[0;31m"
W = "\033[0;33m"; B = "\033[1m";    N = "\033[0m"

def info(m):  print(f"\n{C}{B}[build]{N} {m}")
def ok(m):    print(f"  {G}✔{N}  {m}")
def warn(m):  print(f"  {W}⚠{N}  {m}")
def step(m):  print(f"  {C}→{N}  {m}")
def err(m):   print(f"  {R}✘{N}  {m}"); sys.exit(1)

def run(*cmd, cwd=None):
    step(" ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=cwd or ROOT)
    if r.returncode != 0:
        err(f"Command exited with code {r.returncode}")


# ── Step helpers ──────────────────────────────────────────────────────────

def clean():
    info("Cleaning previous build artifacts")
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            ok(f"Removed {d.relative_to(ROOT)}")


def check_deps():
    info("Checking Python dependencies")
    pkgs = [
        ("PyInstaller",                 "pyinstaller"),
        ("pyinstaller_hooks_contrib",   "pyinstaller-hooks-contrib"),
        ("PIL",                         "Pillow"),
        ("PyQt6",                       "PyQt6"),
    ]
    missing = []
    for module, pkg in pkgs:
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if missing:
        warn(f"Missing: {', '.join(missing)} — installing…")
        run(sys.executable, "-m", "pip", "install", *missing, "-q")
    ok("All dependencies satisfied")

    if shutil.which("upx"):
        ok("UPX found — binary compression will be applied")
    else:
        warn("UPX not found (optional). sudo apt install upx  or  https://upx.github.io")


def generate_icons(force: bool = False):
    info("Generating application icons")
    icon_png = ASSETS / "icon.png"
    icon_ico = ASSETS / "icon.ico"
    icon_svg = ASSETS / "icon.svg"

    if not force and icon_png.exists() and icon_ico.exists():
        ok("Icons already present (pass --clean to regenerate)")
        return

    gen_script = ASSETS / "generate_icon.py"
    try:
        import PIL  # noqa: F401
        run(sys.executable, str(gen_script))
        ok("Raster + SVG icons generated")
    except ImportError:
        warn("Pillow not installed — generating SVG icon only")
        run(sys.executable, str(gen_script))

    if not icon_png.exists():
        # Create a minimal placeholder so PyInstaller doesn't fail
        icon_png.write_bytes(b"")
        warn("icon.png placeholder created (install Pillow for a real icon)")


# ── Stage 1: Compile browser ──────────────────────────────────────────────

def build_browser():
    info("Stage 1 — Compiling browser (PyInstaller)")
    spec = ROOT / "antheneo.spec"
    run(
        sys.executable, "-m", "PyInstaller",
        str(spec),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "browser"),
        "--noconfirm",
        cwd=ROOT,
    )
    bundle = DIST / "antheneo"
    if not bundle.exists():
        err(f"Expected browser bundle at {bundle} — PyInstaller failed")
    ok(f"Browser bundle → {bundle.relative_to(ROOT)}")
    return bundle


# ── Stage 2: Zip the browser bundle ──────────────────────────────────────

def zip_browser(bundle: Path, version: str) -> Path:
    info("Stage 2 — Zipping browser bundle")
    zip_path = DIST / "browser_bundle.zip"
    files = [f for f in bundle.rglob("*") if f.is_file()]
    total = len(files)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for i, f in enumerate(files, 1):
            arcname = f.relative_to(bundle)
            zf.write(f, arcname)
            if i % 50 == 0 or i == total:
                pct = int(i / total * 100)
                print(f"\r    Zipping… {pct}% ({i}/{total})", end="", flush=True)
    print()

    size_mb = zip_path.stat().st_size / 1024**2
    ok(f"Bundle zip → {zip_path.relative_to(ROOT)}  ({size_mb:.1f} MB)")
    return zip_path


# ── Stage 3: Compile wizard ───────────────────────────────────────────────

def build_wizard(version: str) -> Path:
    info("Stage 3 — Compiling installation wizard (PyInstaller onefile)")

    # Patch version in wizard spec's output name dynamically via env
    env = os.environ.copy()
    env["ANTHENEO_VERSION"] = version

    spec = WIZARD / "wizard.spec"
    run(
        sys.executable, "-m", "PyInstaller",
        str(spec),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "wizard"),
        "--noconfirm",
        cwd=ROOT,
    )

    plat    = platform.system().lower()
    suffix  = ".exe" if plat == "windows" else ""
    out_exe = DIST / f"Antheneo-Setup-{version}{suffix}"

    # PyInstaller names it per the spec — find and rename if needed
    candidates = [
        DIST / f"Antheneo-Setup-1.0.0{suffix}",
        DIST / f"Antheneo-Setup-{version}{suffix}",
        DIST / f"antheneo-setup{suffix}",
    ]
    found = next((p for p in candidates if p.exists()), None)
    if found and found != out_exe:
        found.rename(out_exe)
    elif not out_exe.exists():
        matches = list(DIST.glob(f"*Setup*{suffix}")) + list(DIST.glob(f"*setup*{suffix}"))
        if matches:
            matches[0].rename(out_exe)
        else:
            err("Wizard executable not found after PyInstaller run")

    size_mb = out_exe.stat().st_size / 1024**2
    ok(f"Installer wizard → {out_exe.relative_to(ROOT)}  ({size_mb:.1f} MB)")
    return out_exe


# ── Summary ────────────────────────────────────────────────────────────────

def print_summary(exe: Path, version: str):
    plat = platform.system().lower()
    print(f"""
{C}{B}╔══════════════════════════════════════════════════════════════╗
║   Antheneo Browser v{version} — Build Complete                ║
╚══════════════════════════════════════════════════════════════╝{N}

  {G}Installer:{N}  {exe}

  {B}How to distribute:{N}
    Ship only this single file to end-users.
    They double-click it → the GUI wizard guides them through setup.

  {B}How to install:{N}""")

    if plat == "linux":
        print(f"    chmod +x {exe.name} && ./{exe.name}")
    elif plat == "windows":
        print(f"    Double-click  {exe.name}  (Run as Administrator)")
    elif plat == "darwin":
        print(f"    Double-click  {exe.name}")

    print(f"""
  {B}Wizard steps:{N}
    Welcome → License Agreement → Install Path → Options → Installing → Finish

  {B}What the wizard does:{N}
    • Extracts the bundled browser to the chosen directory
    • Creates desktop shortcut and application menu entry
    • Adds  antheneo  to PATH (Linux/macOS)
    • Registers in Add/Remove Programs (Windows)
    • Optionally launches the browser on completion
""")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build Antheneo Browser installer wizard"
    )
    parser.add_argument("--clean",        action="store_true", help="Remove dist/ and build/")
    parser.add_argument("--icon-only",    action="store_true", help="Regenerate icons and exit")
    parser.add_argument("--browser-only", action="store_true", help="Compile browser only (stages 1–2)")
    parser.add_argument("--wizard-only",  action="store_true", help="Compile wizard only (stage 3)")
    parser.add_argument("--version",      default="1.0.0",     help="Version string (default: 1.0.0)")
    args = parser.parse_args()

    version = args.version
    plat    = platform.system()

    print(f"""
{C}{B}╔══════════════════════════════════════════════════════════════╗
║   Antheneo Browser — Build System                            ║
║   Version: {version:<51}║
║   Platform: {plat:<50}║
╚══════════════════════════════════════════════════════════════╝{N}""")

    if args.clean:
        clean()

    generate_icons(force=args.clean)

    if args.icon_only:
        ok("Icons generated. Exiting.")
        return

    check_deps()
    DIST.mkdir(exist_ok=True)

    exe = None

    if not args.wizard_only:
        bundle  = build_browser()
        zip_path = zip_browser(bundle, version)
    else:
        zip_path = DIST / "browser_bundle.zip"
        if not zip_path.exists():
            err("browser_bundle.zip not found. Run without --wizard-only first.")

    if not args.browser_only:
        exe = build_wizard(version)

    if exe:
        print_summary(exe, version)
    else:
        info("Browser stages complete.")
        ok(f"Bundle zip: {zip_path.relative_to(ROOT)}")
        ok("Run  python build.py --wizard-only  to compile the installer wizard.")


if __name__ == "__main__":
    main()
