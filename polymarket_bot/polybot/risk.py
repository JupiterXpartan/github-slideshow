"""Risk management: Kelly sizing, stop-loss / take-profit, drawdown breaker.

This module is deliberately framework-free — it does not touch the network or
the CLOB client, so it is unit-testable and reusable from any execution venue.

Sizing model
------------
For a binary Polymarket outcome priced at `p_market`, buying YES costs
`p_market` and pays $1 if the event resolves true. The decimal odds are
`b = (1 - p_market) / p_market`. With our model probability `p_true`:

    f* = (b * p_true - (1 - p_true)) / b
       = (p_true - p_market) / (1 - p_market)        # for the YES side
       = (p_market - p_true) / p_market              # for the NO side

We always apply *fractional* Kelly (default 1/4) because:
  * `p_true` is uncertain — full Kelly compounds estimation error.
  * Polymarket markets can be thin; full Kelly trades cause execution slippage.
  * Drawdowns under fractional Kelly are dramatically more tolerable.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)

Side = Literal["BUY", "SELL"]


@dataclass
class Position:
    """Live position in a single outcome token."""

    token_id: str
    side: Side                # BUY = long the token; SELL = short via opposite token
    entry_price: float
    shares: float
    opened_ts: float = field(default_factory=time.time)

    def cost_basis(self) -> float:
        return self.entry_price * self.shares

    def unrealized_pnl(self, mark_price: float) -> float:
        """USD PnL if we marked the position to `mark_price` right now."""
        return (mark_price - self.entry_price) * self.shares

    def unrealized_pnl_pct(self, mark_price: float) -> float:
        basis = self.cost_basis()
        if basis <= 0:
            return 0.0
        return self.unrealized_pnl(mark_price) / basis


@dataclass
class RiskState:
    """Mutable bankroll/PnL state persisted across restarts."""

    initial_bankroll: float
    realized_pnl: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    positions: dict[str, Position] = field(default_factory=dict)

    def equity(self, marks: dict[str, float]) -> float:
        unreal = 0.0
        for tok, pos in self.positions.items():
            mark = marks.get(tok, pos.entry_price)
            unreal += pos.unrealized_pnl(mark)
        return self.initial_bankroll + self.realized_pnl + unreal

    def drawdown_pct(self, marks: dict[str, float]) -> float:
        eq = self.equity(marks)
        return (self.initial_bankroll - eq) / self.initial_bankroll


class RiskManager:
    """Sizing + protective-exit decisions."""

    def __init__(
        self,
        state: RiskState,
        *,
        kelly_fraction: float,
        min_trade_usdc: float,
        max_trade_usdc: float,
        min_edge: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        max_drawdown_pct: float,
        max_open_positions: int,
        max_slippage_bps: int,
    ):
        self.state = state
        self.kelly_fraction = kelly_fraction
        self.min_trade_usdc = min_trade_usdc
        self.max_trade_usdc = max_trade_usdc
        self.min_edge = min_edge
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_open_positions = max_open_positions
        self.max_slippage_bps = max_slippage_bps

    # ---------------------------------------------------------------- sizing

    def kelly_size_usd(
        self,
        *,
        side: Side,
        market_price: float,
        true_prob: float,
        bankroll: float,
    ) -> float:
        """Return a fractional-Kelly USD stake. Returns 0 if no edge."""
        if not (0 < market_price < 1):
            return 0.0
        if not (0 < true_prob < 1):
            return 0.0

        if side == "BUY":
            edge = true_prob - market_price
            if edge < self.min_edge:
                return 0.0
            denom = 1.0 - market_price
        else:  # SELL = buy the opposite token, equivalent to fading at p_market
            edge = market_price - true_prob
            if edge < self.min_edge:
                return 0.0
            denom = market_price

        if denom <= 0:
            return 0.0

        f_star = edge / denom
        stake = max(0.0, f_star) * self.kelly_fraction * bankroll
        return float(min(self.max_trade_usdc, max(0.0, stake)))

    # ----------------------------------------------------- protective exits

    def should_exit(self, pos: Position, mark_price: float) -> tuple[bool, str]:
        pnl_pct = pos.unrealized_pnl_pct(mark_price)
        if pnl_pct <= -abs(self.stop_loss_pct):
            return True, f"stop-loss {pnl_pct:.2%}"
        if pnl_pct >= abs(self.take_profit_pct):
            return True, f"take-profit {pnl_pct:.2%}"
        return False, ""

    # ---------------------------------------------------- circuit breakers

    def check_drawdown(self, marks: dict[str, float]) -> bool:
        """Return True and flip the halt flag if drawdown exceeds threshold."""
        if self.state.halted:
            return True
        dd = self.state.drawdown_pct(marks)
        if dd >= self.max_drawdown_pct:
            self.state.halted = True
            self.state.halt_reason = (
                f"max drawdown breached: {dd:.2%} >= {self.max_drawdown_pct:.2%}"
            )
            log.error("CIRCUIT BREAKER: %s", self.state.halt_reason)
            return True
        return False

    def can_open_new(self) -> bool:
        if self.state.halted:
            return False
        return len(self.state.positions) < self.max_open_positions

    # --------------------------------------------------------- slippage gate

    def slippage_ok(self, quote_price: float, fill_price: float) -> bool:
        if quote_price <= 0:
            return False
        slip_bps = abs(fill_price - quote_price) / quote_price * 10_000
        return slip_bps <= self.max_slippage_bps

    # ------------------------------------------------------ position book

    def open_position(
        self, token_id: str, side: Side, entry_price: float, shares: float
    ) -> Position:
        pos = Position(token_id=token_id, side=side, entry_price=entry_price, shares=shares)
        self.state.positions[token_id] = pos
        log.info(
            "OPEN %s %.2f shares @ %.4f (cost $%.2f) tok=%s",
            side, shares, entry_price, pos.cost_basis(), token_id[:10],
        )
        return pos

    def close_position(self, token_id: str, exit_price: float) -> float:
        pos = self.state.positions.pop(token_id, None)
        if pos is None:
            return 0.0
        pnl = pos.unrealized_pnl(exit_price)
        self.state.realized_pnl += pnl
        log.info(
            "CLOSE %s @ %.4f -> realised $%.2f (cum $%.2f) tok=%s",
            pos.side, exit_price, pnl, self.state.realized_pnl, token_id[:10],
        )
        return pnl
