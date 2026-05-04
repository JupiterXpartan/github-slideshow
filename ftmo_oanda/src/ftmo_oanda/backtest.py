"""Bar-by-bar backtester.

Walks the strategy across historical candles, simulating one bracketed entry
at a time per instrument. Each bar after entry checks whether the high or low
hit the stop or target (stop is checked first when both are touched on the
same bar - conservative).

Outputs a summary dict with realistic stats: trades, win rate, expectancy,
max drawdown, profit factor, average R, ending equity. **No 90% win rate
miracles.**
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .risk import FtmoRiskManager, TradeResult
from .strategies.ema_atr_trend import EmaAtrTrendStrategy, Signal
from .timeframe import TimeframeProfile


@dataclass
class OpenTrade:
    instrument: str
    side: str
    units: int
    entry: float
    stop: float
    target: float
    opened_at: pd.Timestamp


def _exit_price(bar: pd.Series, trade: OpenTrade) -> Optional[float]:
    """Stop checked before target on the same bar (conservative)."""
    high, low = float(bar["high"]), float(bar["low"])
    if trade.side == "long":
        if low <= trade.stop:
            return trade.stop
        if high >= trade.target:
            return trade.target
    else:
        if high >= trade.stop:
            return trade.stop
        if low <= trade.target:
            return trade.target
    return None


def run_backtest(
    candles: pd.DataFrame,
    profile: TimeframeProfile,
    risk: FtmoRiskManager,
    instrument: str = "EUR_USD",
    pip_value_per_unit: float = 1.0,
) -> Dict[str, float]:
    """Run a single-instrument backtest. ``candles`` must have OHLC columns."""
    strategy = EmaAtrTrendStrategy(profile)
    df = strategy.annotate(candles).dropna()
    if df.empty:
        return {"error": "not enough bars after warmup"}

    open_trade: Optional[OpenTrade] = None
    cooldown = 0
    equity_curve: List[float] = []

    for ts, bar in df.iterrows():
        # Manage open trade first.
        if open_trade is not None:
            ex = _exit_price(bar, open_trade)
            if ex is not None:
                pnl_per_unit = (
                    (ex - open_trade.entry)
                    if open_trade.side == "long"
                    else (open_trade.entry - ex)
                ) * pip_value_per_unit
                pnl = pnl_per_unit * abs(open_trade.units)
                risk.record_trade(
                    TradeResult(
                        instrument=instrument,
                        units=open_trade.units,
                        entry=open_trade.entry,
                        exit=ex,
                        pnl=pnl,
                        opened_at=open_trade.opened_at.to_pydatetime(),
                        closed_at=ts.to_pydatetime(),
                    )
                )
                open_trade = None
                cooldown = profile.cooldown_bars

        equity_curve.append(risk.state.equity)

        # Hard stop if FTMO total-loss breached.
        if risk.state.equity <= risk.total_loss_floor:
            break

        if cooldown > 0:
            cooldown -= 1
            continue
        if open_trade is not None:
            continue

        # Need a window ending at this bar to evaluate signal.
        window = df.loc[:ts]
        sig: Optional[Signal] = strategy.signal(window)
        if sig is None:
            continue

        ok, _ = risk.can_open_new_trade()
        if not ok:
            continue

        units = risk.position_size(sig.entry, sig.stop, pip_value_per_unit)
        if units == 0:
            continue
        risk.state.open_positions += 1
        open_trade = OpenTrade(
            instrument=instrument,
            side=sig.side,
            units=units,
            entry=sig.entry,
            stop=sig.stop,
            target=sig.target,
            opened_at=ts,
        )

    return _summarize(risk, equity_curve)


def _summarize(risk: FtmoRiskManager, equity_curve: List[float]) -> Dict[str, float]:
    trades = risk.state.closed_trades
    n = len(trades)
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)

    eq = pd.Series(equity_curve) if equity_curve else pd.Series([risk.state.equity])
    peak = eq.cummax()
    drawdown = (eq - peak) / peak
    max_dd_pct = float(drawdown.min() * 100) if not drawdown.empty else 0.0

    return {
        "trades": float(n),
        "win_rate_pct": (100.0 * len(wins) / n) if n else 0.0,
        "avg_win": (gross_win / len(wins)) if wins else 0.0,
        "avg_loss": (gross_loss / len(losses)) if losses else 0.0,
        "expectancy": (sum(pnls) / n) if n else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win else 0.0,
        "max_drawdown_pct": max_dd_pct,
        "starting_equity": risk.state.initial_balance,
        "ending_equity": risk.state.equity,
        "return_pct": (risk.state.equity / risk.state.initial_balance - 1) * 100,
    }
