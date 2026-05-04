"""Environment-driven configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val or ""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class OandaConfig:
    api_token: str
    account_id: str
    environment: str = "practice"

    @property
    def rest_host(self) -> str:
        return (
            "https://api-fxtrade.oanda.com"
            if self.environment == "live"
            else "https://api-fxpractice.oanda.com"
        )

    @property
    def stream_host(self) -> str:
        return (
            "https://stream-fxtrade.oanda.com"
            if self.environment == "live"
            else "https://stream-fxpractice.oanda.com"
        )


@dataclass
class FtmoConfig:
    initial_balance: float = 100_000.0
    profit_target_pct: float = 10.0
    max_daily_loss_pct: float = 5.0
    max_total_loss_pct: float = 10.0
    max_leverage: float = 30.0


@dataclass
class TradingConfig:
    instruments: List[str] = field(default_factory=lambda: ["EUR_USD"])
    timeframe: str = "H1"
    dry_run: bool = True


@dataclass
class AppConfig:
    oanda: OandaConfig
    ftmo: FtmoConfig
    trading: TradingConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            oanda=OandaConfig(
                api_token=_env("OANDA_API_TOKEN", required=True),
                account_id=_env("OANDA_ACCOUNT_ID", required=True),
                environment=_env("OANDA_ENVIRONMENT", "practice"),
            ),
            ftmo=FtmoConfig(
                initial_balance=_env_float("FTMO_INITIAL_BALANCE", 100_000.0),
                profit_target_pct=_env_float("FTMO_PROFIT_TARGET_PCT", 10.0),
                max_daily_loss_pct=_env_float("FTMO_MAX_DAILY_LOSS_PCT", 5.0),
                max_total_loss_pct=_env_float("FTMO_MAX_TOTAL_LOSS_PCT", 10.0),
                max_leverage=_env_float("FTMO_MAX_LEVERAGE", 30.0),
            ),
            trading=TradingConfig(
                instruments=[
                    s.strip()
                    for s in _env("INSTRUMENTS", "EUR_USD").split(",")
                    if s.strip()
                ],
                timeframe=_env("TIMEFRAME", "H1"),
                dry_run=_env_bool("DRY_RUN", True),
            ),
        )
