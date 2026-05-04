"""EMA-crossover trend strategy with ATR-based stops and targets.

Signal rules (evaluated on the most recent *closed* bar):

- Long  when ema_fast > ema_slow AND close > ema_slow AND ema_fast slope > 0
- Short when ema_fast < ema_slow AND close < ema_slow AND ema_fast slope < 0
- Otherwise flat.

Stop and target are derived from the timeframe's ATR multipliers, so a 5m
profile gets tighter brackets than an H4 profile automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ..indicators import atr, ema
from ..timeframe import TimeframeProfile


@dataclass
class Signal:
    side: str  # "long" or "short"
    entry: float
    stop: float
    target: float
    atr: float


class EmaAtrTrendStrategy:
    name = "ema_atr_trend"

    def __init__(self, profile: TimeframeProfile):
        self.profile = profile

    def required_bars(self) -> int:
        return max(self.profile.ema_slow, self.profile.atr_period) + 5

    def annotate(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()
        df["ema_fast"] = ema(df["close"], self.profile.ema_fast)
        df["ema_slow"] = ema(df["close"], self.profile.ema_slow)
        df["atr"] = atr(df, self.profile.atr_period)
        df["ema_fast_slope"] = df["ema_fast"].diff()
        return df

    def signal(self, candles: pd.DataFrame) -> Optional[Signal]:
        if len(candles) < self.required_bars():
            return None
        df = self.annotate(candles).dropna()
        if df.empty:
            return None

        last = df.iloc[-1]
        close = float(last["close"])
        a = float(last["atr"])
        if a <= 0:
            return None

        stop_dist = self.profile.atr_stop_mult * a
        target_dist = self.profile.atr_target_mult * a

        if (
            last["ema_fast"] > last["ema_slow"]
            and close > last["ema_slow"]
            and last["ema_fast_slope"] > 0
        ):
            return Signal(
                side="long",
                entry=close,
                stop=close - stop_dist,
                target=close + target_dist,
                atr=a,
            )
        if (
            last["ema_fast"] < last["ema_slow"]
            and close < last["ema_slow"]
            and last["ema_fast_slope"] < 0
        ):
            return Signal(
                side="short",
                entry=close,
                stop=close + stop_dist,
                target=close - target_dist,
                atr=a,
            )
        return None
