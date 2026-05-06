#!/usr/bin/env python3
"""
Antheneo Browser — GUI Installation Wizard
A self-contained installation wizard compiled as a single executable.
Bundles the browser archive internally; extracts and installs on run.
"""

import sys
import os
import shutil
import zipfile
import platform
import subprocess
import json
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPropertyAnimation,
    QEasingCurve, QPoint,
)
from PyQt6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox,
    QTextEdit, QProgressBar, QFrame, QScrollArea, QStackedWidget,
    QSizePolicy, QSpacerItem,
)
from PyQt6.QtGui import (
    QFont, QFontDatabase, QColor, QPainter, QLinearGradient,
    QPen, QBrush, QPixmap, QIcon, QPalette,
)

# ── Version info (inline for standalone build) ─────────────────────────────
VERSION   = "1.0.0"
APP_NAME  = "Antheneo Browser"
APP_ID    = "com.antheneo.browser"
COPYRIGHT = "© 2025 Antheneo"

PLAT = platform.system().lower()   # 'linux' | 'windows' | 'darwin'

# ── Default install paths ──────────────────────────────────────────────────
if PLAT == "windows":
    DEFAULT_INSTALL = Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Antheneo"
elif PLAT == "darwin":
    DEFAULT_INSTALL = Path("/Applications/Antheneo Browser.app/Contents/MacOS")
else:
    DEFAULT_INSTALL = Path("/opt/antheneo")

# ── Locate browser bundle (zip or directory) ───────────────────────────────
def _find_bundle() -> Path | None:
    """
    Returns the path to the browser bundle.
    - When frozen: looks for browser_bundle.zip in _MEIPASS
    - When running from source: looks for ../../dist/antheneo relative to this file
    """
    if getattr(sys, "frozen", False):
        bundle_zip = Path(sys._MEIPASS) / "browser_bundle.zip"
        if bundle_zip.exists():
            return bundle_zip
    # Source / development fallback
    src_dir = Path(__file__).parent.parent.parent / "dist" / "antheneo"
    if src_dir.exists():
        return src_dir
    return None

BUNDLE_PATH = _find_bundle()

# ── Palette ────────────────────────────────────────────────────────────────
BG_DEEP   = "#0d1117"
BG_PANEL  = "#161b22"
BG_WIDGET = "#1c2128"
BG_ACTIVE = "#2d333b"
CYAN      = "#00d4d4"
CYAN_DIM  = "#007f7f"
PURPLE    = "#a855f7"
SUCCESS   = "#3fb950"
DANGER    = "#f85149"
WARNING   = "#d29922"
TEXT      = "#e6edf3"
TEXT_DIM  = "#8b949e"
BORDER    = "#30363d"

STYLESHEET = f"""
QDialog, QWidget {{
    background: {BG_DEEP};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QPushButton {{
    background: {BG_WIDGET};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: 500;
    min-width: 90px;
}}
QPushButton:hover  {{ background: {BG_ACTIVE}; border-color: {TEXT_DIM}; }}
QPushButton:pressed {{ background: #373e47; }}
QPushButton#primary {{
    background: {CYAN_DIM};
    color: {BG_DEEP};
    border-color: {CYAN};
    font-weight: 700;
}}
QPushButton#primary:hover  {{ background: {CYAN}; }}
QPushButton#primary:disabled {{ background: #1c3030; color: #3a6060; border-color: #1c3030; }}
QPushButton#danger {{ color: {DANGER}; border-color: {DANGER}; background: transparent; }}
QPushButton#danger:hover {{ background: {DANGER}; color: white; }}
QLineEdit {{
    background: {BG_WIDGET};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 12px;
}}
QLineEdit:focus {{ border-color: {CYAN}; }}
QTextEdit {{
    background: {BG_WIDGET};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}}
QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_WIDGET};
}}
QCheckBox::indicator:checked {{ background: {CYAN_DIM}; border-color: {CYAN}; }}
QProgressBar {{
    background: {BG_WIDGET};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {CYAN}; border-radius: 4px; }}
QScrollBar:vertical {{
    background: {BG_DEEP}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BG_ACTIVE}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

LICENSE_TEXT = f"""{APP_NAME} — End User License Agreement

{COPYRIGHT}. All rights reserved.

IMPORTANT: READ THIS AGREEMENT CAREFULLY BEFORE INSTALLING OR USING {APP_NAME.upper()}.
BY CLICKING "I ACCEPT" OR INSTALLING THE SOFTWARE, YOU AGREE TO BE BOUND BY
THE TERMS OF THIS AGREEMENT.

