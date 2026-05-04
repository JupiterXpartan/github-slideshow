"""FTMO-aware risk manager.

Owns three responsibilities:

1. Position sizing - converts a risk-% + stop-distance into integer units of
   the instrument, respecting the timeframe profile's leverage cap and FTMO's
   broker leverage cap.
2. Pre-trade gating - refuses new trades when the daily-loss or total-loss
   guardrails would be breached, or when max-concurrent-positions is hit.
3. State tracking - records realized P&L per trade, equity high-water mark,
   and the start-of-day balance used for the daily-loss check.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from .config import FtmoConfig
from .timeframe import TimeframeProfile

log = logging.getLogger(__name__)


@dataclass
class TradeResult:
    instrument: str
    units: int
    entry: float
    exit: float
    pnl: float
    opened_at: datetime
    closed_at: datetime


@dataclass
class RiskState:
    initial_balance: float
    equity: float
    high_water_equity: float
    day_start_equity: float
    day: date
    open_positions: int = 0
    closed_trades: List[TradeResult] = field(default_factory=list)


class FtmoRiskManager:
    def __init__(self, ftmo: FtmoConfig, profile: TimeframeProfile, starting_equity: Optional[float] = None):
        self.ftmo = ftmo
        self.profile = profile
        bal = starting_equity if starting_equity is not None else ftmo.initial_balance
        today = datetime.now(timezone.utc).date()
        self.state = RiskState(
            initial_balance=ftmo.initial_balance,
            equity=bal,
            high_water_equity=bal,
            day_start_equity=bal,
            day=today,
        )

    # ---- equity bookkeeping -----------------------------------------------

    def roll_day_if_needed(self, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        if now.date() != self.state.day:
            self.state.day = now.date()
            self.state.day_start_equity = self.state.equity
            log.info("New trading day %s, day-start equity=%.2f", self.state.day, self.state.equity)

    def update_equity(self, equity: float) -> None:
        self.state.equity = equity
        if equity > self.state.high_water_equity:
            self.state.high_water_equity = equity

    def record_trade(self, result: TradeResult) -> None:
        self.state.closed_trades.append(result)
        self.update_equity(self.state.equity + result.pnl)
        self.state.open_positions = max(0, self.state.open_positions - 1)

    # ---- FTMO guardrails --------------------------------------------------

    @property
    def daily_loss_budget(self) -> float:
        return self.state.day_start_equity * (self.ftmo.max_daily_loss_pct / 100.0)

    @property
    def total_loss_floor(self) -> float:
        return self.state.initial_balance * (1 - self.ftmo.max_total_loss_pct / 100.0)

    @property
    def profit_target(self) -> float:
        return self.state.initial_balance * (1 + self.ftmo.profit_target_pct / 100.0)

    def daily_loss_used(self) -> float:
        return max(0.0, self.state.day_start_equity - self.state.equity)

    def total_loss_used(self) -> float:
        return max(0.0, self.state.initial_balance - self.state.equity)

    def can_open_new_trade(self) -> tuple[bool, str]:
        """Hard gate before any new entry. Returns (ok, reason)."""
        self.roll_day_if_needed()
        if self.state.equity <= self.total_loss_floor:
            return False, "FTMO max total loss breached"
        if self.daily_loss_used() >= self.daily_loss_budget:
            return False, "FTMO max daily loss reached"
        if self.state.equity >= self.profit_target:
            return False, "Profit target reached, stop trading"
        if self.state.open_positions >= self.profile.max_concurrent_positions:
            return False, "Max concurrent positions reached"
        return True, "ok"

    # ---- position sizing --------------------------------------------------

    def position_size(
        self,
        entry_price: float,
        stop_price: float,
        pip_value_per_unit: float,
        instrument_leverage_cap: Optional[float] = None,
    ) -> int:
        """Compute integer units to risk `risk_per_trade_pct` of equity.

        Args:
            entry_price: planned entry, in quote currency.
            stop_price: planned stop-loss, in quote currency.
            pip_value_per_unit: P&L per unit per 1.0 of price change in the
                account currency. For most pairs this is ~1 unit of quote
                currency per 1.0 price move; the bot uses the
                ``account.marginRate`` and instrument metadata for accuracy
                where needed. For backtests pass 1.0.
            instrument_leverage_cap: per-instrument leverage cap from OANDA
                instrument details, if known.

        Returns:
            Signed integer units. Positive for long (entry > stop), negative
            for short. 0 if risk inputs are invalid.
        """
        stop_distance = abs(entry_price - stop_price)
        if stop_distance <= 0 or self.state.equity <= 0:
            return 0

        risk_dollars = self.state.equity * (self.profile.risk_per_trade_pct / 100.0)
        # P&L per unit if price moves by stop_distance.
        loss_per_unit = stop_distance * pip_value_per_unit
        if loss_per_unit <= 0:
            return 0

        units = risk_dollars / loss_per_unit

        # Leverage cap: notional <= equity * effective_leverage.
        leverage_cap = self.profile.max_effective_leverage
        if instrument_leverage_cap is not None:
            leverage_cap = min(leverage_cap, instrument_leverage_cap)
        leverage_cap = min(leverage_cap, self.ftmo.max_leverage)

        max_notional = self.state.equity * leverage_cap
        max_units_by_leverage = max_notional / max(entry_price, 1e-9)
        units = min(units, max_units_by_leverage)

        signed = int(units) if entry_price > stop_price else -int(units)
        return signed

    # ---- summary ----------------------------------------------------------

    def status(self) -> Dict[str, float]:
        wins = [t for t in self.state.closed_trades if t.pnl > 0]
        losses = [t for t in self.state.closed_trades if t.pnl <= 0]
        n = len(self.state.closed_trades)
        return {
            "equity": self.state.equity,
            "high_water": self.state.high_water_equity,
            "day_start": self.state.day_start_equity,
            "daily_loss_used": self.daily_loss_used(),
            "daily_loss_budget": self.daily_loss_budget,
            "total_loss_used": self.total_loss_used(),
            "total_loss_floor": self.total_loss_floor,
            "profit_target": self.profit_target,
            "trades": float(n),
            "win_rate_pct": (100.0 * len(wins) / n) if n else 0.0,
            "avg_win": (sum(t.pnl for t in wins) / len(wins)) if wins else 0.0,
            "avg_loss": (sum(t.pnl for t in losses) / len(losses)) if losses else 0.0,
        }
