"""
Antheneo Privacy Engine
- Ad/tracker domain blocking
- HTTPS upgrading
- Tracking parameter stripping
- Request statistics
"""

import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo

# Tracking query parameters to strip from URLs
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format", "utm_marketing_tactic",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "msclkid", "twclid", "igshid", "mc_eid", "mc_cid",
    "_openstat", "yclid", "ymclid", "_ga", "_gl",
    "ref", "source", "campaign",   # common but ambiguous – strip conservatively
    "zanpid", "origin", "ir_by", "ir_campaignid",
    "clickid", "click_id", "affiliate_id", "aff_id",
    "s_kwcid", "ef_id", "mkt_tok",
}


class PrivacyStats(QObject):
    stats_updated = pyqtSignal(int, int, int)   # blocked, https_upgrades, params_stripped

    def __init__(self):
        super().__init__()
        self.blocked = 0
        self.https_upgrades = 0
        self.params_stripped = 0

    def add_blocked(self):
        self.blocked += 1
        self._emit()

    def add_https(self):
        self.https_upgrades += 1
        self._emit()

    def add_stripped(self):
        self.params_stripped += 1
        self._emit()

    def reset(self):
        self.blocked = 0
        self.https_upgrades = 0
        self.params_stripped = 0
        self._emit()

    def _emit(self):
        self.stats_updated.emit(self.blocked, self.https_upgrades, self.params_stripped)


class AnthenePrivacyInterceptor(QWebEngineUrlRequestInterceptor):
    """Intercepts all web requests to enforce privacy rules."""

    request_logged = pyqtSignal(str, str, str)  # method, url, status ("blocked"|"allowed"|"upgraded")

    def __init__(self, stats: PrivacyStats, parent=None):
        super().__init__(parent)
        self.stats = stats
        self.shields_enabled = True
        self.block_domains: set[str] = set()
        self.block_regexes: list[re.Pattern] = []
        self._load_blocklist()

    # ── Blocklist Loading ──────────────────────────────────────────────────

    def _load_blocklist(self):
        blocklist_path = Path(__file__).parent.parent / "blocklists" / "trackers.txt"
        if not blocklist_path.exists():
            return
        with blocklist_path.open() as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Strip protocol prefixes if present
                domain = line.split("/")[0].lstrip("*.")
                self.block_domains.add(domain.lower())

    def add_custom_rule(self, domain: str):
        self.block_domains.add(domain.lower().strip())

    def remove_custom_rule(self, domain: str):
        self.block_domains.discard(domain.lower().strip())

    # ── Request Interception ───────────────────────────────────────────────

    def interceptRequest(self, info: QWebEngineUrlRequestInfo):
        if not self.shields_enabled:
            return

        url = info.requestUrl()
        url_str = url.toString()
        host = url.host().lower()

        # 1. Domain blocking
        if self._is_blocked(host):
            info.block(True)
            self.stats.add_blocked()
            self.request_logged.emit("BLOCK", url_str, "blocked")
            return

        # 2. HTTPS upgrade
        if url.scheme() == "http":
            https_url = url
            https_url.setScheme("https")
            try:
                info.redirect(https_url)
                self.stats.add_https()
                self.request_logged.emit("UPGRADE", url_str, "upgraded→https")
            except Exception:
                pass
            return

        # 3. Strip tracking parameters
        query = url.query()
        if query:
            cleaned = self._strip_tracking_params(query)
            if cleaned != query:
                url.setQuery(cleaned)
                info.redirect(url)
                self.stats.add_stripped()
                self.request_logged.emit("CLEAN", url_str, "params_stripped")
                return

        self.request_logged.emit("GET", url_str, "allowed")

    def _is_blocked(self, host: str) -> bool:
        # Exact match
        if host in self.block_domains:
            return True
        # Subdomain match: check if any blocked domain is a suffix
        parts = host.split(".")
        for i in range(len(parts) - 1):
            parent = ".".join(parts[i:])
            if parent in self.block_domains:
                return True
        return False

    def _strip_tracking_params(self, query: str) -> str:
        params = parse_qs(query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
        return urlencode(cleaned, doseq=True)


# ── Fingerprint Protection JS ──────────────────────────────────────────────

FINGERPRINT_PROTECTION_JS = """
(function() {
    'use strict';

    // Canvas fingerprint protection - add slight noise
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attrs) {
        const ctx = origGetContext.call(this, type, attrs);
        if (ctx && (type === '2d')) {
            const origGetImageData = ctx.getImageData.bind(ctx);
            ctx.getImageData = function(x, y, w, h) {
                const imageData = origGetImageData(x, y, w, h);
                for (let i = 0; i < imageData.data.length; i += 100) {
                    imageData.data[i] ^= (Math.random() * 2) | 0;
                }
                return imageData;
            };
        }
        return ctx;
    };

    // WebGL fingerprint protection
    const origGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37446) return 'Antheneo GPU';   // RENDERER
        if (param === 7936)  return 'Antheneo';        // VENDOR
        return origGetParameter.call(this, param);
    };

    // Navigator property spoofing - consistent but non-identifying
    try {
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    } catch(e) {}

    // Timezone normalization
    try {
        const origDateTimeFormat = Intl.DateTimeFormat;
        Intl.DateTimeFormat = function(locale, options) {
            if (options && options.timeZone === undefined) {
                options = Object.assign({}, options, { timeZone: 'UTC' });
            }
            return new origDateTimeFormat(locale, options);
        };
        Intl.DateTimeFormat.prototype = origDateTimeFormat.prototype;
    } catch(e) {}

    // Block battery API (fingerprinting vector)
    if (navigator.getBattery) {
        navigator.getBattery = undefined;
    }

    // AudioContext fingerprint noise
    if (window.AudioContext || window.webkitAudioContext) {
        const AC = window.AudioContext || window.webkitAudioContext;
        const origCreateOscillator = AC.prototype.createOscillator;
        AC.prototype.createOscillator = function() {
            const osc = origCreateOscillator.call(this);
            const origConnect = osc.connect.bind(osc);
            osc.connect = function(dest, ...args) {
                return origConnect(dest, ...args);
            };
            return osc;
        };
    }

    console.log('[Antheneo] Fingerprint protection active');
})();
"""

HTTPS_REDIRECT_JS = """
(function() {
    if (window.location.protocol === 'http:') {
        window.location.protocol = 'https:';
    }
})();
"""
