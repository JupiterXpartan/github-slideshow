"""
Antheneo Browser - Dark Cyberpunk Theme
"""

# Palette constants
BG_DEEP     = "#0d1117"
BG_PANEL    = "#161b22"
BG_WIDGET   = "#1c2128"
BG_HOVER    = "#21262d"
BG_ACTIVE   = "#2d333b"
ACCENT      = "#00d4d4"        # Cyan
ACCENT_DIM  = "#007f7f"
ACCENT_HACK = "#a855f7"        # Purple for hacker mode
DANGER      = "#f85149"
SUCCESS     = "#3fb950"
WARNING     = "#d29922"
TEXT_MAIN   = "#e6edf3"
TEXT_DIM    = "#8b949e"
TEXT_MUTED  = "#484f58"
BORDER      = "#30363d"
BORDER_FOCUS = "#00d4d4"

DARK_STYLESHEET = f"""
/* ─── Global ─────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_MAIN};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

/* ─── MenuBar ─────────────────────────────────────────────── */
QMenuBar {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    border-bottom: 1px solid {BORDER};
    padding: 2px 4px;
}}
QMenuBar::item:selected {{
    background-color: {BG_HOVER};
    border-radius: 4px;
}}
QMenu {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    margin: 1px 4px;
}}
QMenu::item:selected {{
    background-color: {BG_ACTIVE};
    color: {ACCENT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ─── ToolBar ─────────────────────────────────────────────── */
QToolBar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 4px 6px;
}}
QToolBar::separator {{
    background-color: {BORDER};
    width: 1px;
    margin: 4px 2px;
}}

/* ─── TabBar ─────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: {BG_DEEP};
}}
QTabBar {{
    background: {BG_PANEL};
}}
QTabBar::tab {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-right: 1px solid {BORDER};
    padding: 7px 14px 7px 12px;
    min-width: 120px;
    max-width: 220px;
}}
QTabBar::tab:selected {{
    background: {BG_WIDGET};
    color: {TEXT_MAIN};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background: {BG_HOVER};
    color: {TEXT_MAIN};
}}
QTabBar::close-button {{
    image: none;
    subcontrol-position: right;
}}

/* ─── AddressBar / LineEdit ───────────────────────────────── */
QLineEdit {{
    background-color: {BG_WIDGET};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 20px;
    padding: 5px 14px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
    background-color: {BG_ACTIVE};
}}
QLineEdit:hover {{
    border-color: {TEXT_MUTED};
}}

/* ─── Buttons ─────────────────────────────────────────────── */
QPushButton {{
    background-color: {BG_WIDGET};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {TEXT_DIM};
}}
QPushButton:pressed {{
    background-color: {BG_ACTIVE};
}}
QPushButton#accent {{
    background-color: {ACCENT_DIM};
    color: {BG_DEEP};
    border-color: {ACCENT};
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background-color: {ACCENT};
}}
QPushButton#danger {{
    background-color: transparent;
    color: {DANGER};
    border-color: {DANGER};
}}
QPushButton#danger:hover {{
    background-color: {DANGER};
    color: white;
}}
QPushButton#hacker {{
    background-color: #1a0030;
    color: {ACCENT_HACK};
    border-color: {ACCENT_HACK};
}}
QPushButton#hacker:hover {{
    background-color: #2d004d;
}}
QPushButton#hacker:checked {{
    background-color: #2d004d;
    color: #d18dff;
    border-color: #d18dff;
}}

QToolButton {{
    background-color: transparent;
    color: {TEXT_DIM};
    border: none;
    border-radius: 6px;
    padding: 5px 7px;
    font-size: 14px;
}}
QToolButton:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_MAIN};
}}
QToolButton:pressed, QToolButton:checked {{
    background-color: {BG_ACTIVE};
    color: {ACCENT};
}}

/* ─── Shield button states ───────────────────────────────── */
QPushButton#shield_on {{
    background-color: #003320;
    color: {SUCCESS};
    border-color: {SUCCESS};
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}
QPushButton#shield_off {{
    background-color: #330000;
    color: {DANGER};
    border-color: {DANGER};
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

/* ─── StatusBar ───────────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}

/* ─── ProgressBar ─────────────────────────────────────────── */
QProgressBar {{
    background-color: {BG_WIDGET};
    border: none;
    border-radius: 2px;
    height: 3px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 2px;
}}

/* ─── Dock / Panels ───────────────────────────────────────── */
QDockWidget {{
    titlebar-close-icon: url(none);
    color: {TEXT_MAIN};
    font-weight: 600;
}}
QDockWidget::title {{
    background: {BG_PANEL};
    padding: 6px 10px;
    border-bottom: 1px solid {BORDER};
}}
QDockWidget::close-button, QDockWidget::float-button {{
    background: transparent;
    border: none;
    padding: 2px;
}}

/* ─── ScrollBars ──────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BG_ACTIVE};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_DEEP};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_ACTIVE};
    border-radius: 4px;
    min-width: 20px;
}}

/* ─── Table / Tree / List ─────────────────────────────────── */
QTreeWidget, QListWidget, QTableWidget {{
    background: {BG_WIDGET};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    alternate-background-color: {BG_PANEL};
    outline: none;
}}
QTreeWidget::item, QListWidget::item, QTableWidget::item {{
    padding: 3px 6px;
    border-radius: 3px;
}}
QTreeWidget::item:selected, QListWidget::item:selected,
QTableWidget::item:selected {{
    background: {BG_ACTIVE};
    color: {ACCENT};
}}
QHeaderView::section {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 5px 8px;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
}}

/* ─── TextEdit ────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background: {BG_WIDGET};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px;
    font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
    font-size: 12px;
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}

/* ─── ComboBox ────────────────────────────────────────────── */
QComboBox {{
    background: {BG_WIDGET};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 120px;
}}
QComboBox:hover {{ border-color: {TEXT_DIM}; }}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    selection-background-color: {BG_ACTIVE};
    selection-color: {ACCENT};
    outline: none;
}}

/* ─── CheckBox ────────────────────────────────────────────── */
QCheckBox {{
    color: {TEXT_MAIN};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_WIDGET};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_DIM};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {TEXT_DIM};
}}

/* ─── GroupBox ────────────────────────────────────────────── */
QGroupBox {{
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 8px 10px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    background: {BG_DEEP};
    color: {TEXT_DIM};
}}

/* ─── Tab widget inside panels ───────────────────────────── */
QTabWidget#panel_tabs::pane {{
    background: {BG_WIDGET};
    border: 1px solid {BORDER};
    border-radius: 0 0 6px 6px;
}}
QTabBar#panel_tabs::tab {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 5px 12px;
    border-radius: 4px 4px 0 0;
    min-width: 80px;
}}
QTabBar#panel_tabs::tab:selected {{
    background: {BG_WIDGET};
    color: {ACCENT};
    border-bottom: 1px solid {BG_WIDGET};
}}

/* ─── Splitter ────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ─── Labels ──────────────────────────────────────────────── */
QLabel#stat_blocked {{
    color: {SUCCESS};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#stat_https {{
    color: {ACCENT};
    font-size: 11px;
}}
QLabel#url_secure {{
    color: {SUCCESS};
    font-size: 11px;
    padding: 2px 6px;
}}
QLabel#url_insecure {{
    color: {WARNING};
    font-size: 11px;
    padding: 2px 6px;
}}
QLabel#heading {{
    color: {ACCENT};
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#subheading {{
    color: {TEXT_DIM};
    font-size: 11px;
}}
"""

HACKER_MODE_ACCENT = f"""
QToolBar {{ border-bottom: 1px solid {ACCENT_HACK}; }}
QTabBar::tab:selected {{ border-bottom: 2px solid {ACCENT_HACK}; }}
QLineEdit:focus {{ border-color: {ACCENT_HACK}; }}
"""
