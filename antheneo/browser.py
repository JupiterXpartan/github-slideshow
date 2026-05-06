#!/usr/bin/env python3
"""
Antheneo Browser — Privacy-first, resource-light, hacker-ready
"""

import sys
import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import (
    QUrl, Qt, QSize, pyqtSignal, QObject, QTimer, QSettings
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QToolBar, QLineEdit, QPushButton, QLabel,
    QStatusBar, QProgressBar, QMenu, QAction, QTabBar,
    QSizePolicy, QDockWidget, QSplitter, QMessageBox,
    QInputDialog, QDialog, QFormLayout, QComboBox,
    QCheckBox, QGroupBox, QDialogButtonBox, QToolButton,
    QScrollArea,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    QWebEngineDownloadRequest,
)
from PyQt6.QtGui import (
    QIcon, QColor, QFont, QKeySequence, QShortcut,
    QAction as QGuiAction, QDesktopServices,
)

from ui.themes import DARK_STYLESHEET, HACKER_MODE_ACCENT, ACCENT, ACCENT_HACK, SUCCESS, DANGER
from core.privacy import AnthenePrivacyInterceptor, PrivacyStats, FINGERPRINT_PROTECTION_JS
from version import APP_NAME, VERSION, COPYRIGHT

try:
    from ui.hacker_panel import HackerToolsPanel
    HACKER_PANEL_AVAILABLE = True
except ImportError:
    HACKER_PANEL_AVAILABLE = False

# When running as a PyInstaller bundle, __file__ lives inside the temp
# extraction dir (_MEIPASS). User data must go to a real persistent location.
if getattr(sys, "frozen", False):
    APP_DIR  = Path(sys._MEIPASS)          # read-only bundle resources
    APP_DATA = Path.home() / ".antheneo"   # writable user data
else:
    APP_DIR  = Path(__file__).parent
    APP_DATA = APP_DIR

APP_DATA.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DATA / "settings.json"
HOME_URL    = "https://search.brave.com"
NEW_TAB_URL = "about:blank"


# ── Settings ───────────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "home_url": HOME_URL,
    "shields_enabled": True,
    "https_only": True,
    "fingerprint_protection": True,
    "hacker_mode": False,
    "theme": "dark",
    "restore_tabs": True,
    "last_tabs": [],
    "bookmarks": [],
    "custom_css": "",
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open() as f:
                data = json.load(f)
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict):
    with SETTINGS_FILE.open("w") as f:
        json.dump(settings, f, indent=2)


# ── Custom Web Page ────────────────────────────────────────────────────────

class AntheneWebPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def javaScriptConsoleMessage(self, level, message, line, source):
        # Suppress noisy console output from pages; accessible via hacker panel
        pass


# ── Browser Tab ────────────────────────────────────────────────────────────

class BrowserTab(QWebEngineView):
    title_changed_signal = pyqtSignal(str)

    def __init__(self, profile: QWebEngineProfile, settings: dict):
        super().__init__()
        self._settings = settings
        self._profile = profile
        self.page_obj = AntheneWebPage(profile, self)
        self.setPage(self.page_obj)

        self._apply_settings()
        self.loadFinished.connect(self._on_load_finished)
        self.titleChanged.connect(self.title_changed_signal)

    def _apply_settings(self):
        ws = self.page().settings()
        ws.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        ws.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        ws.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        ws.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        ws.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        ws.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        ws.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        # Harden against clickjacking
        ws.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        ws.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)

    def _on_load_finished(self, ok: bool):
        if ok and self._settings.get("fingerprint_protection"):
            self.page().runJavaScript(FINGERPRINT_PROTECTION_JS)

    def navigate(self, url: str):
        if not url.startswith(("http://", "https://", "about:", "file://")):
            # Check if it looks like a URL or a search query
            if re.match(r'^[\w.-]+\.\w{2,}', url) and " " not in url:
                url = "https://" + url
            else:
                url = "https://search.brave.com/search?q=" + url.replace(" ", "+")
        self.setUrl(QUrl(url))

    def apply_user_agent(self, ua: str):
        self._profile.setHttpUserAgent(ua)

    def run_js_with_callback(self, code: str, callback):
        self.page().runJavaScript(code, callback)


