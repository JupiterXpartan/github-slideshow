"""Persistent bot state — keeps PnL/drawdown across restarts."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .risk import Position, RiskState

log = logging.getLogger(__name__)


def load_state(path: Path, initial_bankroll: float) -> RiskState:
    if not path.exists():
        log.info("no state file at %s; starting fresh with bankroll $%.2f", path, initial_bankroll)
        return RiskState(initial_bankroll=initial_bankroll)
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        log.warning("state file %s is corrupt; starting fresh", path)
        return RiskState(initial_bankroll=initial_bankroll)

    state = RiskState(
        initial_bankroll=raw.get("initial_bankroll", initial_bankroll),
        realized_pnl=raw.get("realized_pnl", 0.0),
        halted=raw.get("halted", False),
        halt_reason=raw.get("halt_reason", ""),
    )
    for tok, p in raw.get("positions", {}).items():
        state.positions[tok] = Position(
            token_id=p["token_id"],
            side=p["side"],
            entry_price=p["entry_price"],
            shares=p["shares"],
            opened_ts=p.get("opened_ts", 0.0),
        )
    log.info(
        "restored state: realized=$%.2f, %d open positions, halted=%s",
        state.realized_pnl, len(state.positions), state.halted,
    )
    return state


def save_state(path: Path, state: RiskState) -> None:
    payload = {
        "initial_bankroll": state.initial_bankroll,
        "realized_pnl": state.realized_pnl,
        "halted": state.halted,
        "halt_reason": state.halt_reason,
        "positions": {
            tok: {
                "token_id": p.token_id,
                "side": p.side,
                "entry_price": p.entry_price,
                "shares": p.shares,
                "opened_ts": p.opened_ts,
            }
            for tok, p in state.positions.items()
        },
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)