1. GRANT OF LICENSE
   Antheneo grants you a non-exclusive, non-transferable license to install and use
   {APP_NAME} solely for your personal or internal business purposes.

2. RESTRICTIONS
   You may not: (a) copy, modify, or distribute the Software; (b) reverse engineer,
   decompile, or disassemble the Software; (c) rent, lease, or lend the Software;
   (d) remove any proprietary notices or labels on the Software.

3. PRIVACY
   {APP_NAME} is designed to protect your privacy. It does not collect, transmit,
   or sell your personal browsing data. Privacy Shield statistics are stored locally
   only and never uploaded.

4. HACKER MODE DISCLAIMER
   The Hacker Mode tools included in this Software (DNS lookup, port scanner, header
   inspector, WHOIS, etc.) are provided exclusively for authorized security testing.
   Use of these tools against systems you do not own or have explicit written permission
   to test is illegal and strictly prohibited. Antheneo assumes no liability for misuse.

5. DISCLAIMER OF WARRANTIES
   THE SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
   INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
   PURPOSE, AND NON-INFRINGEMENT.

6. LIMITATION OF LIABILITY
   IN NO EVENT SHALL ANTHENEO BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL,
   EXEMPLARY, OR CONSEQUENTIAL DAMAGES, HOWEVER CAUSED, EVEN IF ADVISED OF THE
   POSSIBILITY OF SUCH DAMAGE.

7. TERMINATION
   This license is effective until terminated. It terminates automatically if you fail
   to comply with any term of this Agreement.

8. GOVERNING LAW
   This Agreement shall be governed by and construed in accordance with applicable law.

By proceeding with the installation you confirm you have read, understood, and agree
to be bound by the terms above.

