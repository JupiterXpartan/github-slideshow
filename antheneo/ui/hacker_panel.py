"""
Antheneo Hacker Tools Panel
Ethical hacking / pentest helper tools integrated into the browser.
Only available when Hacker Mode is enabled.
"""

import socket
import subprocess
import json
import re
from datetime import datetime
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QComboBox, QCheckBox, QGroupBox,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QFormLayout, QFrame, QMenu, QApplication, QAbstractItemView,
)
from PyQt6.QtGui import QColor, QFont, QAction, QClipboard


# ── Worker threads ─────────────────────────────────────────────────────────

class DNSWorker(QThread):
    result_ready = pyqtSignal(str, list)   # host, records
    error = pyqtSignal(str)

    def __init__(self, host: str, record_types: list[str]):
        super().__init__()
        self.host = host
        self.record_types = record_types

    def run(self):
        results = []
        try:
            # A record via getaddrinfo
            infos = socket.getaddrinfo(self.host, None)
            seen = set()
            for info in infos:
                ip = info[4][0]
                if ip not in seen:
                    seen.add(ip)
                    results.append(("A/AAAA", ip))
            # Reverse lookup
            for ip in list(seen)[:3]:
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                    results.append(("PTR", f"{ip} → {hostname}"))
                except Exception:
                    pass
            self.result_ready.emit(self.host, results)
        except Exception as e:
            self.error.emit(str(e))


class PortScanWorker(QThread):
    port_result = pyqtSignal(int, bool, str)   # port, open, service
    finished = pyqtSignal()

    COMMON_PORTS = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
        53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
        443: "HTTPS", 465: "SMTPS", 587: "SMTP/TLS",
        993: "IMAPS", 995: "POP3S", 3306: "MySQL",
        3389: "RDP", 5432: "PostgreSQL", 6379: "Redis",
        8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB",
    }

    def __init__(self, host: str, ports: list[int], timeout: float = 0.5):
        super().__init__()
        self.host = host
        self.ports = ports
        self.timeout = timeout
        self._stop = False

    def run(self):
        for port in self.ports:
            if self._stop:
                break
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(self.timeout)
                    result = s.connect_ex((self.host, port))
                    is_open = result == 0
                    service = self.COMMON_PORTS.get(port, "unknown")
                    self.port_result.emit(port, is_open, service)
            except Exception:
                self.port_result.emit(port, False, "error")
        self.finished.emit()

    def stop(self):
        self._stop = True


# ── Network Log Tab ────────────────────────────────────────────────────────

class NetworkLogWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        bar = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by URL or method…")
        self.filter_edit.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter_edit)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedWidth(60)
        self.btn_clear.clicked.connect(self.clear)
        bar.addWidget(self.btn_clear)

        self.chk_blocked = QCheckBox("Blocked only")
        self.chk_blocked.stateChanged.connect(self._apply_filter)
        bar.addWidget(self.chk_blocked)
        layout.addLayout(bar)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Method", "Status", "URL", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self._all_rows: list[tuple] = []

    def log_request(self, method: str, url: str, status: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._all_rows.append((method, status, url, timestamp))
        self._apply_filter()

    def _apply_filter(self):
        filter_text = self.filter_edit.text().lower()
        blocked_only = self.chk_blocked.isChecked()

        self.table.setRowCount(0)
        for method, status, url, ts in self._all_rows:
            if blocked_only and status != "blocked":
                continue
            if filter_text and filter_text not in url.lower() and filter_text not in method.lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            items = [
                QTableWidgetItem(method),
                QTableWidgetItem(status),
                QTableWidgetItem(url),
                QTableWidgetItem(ts),
            ]
            # Color coding
            color_map = {
                "blocked":  "#f85149",
                "upgraded→https": "#3fb950",
                "params_stripped": "#d29922",
                "allowed":  "#8b949e",
            }
            fg = QColor(color_map.get(status, "#e6edf3"))
            for item in items:
                item.setForeground(fg)
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        url_item = self.table.item(row, 2)
        if not url_item:
            return
        url = url_item.text()
        menu = QMenu(self)
        copy_act = QAction("Copy URL", self)
        copy_act.triggered.connect(lambda: QApplication.clipboard().setText(url))
        menu.addAction(copy_act)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def clear(self):
        self._all_rows.clear()
        self.table.setRowCount(0)


# ── DNS Lookup Tab ─────────────────────────────────────────────────────────

class DNSWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("DNS Lookup"))
        row = QHBoxLayout()
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("hostname or domain…")
        self.host_edit.returnPressed.connect(self.lookup)
        row.addWidget(self.host_edit)
        btn = QPushButton("Lookup")
        btn.clicked.connect(self.lookup)
        row.addWidget(btn)
        layout.addLayout(row)

        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["Type", "Value"])
        self.result_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.result_tree)

        self._worker = None

    def lookup(self):
        host = self.host_edit.text().strip()
        if not host:
            return
        self.result_tree.clear()
        loading = QTreeWidgetItem(["...", f"Resolving {host}"])
        self.result_tree.addTopLevelItem(loading)

        self._worker = DNSWorker(host, ["A", "AAAA", "PTR"])
        self._worker.result_ready.connect(self._show_results)
        self._worker.error.connect(self._show_error)
        self._worker.start()

    def _show_results(self, host: str, records: list):
        self.result_tree.clear()
        parent = QTreeWidgetItem([host, f"{len(records)} records"])
        self.result_tree.addTopLevelItem(parent)
        for rtype, value in records:
            item = QTreeWidgetItem([rtype, value])
            parent.addChild(item)
        self.result_tree.expandAll()

    def _show_error(self, err: str):
        self.result_tree.clear()
        self.result_tree.addTopLevelItem(QTreeWidgetItem(["ERROR", err]))


# ── Port Scanner Tab ───────────────────────────────────────────────────────

class PortScanWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        label = QLabel("Port Scanner")
        label.setObjectName("heading")
        layout.addWidget(label)

        sub = QLabel("Scan only targets you own or have explicit written permission to test.")
        sub.setObjectName("subheading")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        form = QFormLayout()
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("target hostname / IP")
        form.addRow("Host:", self.host_edit)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems([
            "Common 20 ports",
            "Top 100 ports",
            "Well-known (1-1024)",
            "Custom range",
        ])
        form.addRow("Scope:", self.scope_combo)

        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText("e.g. 80,443,8080-8090")
        self.custom_edit.setEnabled(False)
        self.scope_combo.currentIndexChanged.connect(
            lambda i: self.custom_edit.setEnabled(i == 3))
        form.addRow("Custom ports:", self.custom_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("Start Scan")
        self.btn_scan.setObjectName("accent")
        self.btn_scan.clicked.connect(self.start_scan)
        btn_row.addWidget(self.btn_scan)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self.stop_scan)
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)
        layout.addLayout(btn_row)

        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(["Port", "State", "Service"])
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.result_table)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subheading")
        layout.addWidget(self.status_label)

        self._worker = None

    def _parse_ports(self) -> list[int]:
        idx = self.scope_combo.currentIndex()
        if idx == 0:
            return list(PortScanWorker.COMMON_PORTS.keys())
        if idx == 1:
            return list(range(1, 1025))[:100]
        if idx == 2:
            return list(range(1, 1025))
        # Custom
        ports = []
        for part in self.custom_edit.text().split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                try:
                    ports.extend(range(int(a), int(b) + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                ports.append(int(part))
        return ports

    def start_scan(self):
        host = self.host_edit.text().strip()
        if not host:
            return
        ports = self._parse_ports()
        self.result_table.setRowCount(0)
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText(f"Scanning {len(ports)} ports on {host}…")

        self._worker = PortScanWorker(host, ports)
        self._worker.port_result.connect(self._add_result)
        self._worker.finished.connect(self._scan_done)
        self._worker.start()

    def stop_scan(self):
        if self._worker:
            self._worker.stop()

    def _add_result(self, port: int, is_open: bool, service: str):
        if not is_open:
            return  # Only show open ports
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        items = [
            QTableWidgetItem(str(port)),
            QTableWidgetItem("OPEN"),
            QTableWidgetItem(service),
        ]
        for item in items:
            item.setForeground(QColor("#3fb950"))
        for col, item in enumerate(items):
            self.result_table.setItem(row, col, item)

    def _scan_done(self):
        open_count = self.result_table.rowCount()
        self.status_label.setText(f"Scan complete — {open_count} open ports found")
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)


# ── Header Inspector Tab ───────────────────────────────────────────────────

class HeaderInspectorWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Request / Response Headers"))

        row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Enter URL to inspect headers…")
        self.url_edit.returnPressed.connect(self.fetch_headers)
        row.addWidget(self.url_edit)
        btn = QPushButton("Fetch")
        btn.clicked.connect(self.fetch_headers)
        row.addWidget(btn)
        layout.addLayout(row)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["GET", "HEAD", "OPTIONS", "POST"])
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Method:"))
        row2.addWidget(self.method_combo)
        row2.addStretch()
        layout.addLayout(row2)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Response headers will appear here…")
        layout.addWidget(self.output)

    def fetch_headers(self):
        import urllib.request
        url = self.url_edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        method = self.method_combo.currentText()
        self.output.setPlainText(f"Fetching {method} {url}…\n")
        QTimer.singleShot(0, lambda: self._do_fetch(url, method))

    def _do_fetch(self, url: str, method: str):
        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Antheneo/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_line = f"HTTP/1.1 {resp.status} {resp.reason}\n"
                headers = "\n".join(f"{k}: {v}" for k, v in resp.getheaders())
                self.output.setPlainText(status_line + headers)
        except urllib.error.HTTPError as e:
            headers = "\n".join(f"{k}: {v}" for k, v in e.headers.items())
            self.output.setPlainText(f"HTTP {e.code} {e.reason}\n{headers}")
        except Exception as e:
            self.output.setPlainText(f"Error: {e}")


