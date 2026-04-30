"""Typed configuration loader.

All tunables live in `.env` so the bot can be reconfigured without code
changes. Validation is intentionally strict — bad config should crash at
startup, not silently produce wrong-sized orders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _f(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _i(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _s(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    return raw if raw not in (None, "") else default


def _list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    # Wallet / chain
    pk: str
    poly_funder: str
    signature_type: int
    chain_id: int

    # CLOB
    clob_host: str
    clob_ws_url: str
    clob_api_key: str
    clob_api_secret: str
    clob_api_passphrase: str

    # RPC
    polygon_rpc_url: str

    # LLM
    anthropic_api_key: str
    llm_model: str

    # Trading
    watchlist: list[str]
    bankroll_usdc: float
    min_trade_usdc: float
    max_trade_usdc: float
    kelly_fraction: float
    min_edge: float

    # Risk
    stop_loss_pct: float
    take_profit_pct: float
    max_drawdown_pct: float
    max_open_positions: int
    max_slippage_bps: int

    # Loop
    poll_interval_seconds: int
    order_ttl_seconds: int

    # Misc
    log_level: str
    state_file: Path = field(default_factory=lambda: Path("./bot_state.json"))

    @classmethod
    def load(cls, env_path: str | os.PathLike[str] | None = None) -> "Config":
        load_dotenv(env_path) if env_path else load_dotenv()

        pk = _s("PK")
        if not pk or not pk.startswith("0x") or len(pk) != 66:
            raise ValueError(
                "PK must be a 32-byte hex string starting with 0x. "
                "Refusing to start with an invalid private key."
            )

        cfg = cls(
            pk=pk,
            poly_funder=_s("POLY_FUNDER"),
            signature_type=_i("SIGNATURE_TYPE", 0),
            chain_id=_i("CHAIN_ID", 137),
            clob_host=_s("CLOB_HOST", "https://clob.polymarket.com"),
            clob_ws_url=_s(
                "CLOB_WS_URL",
                "wss://ws-subscriptions-clob.polymarket.com/ws/market",
            ),
            clob_api_key=_s("CLOB_API_KEY"),
            clob_api_secret=_s("CLOB_API_SECRET"),
            clob_api_passphrase=_s("CLOB_API_PASSPHRASE"),
            polygon_rpc_url=_s("POLYGON_RPC_URL", "https://polygon-rpc.com"),
            anthropic_api_key=_s("ANTHROPIC_API_KEY"),
            llm_model=_s("LLM_MODEL", "claude-sonnet-4-6"),
            watchlist=_list("WATCHLIST_CONDITION_IDS"),
            bankroll_usdc=_f("BANKROLL_USDC", 100.0),
            min_trade_usdc=_f("MIN_TRADE_USDC", 5.0),
            max_trade_usdc=_f("MAX_TRADE_USDC", 25.0),
            kelly_fraction=_f("KELLY_FRACTION", 0.25),
            min_edge=_f("MIN_EDGE", 0.04),
            stop_loss_pct=_f("STOP_LOSS_PCT", 0.20),
            take_profit_pct=_f("TAKE_PROFIT_PCT", 0.40),
            max_drawdown_pct=_f("MAX_DRAWDOWN_PCT", 0.25),
            max_open_positions=_i("MAX_OPEN_POSITIONS", 5),
            max_slippage_bps=_i("MAX_SLIPPAGE_BPS", 150),
            poll_interval_seconds=_i("POLL_INTERVAL_SECONDS", 15),
            order_ttl_seconds=_i("ORDER_TTL_SECONDS", 120),
            log_level=_s("LOG_LEVEL", "INFO"),
            state_file=Path(_s("STATE_FILE", "./bot_state.json")),
        )

        if cfg.min_trade_usdc <= 0 or cfg.max_trade_usdc < cfg.min_trade_usdc:
            raise ValueError("MAX_TRADE_USDC must be >= MIN_TRADE_USDC > 0")
        if not (0 < cfg.kelly_fraction <= 1):
            raise ValueError("KELLY_FRACTION must be in (0, 1]")
        if not (0 < cfg.max_drawdown_pct < 1):
            raise ValueError("MAX_DRAWDOWN_PCT must be in (0, 1)")
        if cfg.bankroll_usdc <= 0:
            raise ValueError("BANKROLL_USDC must be > 0")

        return cfg