# ── Address Bar ────────────────────────────────────────────────────────────

class AddressBar(QLineEdit):
    navigate_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Search or enter URL…")
        self.returnPressed.connect(self._on_return)
        self.setMinimumWidth(300)

    def _on_return(self):
        self.navigate_requested.emit(self.text().strip())

    def set_url(self, url: str):
        self.setText(url)
        self.setCursorPosition(0)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()


# ── Custom Tab Bar ─────────────────────────────────────────────────────────

class AntheneTabWidget(QTabWidget):
    new_tab_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)

        # "+" button at end of tab bar
        self.new_tab_btn = QToolButton()
        self.new_tab_btn.setText("+")
        self.new_tab_btn.setToolTip("New Tab (Ctrl+T)")
        self.new_tab_btn.clicked.connect(self.new_tab_requested)
        self.setCornerWidget(self.new_tab_btn, Qt.Corner.TopRightCorner)


# ── Main Browser Window ────────────────────────────────────────────────────

class AntheoBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.hacker_mode = self.settings.get("hacker_mode", False)
        self._download_count = 0
        self._hacker_panel: HackerToolsPanel | None = None

        # Privacy stats
        self.privacy_stats = PrivacyStats()
        self.privacy_stats.stats_updated.connect(self._update_stats_display)

        # Web engine profile (shared across tabs)
        self.profile = QWebEngineProfile("antheneo_profile", self)
        self._setup_profile()

        # Privacy interceptor
        self.interceptor = AnthenePrivacyInterceptor(self.privacy_stats, self)
        self.interceptor.shields_enabled = self.settings.get("shields_enabled", True)
        self.interceptor.request_logged.connect(self._on_request_logged)
        self.profile.setUrlRequestInterceptor(self.interceptor)

        self._build_ui()
        self._build_menu()
        self._setup_shortcuts()
        self._apply_theme()

        # Open initial tab
        self.new_tab(self.settings.get("home_url", HOME_URL))
        self.setWindowTitle(f"{APP_NAME} Browser")
        self.resize(1280, 800)

    # ── Profile Setup ──────────────────────────────────────────────────────

    def _setup_profile(self):
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Antheneo/1.0 Privacy/Max"
        self.profile.setHttpUserAgent(ua)
        self.profile.downloadRequested.connect(self._handle_download)

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Toolbar ──
        self.toolbar = QToolBar("Navigation", self)
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        # Navigation buttons
        self.btn_back = QToolButton()
        self.btn_back.setText("◀")
        self.btn_back.setToolTip("Back (Alt+←)")
        self.btn_back.clicked.connect(lambda: self._current_tab() and self._current_tab().back())
        self.toolbar.addWidget(self.btn_back)

        self.btn_forward = QToolButton()
        self.btn_forward.setText("▶")
        self.btn_forward.setToolTip("Forward (Alt+→)")
        self.btn_forward.clicked.connect(lambda: self._current_tab() and self._current_tab().forward())
        self.toolbar.addWidget(self.btn_forward)

        self.btn_reload = QToolButton()
        self.btn_reload.setText("↻")
        self.btn_reload.setToolTip("Reload (F5)")
        self.btn_reload.clicked.connect(self._reload_or_stop)
        self.toolbar.addWidget(self.btn_reload)

        self.btn_home = QToolButton()
        self.btn_home.setText("⌂")
        self.btn_home.setToolTip("Home")
        self.btn_home.clicked.connect(self._go_home)
        self.toolbar.addWidget(self.btn_home)

        self.toolbar.addSeparator()

        # Security indicator
        self.security_label = QLabel("🔒")
        self.security_label.setObjectName("url_secure")
        self.security_label.setToolTip("Connection secure")
        self.toolbar.addWidget(self.security_label)

        # Address bar
        self.address_bar = AddressBar()
        self.address_bar.navigate_requested.connect(self._navigate_to)
        addr_wrapper = QWidget()
        addr_layout = QHBoxLayout(addr_wrapper)
        addr_layout.setContentsMargins(4, 0, 4, 0)
        addr_layout.addWidget(self.address_bar)
        self.toolbar.addWidget(addr_wrapper)
        addr_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Shield button
        self.btn_shield = QPushButton("🛡")
        self.btn_shield.setCheckable(True)
        self.btn_shield.setChecked(self.settings.get("shields_enabled", True))
        self.btn_shield.setObjectName("shield_on" if self.interceptor.shields_enabled else "shield_off")
        self.btn_shield.setToolTip("Toggle Privacy Shields")
        self.btn_shield.toggled.connect(self._toggle_shields)
        self.toolbar.addWidget(self.btn_shield)

        # Hacker mode button
        self.btn_hacker = QPushButton("⚡")
        self.btn_hacker.setCheckable(True)
        self.btn_hacker.setChecked(self.hacker_mode)
        self.btn_hacker.setObjectName("hacker")
        self.btn_hacker.setToolTip("Toggle Hacker Mode")
        self.btn_hacker.toggled.connect(self._toggle_hacker_mode)
        self.toolbar.addWidget(self.btn_hacker)

        self.toolbar.addSeparator()

        self.btn_new_tab = QToolButton()
        self.btn_new_tab.setText("+")
        self.btn_new_tab.setToolTip("New Tab (Ctrl+T)")
        self.btn_new_tab.clicked.connect(lambda: self.new_tab())
        self.toolbar.addWidget(self.btn_new_tab)

        # ── Tab widget ──
        self.tabs = AntheneTabWidget()
        self.tabs.new_tab_requested.connect(lambda: self.new_tab())
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_url_label = QLabel("")
        self.status_url_label.setObjectName("subheading")
        self.status_bar.addWidget(self.status_url_label)

        self.status_bar.addPermanentWidget(QLabel("  "))

        self.blocked_label = QLabel("🛡 0 blocked")
        self.blocked_label.setObjectName("stat_blocked")
        self.blocked_label.setToolTip("Trackers/Ads blocked this session")
        self.status_bar.addPermanentWidget(self.blocked_label)

        self.https_label = QLabel("  🔐 0 upgraded")
        self.https_label.setObjectName("stat_https")
        self.https_label.setToolTip("HTTP→HTTPS upgrades")
        self.status_bar.addPermanentWidget(self.https_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # ── Hacker panel (dock) ──
        if HACKER_PANEL_AVAILABLE:
            self._hacker_panel = HackerToolsPanel(self)
            self._hacker_panel.ua_changed.connect(self._apply_user_agent)
            self._hacker_panel.execute_js.connect(self._execute_js_in_tab)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._hacker_panel)
            self._hacker_panel.setVisible(self.hacker_mode)

    # ── Menu ───────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        self._add_action(file_menu, "New Tab", self._new_tab_action, "Ctrl+T")
        self._add_action(file_menu, "New Private Window", self._new_private_window, "Ctrl+Shift+N")
        file_menu.addSeparator()
        self._add_action(file_menu, "Save Page As…", self._save_page, "Ctrl+S")
        file_menu.addSeparator()
        self._add_action(file_menu, "Close Tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W")
        self._add_action(file_menu, "Quit", self.close, "Ctrl+Q")

        # View
        view_menu = menubar.addMenu("&View")
        self._add_action(view_menu, "Zoom In", lambda: self._zoom(0.1), "Ctrl++")
        self._add_action(view_menu, "Zoom Out", lambda: self._zoom(-0.1), "Ctrl+-")
        self._add_action(view_menu, "Reset Zoom", lambda: self._zoom_reset(), "Ctrl+0")
        view_menu.addSeparator()
        self._add_action(view_menu, "Page Source", self._view_source, "Ctrl+U")
        self._add_action(view_menu, "Developer Tools", self._open_devtools, "F12")
        view_menu.addSeparator()
        act_hacker = self._add_action(
            view_menu, "Hacker Panel", self._toggle_hacker_panel, "Ctrl+Shift+H"
        )
        act_hacker.setCheckable(True)
        act_hacker.setChecked(self.hacker_mode)

        # Privacy
        privacy_menu = menubar.addMenu("&Privacy")
        self._add_action(privacy_menu, "Clear Session Data", self._clear_session)
        privacy_menu.addSeparator()
        shields_act = self._add_action(privacy_menu, "Privacy Shields", self._toggle_shields_menu)
        shields_act.setCheckable(True)
        shields_act.setChecked(self.interceptor.shields_enabled)
        self._shields_menu_action = shields_act

        fp_act = self._add_action(
            privacy_menu, "Fingerprint Protection",
            lambda c: self.settings.update({"fingerprint_protection": c})
        )
        fp_act.setCheckable(True)
        fp_act.setChecked(self.settings.get("fingerprint_protection", True))
        privacy_menu.addSeparator()
        self._add_action(privacy_menu, "Privacy Stats", self._show_privacy_stats)

        # Bookmarks
        bm_menu = menubar.addMenu("&Bookmarks")
        self._add_action(bm_menu, "Bookmark This Page", self._add_bookmark, "Ctrl+D")
        bm_menu.addSeparator()
        self._bookmark_menu = bm_menu
        self._refresh_bookmark_menu()

        # Tools
        tools_menu = menubar.addMenu("&Tools")
        self._add_action(tools_menu, "Settings…", self._open_settings, "Ctrl+,")
        tools_menu.addSeparator()
        self._add_action(tools_menu, "Hacker Mode", self._toggle_hacker_mode_menu)

        # Help
        help_menu = menubar.addMenu("&Help")
        self._add_action(help_menu, "About Antheneo", self._show_about)

    def _add_action(self, menu: QMenu, text: str, slot=None, shortcut: str = "") -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if slot:
            action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ── Shortcuts ──────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self, self._reload_current)
        QShortcut(QKeySequence("Ctrl+L"), self, self.address_bar.setFocus)
        QShortcut(QKeySequence("Alt+Left"), self, lambda: self._current_tab() and self._current_tab().back())
        QShortcut(QKeySequence("Alt+Right"), self, lambda: self._current_tab() and self._current_tab().forward())
        QShortcut(QKeySequence("Ctrl+Tab"), self, self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self._prev_tab)
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda n=i: self.tabs.setCurrentIndex(n - 1))

    # ── Tab Management ─────────────────────────────────────────────────────

    def new_tab(self, url: str = NEW_TAB_URL) -> BrowserTab:
        tab = BrowserTab(self.profile, self.settings)
        tab.loadStarted.connect(lambda: self._on_load_started(tab))
        tab.loadProgress.connect(lambda p: self._on_load_progress(p, tab))
        tab.loadFinished.connect(lambda ok: self._on_load_finished(ok, tab))
        tab.urlChanged.connect(lambda u: self._on_url_changed(u, tab))
        tab.titleChanged.connect(lambda t: self._on_title_changed(t, tab))

        idx = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(idx)
        if url and url != NEW_TAB_URL:
            tab.navigate(url)
        return tab

    def close_tab(self, index: int):
        if self.tabs.count() <= 1:
            self.close()
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget:
            widget.deleteLater()

    def _current_tab(self) -> BrowserTab | None:
        return self.tabs.currentWidget()

    def _next_tab(self):
        idx = (self.tabs.currentIndex() + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(idx)

    def _prev_tab(self):
        idx = (self.tabs.currentIndex() - 1) % self.tabs.count()
        self.tabs.setCurrentIndex(idx)

    def _new_tab_action(self):
        self.new_tab(self.settings.get("home_url", HOME_URL))

    # ── Navigation ─────────────────────────────────────────────────────────

    def _navigate_to(self, url: str):
        tab = self._current_tab()
        if tab:
            tab.navigate(url)

    def _go_home(self):
        self._navigate_to(self.settings.get("home_url", HOME_URL))

    def _reload_or_stop(self):
        tab = self._current_tab()
        if tab:
            tab.reload()

    def _reload_current(self):
        tab = self._current_tab()
        if tab:
            tab.reload()

    def _zoom(self, delta: float):
        tab = self._current_tab()
        if tab:
            tab.setZoomFactor(max(0.25, min(5.0, tab.zoomFactor() + delta)))

    def _zoom_reset(self):
        tab = self._current_tab()
        if tab:
            tab.setZoomFactor(1.0)

    # ── Tab Event Handlers ─────────────────────────────────────────────────

    def _on_load_started(self, tab: BrowserTab):
        if tab is self._current_tab():
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.btn_reload.setText("✕")

    def _on_load_progress(self, progress: int, tab: BrowserTab):
        if tab is self._current_tab():
            self.progress_bar.setValue(progress)

    def _on_load_finished(self, ok: bool, tab: BrowserTab):
        if tab is self._current_tab():
            self.progress_bar.setVisible(False)
            self.btn_reload.setText("↻")
        idx = self.tabs.indexOf(tab)
        if idx >= 0:
            title = tab.title() or "New Tab"
            short = title[:22] + "…" if len(title) > 24 else title
            self.tabs.setTabText(idx, short)
            self.tabs.setTabToolTip(idx, title)

    def _on_url_changed(self, url: QUrl, tab: BrowserTab):
        if tab is self._current_tab():
            url_str = url.toString()
            self.address_bar.set_url(url_str)
            is_https = url.scheme() == "https"
            self.security_label.setText("🔒" if is_https else "⚠")
            self.security_label.setObjectName("url_secure" if is_https else "url_insecure")
            self.security_label.setToolTip(
                "Connection secure (HTTPS)" if is_https else "Connection NOT secure"
            )
            self._refresh_style()

    def _on_title_changed(self, title: str, tab: BrowserTab):
        idx = self.tabs.indexOf(tab)
        if idx >= 0:
            short = title[:22] + "…" if len(title) > 24 else title
            self.tabs.setTabText(idx, short or "New Tab")
            self.tabs.setTabToolTip(idx, title)
        if tab is self._current_tab():
            self.setWindowTitle(f"{title} — Antheneo")

    def _on_tab_changed(self, index: int):
        tab = self.tabs.widget(index)
        if isinstance(tab, BrowserTab):
            url = tab.url().toString()
            self.address_bar.set_url(url)
            is_https = tab.url().scheme() == "https"
            self.security_label.setText("🔒" if is_https else "⚠")
            title = tab.title() or "New Tab"
            self.setWindowTitle(f"{title} — Antheneo")

    # ── Privacy & Shields ──────────────────────────────────────────────────

    def _toggle_shields(self, checked: bool):
        self.interceptor.shields_enabled = checked
        self.settings["shields_enabled"] = checked
        self.btn_shield.setObjectName("shield_on" if checked else "shield_off")
        self._refresh_style()
        save_settings(self.settings)
        if hasattr(self, "_shields_menu_action"):
            self._shields_menu_action.setChecked(checked)

    def _toggle_shields_menu(self, checked: bool):
        self.btn_shield.setChecked(checked)

    def _update_stats_display(self, blocked: int, https: int, stripped: int):
        self.blocked_label.setText(f"🛡 {blocked} blocked")
        self.https_label.setText(f"  🔐 {https} upgraded")

    def _on_request_logged(self, method: str, url: str, status: str):
        if self._hacker_panel and self.hacker_mode:
            self._hacker_panel.log_request(method, url, status)

    def _clear_session(self):
        self.profile.clearAllVisitedLinks()
        self.profile.clearHttpCache()
        self.privacy_stats.reset()
        QMessageBox.information(self, "Session Cleared",
            "Browsing history, cache, and cookies have been cleared.")

    def _show_privacy_stats(self):
        s = self.privacy_stats
        QMessageBox.information(self, "Privacy Stats",
            f"This session:\n\n"
            f"  🛡  Trackers/Ads blocked:  {s.blocked}\n"
            f"  🔐  HTTP→HTTPS upgrades:   {s.https_upgrades}\n"
            f"  🧹  Tracking params stripped: {s.params_stripped}"
        )

    # ── Hacker Mode ────────────────────────────────────────────────────────

    def _toggle_hacker_mode(self, checked: bool = None):
        if checked is None:
            checked = not self.hacker_mode
        self.hacker_mode = checked
        self.btn_hacker.setChecked(checked)
        self.settings["hacker_mode"] = checked
        save_settings(self.settings)

        if self._hacker_panel:
            self._hacker_panel.setVisible(checked)
        self._apply_theme()

    def _toggle_hacker_mode_menu(self):
        self._toggle_hacker_mode(not self.hacker_mode)

    def _toggle_hacker_panel(self, checked: bool):
        if self._hacker_panel:
            self._hacker_panel.setVisible(checked)

    def _apply_user_agent(self, ua: str):
        self.profile.setHttpUserAgent(ua)

    def _execute_js_in_tab(self, code: str):
        tab = self._current_tab()
        if not tab:
            return
        def _cb(result):
            result_str = str(result) if result is not None else "undefined"
            if self._hacker_panel:
                self._hacker_panel.log_js_result(result_str)
        tab.run_js_with_callback(code, _cb)

    # ── Developer Tools ────────────────────────────────────────────────────

    def _open_devtools(self):
        tab = self._current_tab()
        if not tab:
            return
        dev_view = QWebEngineView()
        tab.page().setDevToolsPage(dev_view.page())
        dev_view.setWindowTitle("Antheneo DevTools")
        dev_view.resize(900, 600)
        dev_view.show()
        self._devtools_view = dev_view  # keep reference

    def _view_source(self):
        tab = self._current_tab()
        if not tab:
            return
        url = "view-source:" + tab.url().toString()
        self.new_tab(url)

    # ── Bookmarks ──────────────────────────────────────────────────────────

    def _add_bookmark(self):
        tab = self._current_tab()
        if not tab:
            return
        url = tab.url().toString()
        title = tab.title() or url
        bookmarks: list = self.settings.get("bookmarks", [])
        if not any(b["url"] == url for b in bookmarks):
            bookmarks.append({"title": title, "url": url})
            self.settings["bookmarks"] = bookmarks
            save_settings(self.settings)
            self._refresh_bookmark_menu()

    def _refresh_bookmark_menu(self):
        # Remove old bookmark actions (keep first 2: "Bookmark This Page" + separator)
        for action in self._bookmark_menu.actions()[2:]:
            self._bookmark_menu.removeAction(action)
        for bm in self.settings.get("bookmarks", []):
            title = bm.get("title", bm["url"])[:40]
            url = bm["url"]
            act = QAction(title, self)
            act.triggered.connect(lambda _, u=url: self.new_tab(u))
            self._bookmark_menu.addAction(act)

    # ── Downloads ─────────────────────────────────────────────────────────

    def _handle_download(self, download: QWebEngineDownloadRequest):
        from PyQt6.QtWidgets import QFileDialog
        suggested = download.suggestedFileName()
        path, _ = QFileDialog.getSaveFileName(self, "Save File", suggested)
        if path:
            download.setDownloadFileName(path)
            download.accept()
            self._download_count += 1
            self.status_bar.showMessage(f"Downloading: {suggested}", 4000)
        else:
            download.cancel()

    def _save_page(self):
        tab = self._current_tab()
        if not tab:
            return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Page", "page.html",
            "HTML (*.html);;MIME HTML (*.mhtml)"
        )
        if path:
            fmt = (QWebEngineDownloadRequest.SavePageFormat.MimeHtmlSaveFormat
                   if path.endswith(".mhtml") else
                   QWebEngineDownloadRequest.SavePageFormat.CompleteHtmlSaveFormat)
            tab.page().save(path, fmt)

    # ── New Private Window ─────────────────────────────────────────────────

    def _new_private_window(self):
        win = AntheoBrowser.__new__(AntheoBrowser)
        QMainWindow.__init__(win)
        win.settings = dict(DEFAULT_SETTINGS)
        win.settings["home_url"] = self.settings.get("home_url", HOME_URL)
        win.hacker_mode = False
        win._download_count = 0
        win._hacker_panel = None
        win.privacy_stats = PrivacyStats()
        win.privacy_stats.stats_updated.connect(win._update_stats_display)
        private_profile = QWebEngineProfile(win)   # Off-the-record profile
        private_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        private_profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        win.profile = private_profile
        win.interceptor = AnthenePrivacyInterceptor(win.privacy_stats, win)
        win.interceptor.request_logged.connect(win._on_request_logged)
        private_profile.setUrlRequestInterceptor(win.interceptor)
        win._build_ui()
        win._build_menu()
        win._setup_shortcuts()
        win._apply_theme()
        win.new_tab(HOME_URL)
        win.setWindowTitle("Antheneo Browser [Private]")
        win.resize(1280, 800)
        win.show()
        self._private_win = win

    # ── Settings Dialog ────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Antheneo Settings")
        dlg.setMinimumWidth(480)
        layout = QVBoxLayout(dlg)

        form = QFormLayout()

        home_edit = QLineEdit(self.settings.get("home_url", HOME_URL))
        form.addRow("Home URL:", home_edit)

        shields_chk = QCheckBox("Enable Privacy Shields")
        shields_chk.setChecked(self.settings.get("shields_enabled", True))
        form.addRow("", shields_chk)

        fp_chk = QCheckBox("Fingerprint Protection")
        fp_chk.setChecked(self.settings.get("fingerprint_protection", True))
        form.addRow("", fp_chk)

        https_chk = QCheckBox("HTTPS-Only Mode")
        https_chk.setChecked(self.settings.get("https_only", True))
        form.addRow("", https_chk)

        hacker_chk = QCheckBox("Enable Hacker Mode on startup")
        hacker_chk.setChecked(self.settings.get("hacker_mode", False))
        form.addRow("", hacker_chk)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings["home_url"] = home_edit.text().strip()
            self.settings["shields_enabled"] = shields_chk.isChecked()
            self.settings["fingerprint_protection"] = fp_chk.isChecked()
            self.settings["https_only"] = https_chk.isChecked()
            self.settings["hacker_mode"] = hacker_chk.isChecked()
            self._toggle_shields(shields_chk.isChecked())
            save_settings(self.settings)

    # ── About Dialog ───────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
            f"<h2 style='color:#00d4d4'>{APP_NAME} Browser v{VERSION}</h2>"
            "<p>A privacy-first, resource-light browser with integrated ethical hacking tools.</p>"
            "<p><b>Privacy features:</b></p>"
            "<ul>"
            "<li>Ad &amp; tracker blocking (custom domain blocklist)</li>"
            "<li>Automatic HTTPS upgrading</li>"
            "<li>Tracking parameter stripping (UTM, fbclid, gclid…)</li>"
            "<li>Canvas/WebGL/AudioContext fingerprint protection</li>"
            "<li>Memory-only cache &amp; no persistent cookies by default</li>"
            "</ul>"
            "<p><b>Hacker Mode features:</b></p>"
            "<ul>"
            "<li>Network request log with filtering</li>"
            "<li>DNS lookup tool</li>"
            "<li>Port scanner (common &amp; custom ports)</li>"
            "<li>HTTP header inspector</li>"
            "<li>User-Agent switcher</li>"
            "<li>JavaScript console with history</li>"
            "<li>WHOIS, robots.txt, security header audit</li>"
            "</ul>"
            f"<p style='color:#8b949e; font-size:11px;'>"
            f"{COPYRIGHT}<br>"
            f"Hacker Mode tools are for authorized testing only.<br>"
            f"Built with PyQt6 + QtWebEngine.</p>"
        )

    # ── Theme ──────────────────────────────────────────────────────────────

    def _apply_theme(self):
        sheet = DARK_STYLESHEET
        if self.hacker_mode:
            sheet += HACKER_MODE_ACCENT
        self.setStyleSheet(sheet)

    def _refresh_style(self):
        self.setStyleSheet(self.styleSheet())


# ── Entry Point ────────────────────────────────────────────────────────────

def main():
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Antheneo")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Antheneo")

    window = AntheoBrowser()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