# ── User-Agent Switcher Tab ────────────────────────────────────────────────

PRESET_UAS = {
    "Antheneo (default)":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Antheneo/1.0 Privacy/Max",
    "Chrome 120 (Windows)":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Firefox 121 (Linux)":
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Safari 17 (macOS)":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mobile — iOS Safari":
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mobile — Android Chrome":
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.43 Mobile Safari/537.36",
    "Googlebot":
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "cURL":
        "curl/8.5.0",
    "Custom": "",
}


class UserAgentWidget(QWidget):
    ua_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("User-Agent Switcher"))

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESET_UAS.keys())
        self.preset_combo.currentTextChanged.connect(self._preset_selected)
        layout.addWidget(self.preset_combo)

        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("Custom user-agent string…")
        layout.addWidget(self.ua_edit)

        btn = QPushButton("Apply to Current Tab")
        btn.setObjectName("accent")
        btn.clicked.connect(self._apply)
        layout.addWidget(btn)

        self.active_label = QLabel("Active: Antheneo (default)")
        self.active_label.setObjectName("subheading")
        layout.addWidget(self.active_label)
        layout.addStretch()

    def _preset_selected(self, name: str):
        ua = PRESET_UAS.get(name, "")
        if ua:
            self.ua_edit.setText(ua)

    def _apply(self):
        ua = self.ua_edit.text().strip()
        if ua:
            self.ua_changed.emit(ua)
            preset = self.preset_combo.currentText()
            self.active_label.setText(f"Active: {preset}")


# ── JavaScript Console Tab ─────────────────────────────────────────────────