{COPYRIGHT}
https://antheneo.io
"""


# ── Sidebar step indicator ─────────────────────────────────────────────────

class SidebarWidget(QWidget):
    STEPS = ["Welcome", "License", "Install Path", "Options", "Installing", "Finished"]

    def __init__(self):
        super().__init__()
        self.setFixedWidth(210)
        self._current = 0
        self.setStyleSheet(f"background: {BG_PANEL};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo area ──────────────────────────────────────────────────────
        logo_frame = QWidget()
        logo_frame.setFixedHeight(120)
        logo_frame.setStyleSheet(f"background: {BG_DEEP}; border-bottom: 1px solid {BORDER};")
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(20, 18, 20, 14)
        logo_layout.setSpacing(2)

        icon_label = QLabel("⚡")
        icon_label.setStyleSheet(f"color: {CYAN}; font-size: 32px; font-weight: bold;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        logo_layout.addWidget(icon_label)

        name_label = QLabel("ANTHENEO")
        name_label.setStyleSheet(f"color: {CYAN}; font-size: 15px; font-weight: 800; letter-spacing: 2px;")
        logo_layout.addWidget(name_label)

        sub_label = QLabel("Browser")
        sub_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        logo_layout.addWidget(sub_label)

        layout.addWidget(logo_frame)

        # ── Step list ──────────────────────────────────────────────────────
        steps_frame = QWidget()
        steps_layout = QVBoxLayout(steps_frame)
        steps_layout.setContentsMargins(0, 16, 0, 16)
        steps_layout.setSpacing(2)

        self._step_labels: list[QLabel] = []
        for i, name in enumerate(self.STEPS):
            row = QWidget()
            row.setFixedHeight(36)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 0, 16, 0)
            row_layout.setSpacing(10)

            dot = QLabel("●" if i == 0 else "○")
            dot.setFixedWidth(14)
            dot.setObjectName(f"dot_{i}")
            row_layout.addWidget(dot)

            lbl = QLabel(name)
            lbl.setObjectName(f"step_{i}")
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            steps_layout.addWidget(row)
            self._step_labels.append((dot, lbl, row))

        steps_layout.addStretch()
        layout.addWidget(steps_frame, 1)

        # ── Version footer ─────────────────────────────────────────────────
        footer = QLabel(f"v{VERSION}\n{COPYRIGHT}")
        footer.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; padding: 12px 20px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(footer)

        self._refresh()

    def set_step(self, idx: int):
        self._current = idx
        self._refresh()

    def _refresh(self):
        for i, (dot, lbl, row) in enumerate(self._step_labels):
            if i < self._current:
                dot.setText("✔")
                dot.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
                lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
                row.setStyleSheet("background: transparent;")
            elif i == self._current:
                dot.setText("▶")
                dot.setStyleSheet(f"color: {CYAN}; font-size: 11px;")
                lbl.setStyleSheet(f"color: {CYAN}; font-size: 12px; font-weight: 700;")
                row.setStyleSheet(f"background: {BG_ACTIVE}; border-radius: 4px;")
            else:
                dot.setText("○")
                dot.setStyleSheet(f"color: {BORDER}; font-size: 11px;")
                lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
                row.setStyleSheet("background: transparent;")


# ── Install worker thread ──────────────────────────────────────────────────

class InstallWorker(QThread):
    progress   = pyqtSignal(int, str)    # percent, status message
    log        = pyqtSignal(str)
    finished   = pyqtSignal(bool, str)   # success, message

    def __init__(self, bundle: Path, target: Path, options: dict):
        super().__init__()
        self.bundle  = bundle
        self.target  = target
        self.options = options

    def run(self):
        try:
            self._install()
            self.finished.emit(True, "Installation complete.")
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _install(self):
        target = self.target
        self.progress.emit(2, "Preparing installation directory…")
        target.mkdir(parents=True, exist_ok=True)

        # ── Extract / copy files ───────────────────────────────────────────
        if self.bundle.suffix == ".zip":
            self._extract_zip()
        else:
            self._copy_dir()

        # ── Platform post-install ──────────────────────────────────────────
        self.progress.emit(82, "Running post-install steps…")
        if PLAT == "linux":
            self._postinstall_linux()
        elif PLAT == "windows":
            self._postinstall_windows()
        elif PLAT == "darwin":
            self._postinstall_macos()

        self.progress.emit(100, f"{APP_NAME} installed successfully.")
        self.log.emit("─" * 50)
        self.log.emit(f"Installation complete  →  {target}")

    def _extract_zip(self):
        self.log.emit(f"Extracting bundle to {self.target}…")
        with zipfile.ZipFile(self.bundle) as zf:
            members = zf.namelist()
            total   = len(members)
            for i, member in enumerate(members, 1):
                zf.extract(member, self.target)
                pct = int(2 + (i / total) * 75)
                if i % 20 == 0 or i == total:
                    self.progress.emit(pct, f"Extracting… ({i}/{total})")
                    self.log.emit(f"  {member}")

    def _copy_dir(self):
        src = self.bundle
        dst = self.target
        self.log.emit(f"Copying {src} → {dst}…")
        files = list(src.rglob("*"))
        total = len(files)
        for i, f in enumerate(files, 1):
            rel  = f.relative_to(src)
            dest = dst / rel
            if f.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
            pct = int(2 + (i / total) * 75)
            if i % 30 == 0 or i == total:
                self.progress.emit(pct, f"Copying files… ({i}/{total})")

    # ── Linux ──────────────────────────────────────────────────────────────

    def _postinstall_linux(self):
        target = self.target
        exe    = target / "antheneo"
        if exe.exists():
            exe.chmod(0o755)

        # Launcher symlink
        if self.options.get("add_to_path", True):
            link = Path("/usr/local/bin/antheneo")
            try:
                link.unlink(missing_ok=True)
                link.symlink_to(exe)
                self.log.emit(f"Launcher symlink: {link}")
            except PermissionError:
                wrapper = Path.home() / ".local" / "bin" / "antheneo"
                wrapper.parent.mkdir(parents=True, exist_ok=True)
                wrapper.write_text(f"#!/bin/sh\nexec {exe} \"$@\"\n")
                wrapper.chmod(0o755)
                self.log.emit(f"Launcher (user): {wrapper}")

        # .desktop file
        if self.options.get("desktop_shortcut", True) or self.options.get("menu_entry", True):
            icon_path = target / "assets" / "icon.png"
            desktop_content = (
                "[Desktop Entry]\n"
                f"Name={APP_NAME}\n"
                "GenericName=Web Browser\n"
                f"Comment=Privacy-first browser with ethical hacking tools\n"
                f"Exec={exe} %U\n"
                f"Icon={icon_path}\n"
                "Terminal=false\n"
                "Type=Application\n"
                "Categories=Network;WebBrowser;Security;\n"
                "MimeType=text/html;text/xml;application/xhtml+xml;"
                "x-scheme-handler/http;x-scheme-handler/https;\n"
                "StartupNotify=true\n"
            )
            # System-wide if writable, else user
            sys_apps = Path("/usr/share/applications")
            user_apps = Path.home() / ".local" / "share" / "applications"
            try:
                desktop_file = sys_apps / "antheneo.desktop"
                desktop_file.write_text(desktop_content)
            except PermissionError:
                user_apps.mkdir(parents=True, exist_ok=True)
                desktop_file = user_apps / "antheneo.desktop"
                desktop_file.write_text(desktop_content)
            self.log.emit(f".desktop entry: {desktop_file}")

            # Refresh caches
            subprocess.run(
                ["update-desktop-database", str(desktop_file.parent)],
                capture_output=True
            )

        # Desktop shortcut (symlink on Linux)
        if self.options.get("desktop_shortcut", True):
            desk = Path.home() / "Desktop" / "Antheneo Browser.desktop"
            if desk.parent.exists():
                shutil.copy2(desktop_file, desk)
                desk.chmod(0o755)
                self.log.emit(f"Desktop shortcut: {desk}")

        self.progress.emit(95, "Post-install complete.")

    # ── Windows ────────────────────────────────────────────────────────────

    def _postinstall_windows(self):
        target = self.target
        exe    = target / "antheneo.exe"
        if not exe.exists():
            return

        def _create_shortcut(link_path: Path, target_exe: Path, description: str):
            ps = (
                f"$ws = New-Object -ComObject WScript.Shell; "
                f"$sc = $ws.CreateShortcut('{link_path}'); "
                f"$sc.TargetPath = '{target_exe}'; "
                f"$sc.Description = '{description}'; "
                f"$sc.WorkingDirectory = '{target_exe.parent}'; "
                f"$sc.Save()"
            )
            subprocess.run(["powershell", "-Command", ps], capture_output=True)
            self.log.emit(f"Shortcut: {link_path}")

        # Desktop shortcut
        if self.options.get("desktop_shortcut", True):
            desktop = Path(os.path.expanduser("~/Desktop"))
            if desktop.exists():
                _create_shortcut(
                    desktop / f"{APP_NAME}.lnk", exe,
                    "Privacy-first browser with ethical hacking tools"
                )

        # Start menu
        if self.options.get("menu_entry", True):
            start = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Antheneo"
            start.mkdir(parents=True, exist_ok=True)
            _create_shortcut(
                start / f"{APP_NAME}.lnk", exe,
                "Privacy-first browser with ethical hacking tools"
            )
            _create_shortcut(
                start / f"Uninstall {APP_NAME}.lnk",
                target / "uninstall.exe", "Uninstall Antheneo Browser"
            )

        # Write uninstall info to registry
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\com.antheneo.browser"
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                winreg.SetValueEx(key, "DisplayName",    0, winreg.REG_SZ, APP_NAME)
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
                winreg.SetValueEx(key, "Publisher",      0, winreg.REG_SZ, "Antheneo")
                winreg.SetValueEx(key, "InstallLocation",0, winreg.REG_SZ, str(target))
                winreg.SetValueEx(key, "DisplayIcon",    0, winreg.REG_SZ, str(exe))
                winreg.SetValueEx(key, "URLInfoAbout",   0, winreg.REG_SZ, "https://antheneo.io")
            self.log.emit("Registry: Add/Remove Programs entry created.")
        except Exception:
            pass

        self.progress.emit(95, "Post-install complete.")

    # ── macOS ──────────────────────────────────────────────────────────────

    def _postinstall_macos(self):
        target = self.target
        exe    = target / "antheneo"
        if exe.exists():
            exe.chmod(0o755)
        if self.options.get("desktop_shortcut", True):
            desk = Path.home() / "Desktop" / f"{APP_NAME}"
            subprocess.run(["ln", "-sf", str(exe), str(desk)], capture_output=True)
            self.log.emit(f"Desktop alias: {desk}")
        self.progress.emit(95, "Post-install complete.")


# ── Wizard pages ───────────────────────────────────────────────────────────

def _heading(text: str, color: str = CYAN) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 800;")
    lbl.setWordWrap(True)
    return lbl


def _body(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px; line-height: 160%;")
    lbl.setWordWrap(True)
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {BORDER};")
    return line


def _feature_bullet(icon: str, text: str) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(10)

    ico = QLabel(icon)
    ico.setStyleSheet(f"color: {CYAN}; font-size: 16px;")
    ico.setFixedWidth(22)
    layout.addWidget(ico)

    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
    layout.addWidget(lbl)
    layout.addStretch()
    return row


# ── Page 0: Welcome ────────────────────────────────────────────────────────

def page_welcome() -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(36, 32, 36, 20)
    lay.setSpacing(14)

    lay.addWidget(_heading(f"Welcome to {APP_NAME} Setup"))
    lay.addWidget(_body(f"This wizard will install {APP_NAME} v{VERSION} on your computer. "
                        "Please close all other applications before continuing."))
    lay.addWidget(_divider())

    feat_title = QLabel("What you're getting:")
    feat_title.setStyleSheet(f"color: {TEXT}; font-weight: 600; font-size: 13px; margin-top: 4px;")
    lay.addWidget(feat_title)

    features = [
        ("🛡", "Built-in ad & tracker blocker — 150+ blocked domains"),
        ("🔐", "Automatic HTTP→HTTPS upgrading on every request"),
        ("🎭", "Browser fingerprint randomization (canvas, WebGL, audio)"),
        ("🧹", "Tracking parameter stripping (UTM, fbclid, gclid…)"),
        ("🌑", "Dark cyberpunk UI with cyan & purple accents"),
        ("⚡", "Optional Hacker Mode: DNS, port scan, WHOIS, JS console"),
    ]
    for icon, text in features:
        lay.addWidget(_feature_bullet(icon, text))

    lay.addStretch()

    note = QLabel(f"Click  Next  to continue   |   {COPYRIGHT}")
    note.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
    note.setAlignment(Qt.AlignmentFlag.AlignRight)
    lay.addWidget(note)
    return w


# ── Page 1: License ────────────────────────────────────────────────────────

def page_license(accepted_cb) -> tuple[QWidget, QCheckBox]:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(36, 32, 36, 20)
    lay.setSpacing(12)

    lay.addWidget(_heading("License Agreement"))
    lay.addWidget(_body("Please read the following license carefully before proceeding."))

    txt = QTextEdit()
    txt.setReadOnly(True)
    txt.setPlainText(LICENSE_TEXT)
    txt.setMinimumHeight(240)
    lay.addWidget(txt, 1)

    chk = QCheckBox("I have read and accept the terms of the License Agreement")
    chk.setStyleSheet(f"color: {TEXT}; font-size: 13px; margin-top: 4px;")
    chk.toggled.connect(accepted_cb)
    lay.addWidget(chk)
    return w, chk


# ── Page 2: Install Path ───────────────────────────────────────────────────

def page_install_path() -> tuple[QWidget, QLineEdit]:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(36, 32, 36, 20)
    lay.setSpacing(14)

    lay.addWidget(_heading("Choose Install Location"))
    lay.addWidget(_body("Select the folder where Antheneo Browser will be installed."))
    lay.addWidget(_divider())

    path_row = QHBoxLayout()
    path_row.setSpacing(8)

    path_edit = QLineEdit(str(DEFAULT_INSTALL))
    path_edit.setPlaceholderText("Installation directory…")
    path_row.addWidget(path_edit, 1)

    browse_btn = QPushButton("Browse…")
    browse_btn.setFixedWidth(90)

    def _browse():
        chosen = QFileDialog.getExistingDirectory(
            w, "Choose Installation Folder", str(DEFAULT_INSTALL)
        )
        if chosen:
            path_edit.setText(chosen)

    browse_btn.clicked.connect(_browse)
    path_row.addWidget(browse_btn)
    lay.addLayout(path_row)

    # Space info
    space_lbl = QLabel()
    space_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

    def _update_space(path_str: str):
        try:
            usage = shutil.disk_usage(Path(path_str).anchor)
            free_gb = usage.free / 1024**3
            space_lbl.setText(f"Free space: {free_gb:.1f} GB")
        except Exception:
            space_lbl.setText("")

    path_edit.textChanged.connect(_update_space)
    _update_space(str(DEFAULT_INSTALL))
    lay.addWidget(space_lbl)

    lay.addWidget(_divider())
    lay.addWidget(_body(
        "Required disk space: ~250 MB\n"
        "The installer will create the directory if it does not exist."
    ))
    lay.addStretch()
    return w, path_edit


# ── Page 3: Options ────────────────────────────────────────────────────────

def page_options() -> tuple[QWidget, dict]:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(36, 32, 36, 20)
    lay.setSpacing(14)

    lay.addWidget(_heading("Installation Options"))
    lay.addWidget(_body("Choose how Antheneo Browser will be configured after install."))
    lay.addWidget(_divider())

    checkboxes = {}

    opts = [
        ("desktop_shortcut", "Create a Desktop shortcut", True),
        ("menu_entry",       "Add to application menu / Start Menu", True),
        ("add_to_path",      "Add  antheneo  command to PATH", True),
    ]
    if PLAT == "linux" or PLAT == "darwin":
        opts.append(("default_browser",
                     "Register Antheneo as default browser (optional)", False))

    for key, label, default in opts:
        chk = QCheckBox(label)
        chk.setChecked(default)
        lay.addWidget(chk)
        checkboxes[key] = chk

    lay.addWidget(_divider())

    note = _body(
        "Hacker Mode tools are disabled by default. You can enable them "
        "at any time in the browser via the  ⚡  button or Settings menu."
    )
    lay.addWidget(note)
    lay.addStretch()
    return w, checkboxes


# ── Page 4: Installing ─────────────────────────────────────────────────────

def page_installing() -> tuple[QWidget, QProgressBar, QLabel, QTextEdit]:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(36, 32, 36, 20)
    lay.setSpacing(12)

    lay.addWidget(_heading("Installing…"))
    status_lbl = QLabel("Preparing…")
    status_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
    lay.addWidget(status_lbl)

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setFixedHeight(10)
    lay.addWidget(bar)

    log = QTextEdit()
    log.setReadOnly(True)
    log.setMinimumHeight(200)
    log.setStyleSheet(
        f"background: {BG_DEEP}; color: {TEXT_DIM}; font-size: 11px; "
        f"font-family: monospace; border: 1px solid {BORDER}; border-radius: 6px;"
    )
    lay.addWidget(log, 1)
    return w, bar, status_lbl, log


# ── Page 5: Finished ───────────────────────────────────────────────────────

def page_finished(success: bool, message: str, launch_cb) -> tuple[QWidget, QCheckBox]:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(36, 32, 36, 20)
    lay.setSpacing(14)

    if success:
        lay.addWidget(_heading("Installation Complete! 🎉", SUCCESS))
        lay.addWidget(_body(
            f"{APP_NAME} v{VERSION} has been installed successfully.\n\n"
            "Your privacy is now protected by default:\n"
            "  •  Ads and trackers are blocked\n"
            "  •  Connections are automatically upgraded to HTTPS\n"
            "  •  Browser fingerprinting is randomized"
        ))
        lay.addWidget(_divider())
        launch_chk = QCheckBox(f"Launch {APP_NAME} now")
        launch_chk.setChecked(True)
        launch_chk.toggled.connect(launch_cb)
        launch_chk.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 600;")
        lay.addWidget(launch_chk)
    else:
        lay.addWidget(_heading("Installation Failed", DANGER))
        err_txt = QTextEdit()
        err_txt.setReadOnly(True)
        err_txt.setPlainText(message)
        lay.addWidget(err_txt)
        launch_chk = QCheckBox()
        launch_chk.hide()

    lay.addStretch()
    return w, launch_chk


# ── Main Wizard Dialog ─────────────────────────────────────────────────────

class InstallerWizard(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Setup Wizard")
        self.setFixedSize(820, 540)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(STYLESHEET)

        self._step = 0
        self._launch_browser = True
        self._worker: InstallWorker | None = None
        self._install_path: Path = DEFAULT_INSTALL
        self._install_ok   = False

        self._build_ui()
        self._goto(0)

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left sidebar
        self.sidebar = SidebarWidget()
        root.addWidget(self.sidebar)

        # Right area
        right = QWidget()
        right.setStyleSheet(f"background: {BG_DEEP};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {BORDER};")
        root.addWidget(sep)

        # Page stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {BG_DEEP};")
        right_layout.addWidget(self.stack, 1)

        # ── Build all pages ────────────────────────────────────────────────
        # Page 0
        self.stack.addWidget(page_welcome())

        # Page 1
        p1, self._license_chk = page_license(self._on_license_toggled)
        self.stack.addWidget(p1)

        # Page 2
        p2, self._path_edit = page_install_path()
        self.stack.addWidget(p2)

        # Page 3
        p3, self._option_chks = page_options()
        self.stack.addWidget(p3)

        # Page 4 (installing — built dynamically on enter)
        p4, self._progress_bar, self._status_lbl, self._log = page_installing()
        self.stack.addWidget(p4)

        # Page 5 (finished — rebuilt after install)
        self._p5_placeholder = QWidget()
        self.stack.addWidget(self._p5_placeholder)

        # ── Bottom nav bar ─────────────────────────────────────────────────
        nav_frame = QWidget()
        nav_frame.setFixedHeight(56)
        nav_frame.setStyleSheet(f"background: {BG_PANEL}; border-top: 1px solid {BORDER};")
        nav = QHBoxLayout(nav_frame)
        nav.setContentsMargins(20, 10, 20, 10)
        nav.setSpacing(10)

        nav.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.clicked.connect(self._on_cancel)
        nav.addWidget(self.btn_cancel)

        self.btn_back = QPushButton("◀  Back")
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next  ▶")
        self.btn_next.setObjectName("primary")
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_next)

        right_layout.addWidget(nav_frame)
        root.addWidget(right)

    # ── Navigation ─────────────────────────────────────────────────────────

    def _goto(self, step: int):
        self._step = step
        self.stack.setCurrentIndex(step)
        self.sidebar.set_step(step)

        is_first  = step == 0
        is_last   = step == 5
        installing = step == 4

        self.btn_back.setEnabled(not is_first and not installing)
        self.btn_cancel.setVisible(not is_last)
        self.btn_next.setEnabled(self._can_proceed())

        if is_last:
            self.btn_next.setText("Finish")
            self.btn_back.setEnabled(False)
        elif step == 3:
            self.btn_next.setText("Install  ▶")
        elif installing:
            self.btn_next.setEnabled(False)
            self.btn_next.setText("Installing…")
        else:
            self.btn_next.setText("Next  ▶")

    def _can_proceed(self) -> bool:
        if self._step == 1:
            return self._license_chk.isChecked()
        return True

    def _go_next(self):
        if self._step == 5:
            self._finish()
            return
        if self._step == 3:
            self._start_install()
            return
        self._goto(self._step + 1)

    def _go_back(self):
        if self._step > 0:
            self._goto(self._step - 1)

    def _on_license_toggled(self, checked: bool):
        if self._step == 1:
            self.btn_next.setEnabled(checked)

    def _on_cancel(self):
        from PyQt6.QtWidgets import QMessageBox
        if self._step == 4:
            return   # Don't cancel mid-install
        if QMessageBox.question(
            self, "Cancel Setup",
            f"Cancel the installation of {APP_NAME}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.reject()

    # ── Installation ────────────────────────────────────────────────────────

    def _start_install(self):
        self._install_path = Path(self._path_edit.text().strip())
        options = {k: chk.isChecked() for k, chk in self._option_chks.items()}

        if BUNDLE_PATH is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error",
                "Browser bundle not found.\n\nRun build.py first to compile the browser.")
            return

        self._goto(4)
        self._log.clear()
        self._progress_bar.setValue(0)

        self._worker = InstallWorker(BUNDLE_PATH, self._install_path, options)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress_bar.setValue(pct)
        self._status_lbl.setText(msg)

    def _on_log(self, line: str):
        self._log.append(line)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _on_install_finished(self, success: bool, message: str):
        self._install_ok = success

        # Replace placeholder with real finish page
        self.stack.removeWidget(self._p5_placeholder)
        self._p5_placeholder.deleteLater()

        p5, self._launch_chk = page_finished(
            success, message,
            lambda checked: setattr(self, "_launch_browser", checked)
        )
        self.stack.addWidget(p5)
        self._goto(5)

    # ── Finish ─────────────────────────────────────────────────────────────

    def _finish(self):
        if self._install_ok and self._launch_browser:
            exe = self._install_path / ("antheneo.exe" if PLAT == "windows" else "antheneo")
            if exe.exists():
                subprocess.Popen([str(exe)], close_fds=True)
        self.accept()


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(f"{APP_NAME} Setup")
    app.setApplicationVersion(VERSION)

    # Try to set app icon from bundle
    if getattr(sys, "frozen", False):
        ico = Path(sys._MEIPASS) / "assets" / "icon.png"
    else:
        ico = Path(__file__).parent.parent.parent / "assets" / "icon.png"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    wizard = InstallerWizard()
    result = wizard.exec()
    sys.exit(0 if result == QDialog.DialogCode.Accepted else 1)


if __name__ == "__main__":
    main()
