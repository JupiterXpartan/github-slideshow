"""Timeframe-aware trading profiles.

Auto-adjusts risk-per-trade, effective leverage, ATR-stop multipliers, EMA
lookbacks, signal cooldown and maximum concurrent positions based on the
chosen OANDA candle granularity.

Lower timeframes -> more signals -> smaller risk-per-trade and tighter stops.
Higher timeframes -> fewer signals -> larger risk-per-trade and wider stops.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# Mapping of OANDA granularity codes to approximate minutes-per-bar.
GRANULARITY_MINUTES: Dict[str, int] = {
    "S5": 1 / 12,
    "S10": 1 / 6,
    "S30": 0.5,
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "H12": 720,
    "D": 1440,
    "W": 10080,
}


@dataclass(frozen=True)
class TimeframeProfile:
    """Settings derived from a timeframe.

    Attributes:
        granularity: OANDA candle code (e.g. "M15", "H1").
        minutes_per_bar: minutes covered by one bar.
        risk_per_trade_pct: % of account equity risked per trade.
        max_effective_leverage: leverage cap *this profile* will use, bounded
            by the broker / FTMO cap supplied by the risk manager.
        atr_period: ATR lookback in bars.
        atr_stop_mult: ATR multiples used for the stop-loss distance.
        atr_target_mult: ATR multiples used for the take-profit distance
            (this gives a constant reward:risk ratio = target/stop).
        ema_fast: fast EMA lookback.
        ema_slow: slow EMA lookback.
        cooldown_bars: bars to wait after a trade closes before a new entry
            on the same instrument.
        max_concurrent_positions: cap across all instruments.
        candles_history: how many bars to pull when warming up.
    """

    granularity: str
    minutes_per_bar: float
    risk_per_trade_pct: float
    max_effective_leverage: float
    atr_period: int
    atr_stop_mult: float
    atr_target_mult: float
    ema_fast: int
    ema_slow: int
    cooldown_bars: int
    max_concurrent_positions: int
    candles_history: int

    @property
    def reward_risk(self) -> float:
        return self.atr_target_mult / self.atr_stop_mult


# Hand-tuned profiles. Numbers err on the conservative side for FTMO:
# - daily-loss rule means many small losers must not blow the 5% cap;
# - the bot caps risk-per-trade well below the worst-case daily budget;
# - leverage stays well under FTMO's broker cap.
_PROFILES: Dict[str, TimeframeProfile] = {
    "M1": TimeframeProfile(
        granularity="M1",
        minutes_per_bar=1,
        risk_per_trade_pct=0.10,
        max_effective_leverage=5,
        atr_period=14,
        atr_stop_mult=1.5,
        atr_target_mult=2.25,
        ema_fast=8,
        ema_slow=21,
        cooldown_bars=10,
        max_concurrent_positions=1,
        candles_history=500,
    ),
    "M5": TimeframeProfile(
        granularity="M5",
        minutes_per_bar=5,
        risk_per_trade_pct=0.20,
        max_effective_leverage=8,
        atr_period=14,
        atr_stop_mult=1.75,
        atr_target_mult=2.75,
        ema_fast=12,
        ema_slow=34,
        cooldown_bars=6,
        max_concurrent_positions=2,
        candles_history=500,
    ),
    "M15": TimeframeProfile(
        granularity="M15",
        minutes_per_bar=15,
        risk_per_trade_pct=0.30,
        max_effective_leverage=10,
        atr_period=14,
        atr_stop_mult=2.0,
        atr_target_mult=3.0,
        ema_fast=20,
        ema_slow=50,
        cooldown_bars=4,
        max_concurrent_positions=2,
        candles_history=500,
    ),
    "M30": TimeframeProfile(
        granularity="M30",
        minutes_per_bar=30,
        risk_per_trade_pct=0.40,
        max_effective_leverage=12,
        atr_period=14,
        atr_stop_mult=2.0,
        atr_target_mult=3.0,
        ema_fast=20,
        ema_slow=50,
        cooldown_bars=3,
        max_concurrent_positions=3,
        candles_history=500,
    ),
    "H1": TimeframeProfile(
        granularity="H1",
        minutes_per_bar=60,
        risk_per_trade_pct=0.50,
        max_effective_leverage=15,
        atr_period=14,
        atr_stop_mult=2.0,
        atr_target_mult=3.5,
        ema_fast=21,
        ema_slow=55,
        cooldown_bars=3,
        max_concurrent_positions=3,
        candles_history=500,
    ),
    "H4": TimeframeProfile(
        granularity="H4",
        minutes_per_bar=240,
        risk_per_trade_pct=0.75,
        max_effective_leverage=20,
        atr_period=14,
        atr_stop_mult=2.5,
        atr_target_mult=4.0,
        ema_fast=21,
        ema_slow=55,
        cooldown_bars=2,
        max_concurrent_positions=4,
        candles_history=400,
    ),
    "D": TimeframeProfile(
        granularity="D",
        minutes_per_bar=1440,
        risk_per_trade_pct=1.00,
        max_effective_leverage=25,
        atr_period=14,
        atr_stop_mult=3.0,
        atr_target_mult=4.5,
        ema_fast=20,
        ema_slow=50,
        cooldown_bars=1,
        max_concurrent_positions=5,
        candles_history=300,
    ),
}


def for_timeframe(granularity: str) -> TimeframeProfile:
    """Return the profile for an OANDA granularity, raising on unknown codes."""
    key = granularity.upper()
    if key not in _PROFILES:
        raise ValueError(
            f"Unsupported timeframe '{granularity}'. "
            f"Choose one of: {', '.join(_PROFILES)}"
        )
    return _PROFILES[key]


def all_profiles() -> Dict[str, TimeframeProfile]:
    return dict(_PROFILES)