class JSConsoleWidget(QWidget):
    execute_js = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        layout.addWidget(QLabel("JavaScript Console"))

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Cascadia Code", 11))
        layout.addWidget(self.output, 1)

        input_row = QHBoxLayout()
        prompt = QLabel(">")
        prompt.setStyleSheet("color: #00d4d4; font-family: monospace; font-weight: bold;")
        input_row.addWidget(prompt)
        self.input_edit = QLineEdit()
        self.input_edit.setFont(QFont("Cascadia Code", 11))
        self.input_edit.setPlaceholderText("JavaScript expression…")
        self.input_edit.returnPressed.connect(self._run)
        input_row.addWidget(self.input_edit)
        btn = QPushButton("Run")
        btn.setFixedWidth(50)
        btn.clicked.connect(self._run)
        input_row.addWidget(btn)
        layout.addLayout(input_row)

        self._history: list[str] = []
        self._hist_idx = -1

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up and self._history:
            self._hist_idx = max(0, self._hist_idx - 1)
            self.input_edit.setText(self._history[self._hist_idx])
        elif event.key() == Qt.Key.Key_Down and self._history:
            self._hist_idx = min(len(self._history), self._hist_idx + 1)
            if self._hist_idx < len(self._history):
                self.input_edit.setText(self._history[self._hist_idx])
            else:
                self.input_edit.clear()
        super().keyPressEvent(event)

    def _run(self):
        code = self.input_edit.text().strip()
        if not code:
            return
        self._history.append(code)
        self._hist_idx = len(self._history)
        self.output.append(f'<span style="color:#00d4d4">» {code}</span>')
        self.input_edit.clear()
        self.execute_js.emit(code)

    def log_result(self, result: str, is_error: bool = False):
        color = "#f85149" if is_error else "#e6edf3"
        self.output.append(f'<span style="color:{color}">{result}</span>')


# ── WHOIS / Recon Tab ──────────────────────────────────────────────────────

class ReconWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        label = QLabel("Recon Tools")
        label.setObjectName("heading")
        layout.addWidget(label)

        tabs = QTabWidget()

        # WHOIS
        whois_w = QWidget()
        wl = QVBoxLayout(whois_w)
        row = QHBoxLayout()
        self.whois_edit = QLineEdit()
        self.whois_edit.setPlaceholderText("domain or IP…")
        self.whois_edit.returnPressed.connect(self.run_whois)
        row.addWidget(self.whois_edit)
        wb = QPushButton("WHOIS")
        wb.clicked.connect(self.run_whois)
        row.addWidget(wb)
        wl.addLayout(row)
        self.whois_out = QTextEdit()
        self.whois_out.setReadOnly(True)
        wl.addWidget(self.whois_out)
        tabs.addTab(whois_w, "WHOIS")

        # Robots.txt
        robots_w = QWidget()
        rl = QVBoxLayout(robots_w)
        row2 = QHBoxLayout()
        self.robots_edit = QLineEdit()
        self.robots_edit.setPlaceholderText("domain (e.g. example.com)…")
        self.robots_edit.returnPressed.connect(self.fetch_robots)
        row2.addWidget(self.robots_edit)
        rb = QPushButton("Fetch")
        rb.clicked.connect(self.fetch_robots)
        row2.addWidget(rb)
        rl.addLayout(row2)
        self.robots_out = QTextEdit()
        self.robots_out.setReadOnly(True)
        rl.addWidget(self.robots_out)
        tabs.addTab(robots_w, "robots.txt")

        # Security Headers Check
        headers_w = QWidget()
        hl = QVBoxLayout(headers_w)
        row3 = QHBoxLayout()
        self.sec_edit = QLineEdit()
        self.sec_edit.setPlaceholderText("https://target.com")
        self.sec_edit.returnPressed.connect(self.check_security_headers)
        row3.addWidget(self.sec_edit)
        hb = QPushButton("Check")
        hb.clicked.connect(self.check_security_headers)
        row3.addWidget(hb)
        hl.addLayout(row3)
        self.sec_out = QTextEdit()
        self.sec_out.setReadOnly(True)
        hl.addWidget(self.sec_out)
        tabs.addTab(headers_w, "Security Headers")

        layout.addWidget(tabs)

    def run_whois(self):
        target = self.whois_edit.text().strip()
        if not target:
            return
        self.whois_out.setPlainText(f"Running WHOIS for {target}…")
        QTimer.singleShot(0, lambda: self._do_whois(target))

    def _do_whois(self, target: str):
        try:
            result = subprocess.run(
                ["whois", target],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout or result.stderr or "No output"
            self.whois_out.setPlainText(output)
        except FileNotFoundError:
            self.whois_out.setPlainText(
                "whois not found. Install with: sudo apt install whois\n"
                "Or use: https://who.is/"
            )
        except subprocess.TimeoutExpired:
            self.whois_out.setPlainText("Timeout — WHOIS server did not respond.")
        except Exception as e:
            self.whois_out.setPlainText(f"Error: {e}")

    def fetch_robots(self):
        domain = self.robots_edit.text().strip().rstrip("/")
        if not domain:
            return
        if not domain.startswith("http"):
            domain = "https://" + domain
        url = f"{domain}/robots.txt"
        self.robots_out.setPlainText(f"Fetching {url}…")
        QTimer.singleShot(0, lambda: self._do_fetch(url, self.robots_out))

    def check_security_headers(self):
        url = self.sec_edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        self.sec_out.setPlainText(f"Checking security headers for {url}…")
        QTimer.singleShot(0, lambda: self._do_sec_check(url))

    def _do_fetch(self, url: str, output: QTextEdit):
        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 Antheneo/1.0"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                output.setPlainText(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            output.setPlainText(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            output.setPlainText(f"Error: {e}")

    def _do_sec_check(self, url: str):
        import urllib.request, urllib.error
        SECURITY_HEADERS = [
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Cross-Origin-Embedder-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
        ]
        try:
            req = urllib.request.Request(url, method="HEAD", headers={
                "User-Agent": "Mozilla/5.0 Antheneo/1.0"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                present = {k.lower(): v for k, v in resp.getheaders()}
        except urllib.error.HTTPError as e:
            present = {k.lower(): v for k, v in e.headers.items()}
        except Exception as e:
            self.sec_out.setPlainText(f"Error: {e}")
            return

        lines = [f"Security Header Audit: {url}\n{'─'*50}"]
        for h in SECURITY_HEADERS:
            val = present.get(h.lower())
            if val:
                lines.append(f"✔  {h}\n   {val}")
            else:
                lines.append(f"✘  {h}  ← MISSING")
        self.sec_out.setPlainText("\n".join(lines))


# ── Main Hacker Panel ──────────────────────────────────────────────────────

class HackerToolsPanel(QDockWidget):
    ua_changed = pyqtSignal(str)
    execute_js = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("⚡  Hacker Tools", parent)
        self.setObjectName("hacker_panel")
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(380)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Warning banner
        banner = QLabel(
            "⚠  For authorized testing only. Misuse may be illegal."
        )
        banner.setStyleSheet(
            "background:#2d1b00; color:#d29922; padding:6px 10px; "
            "border-bottom:1px solid #d29922; font-size:11px;"
        )
        banner.setWordWrap(True)
        main_layout.addWidget(banner)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("panel_tabs")

        self.net_log = NetworkLogWidget()
        self.tabs.addTab(self.net_log, "Network")

        self.dns_widget = DNSWidget()
        self.tabs.addTab(self.dns_widget, "DNS")

        self.port_scan = PortScanWidget()
        self.tabs.addTab(self.port_scan, "Port Scan")

        self.header_inspector = HeaderInspectorWidget()
        self.tabs.addTab(self.header_inspector, "Headers")

        self.ua_widget = UserAgentWidget()
        self.ua_widget.ua_changed.connect(self.ua_changed)
        self.tabs.addTab(self.ua_widget, "User-Agent")

        self.js_console = JSConsoleWidget()
        self.js_console.execute_js.connect(self.execute_js)
        self.tabs.addTab(self.js_console, "JS Console")

        self.recon_widget = ReconWidget()
        self.tabs.addTab(self.recon_widget, "Recon")

        main_layout.addWidget(self.tabs)
        self.setWidget(container)

    def log_request(self, method: str, url: str, status: str):
        self.net_log.log_request(method, url, status)

    def log_js_result(self, result: str, is_error: bool = False):
        self.js_console.log_result(result, is_error)
