from datetime import datetime, timedelta, timezone

from ftmo_oanda.config import FtmoConfig
from ftmo_oanda.risk import FtmoRiskManager, TradeResult
from ftmo_oanda.timeframe import for_timeframe


def _mgr(equity: float = 100_000.0) -> FtmoRiskManager:
    return FtmoRiskManager(FtmoConfig(), for_timeframe("H1"), starting_equity=equity)


def test_position_size_respects_risk_per_trade():
    mgr = _mgr()
    units = mgr.position_size(entry_price=1.1000, stop_price=1.0950, pip_value_per_unit=1.0)
    # Risk = 0.50% of 100k = 500. stop_distance = 0.0050. units ~= 500/0.0050 = 100_000
    # But leverage cap (15x equity / entry) = 1_500_000 / 1.1 ~= 1.36M, doesn't bind.
    assert 95_000 <= units <= 105_000


def test_position_size_capped_by_leverage():
    mgr = _mgr(equity=1_000.0)
    # Tight stop forces huge size by risk math, but leverage clamps it.
    units = mgr.position_size(entry_price=1.10, stop_price=1.0999, pip_value_per_unit=1.0)
    max_notional = 1_000.0 * mgr.profile.max_effective_leverage
    assert units * 1.10 <= max_notional + 1


def test_short_returns_negative_units():
    mgr = _mgr()
    units = mgr.position_size(entry_price=1.1000, stop_price=1.1050, pip_value_per_unit=1.0)
    assert units < 0


def test_invalid_inputs_yield_zero_units():
    mgr = _mgr()
    assert mgr.position_size(1.1, 1.1, 1.0) == 0
    assert mgr.position_size(1.1, 1.0, 0.0) == 0


def test_daily_loss_blocks_new_trades():
    mgr = _mgr()
    # Simulate a loss equal to the daily budget.
    mgr.update_equity(mgr.state.equity - mgr.daily_loss_budget)
    ok, reason = mgr.can_open_new_trade()
    assert not ok
    assert "daily" in reason.lower()


def test_total_loss_blocks_new_trades():
    mgr = _mgr()
    mgr.update_equity(mgr.total_loss_floor - 1)
    ok, reason = mgr.can_open_new_trade()
    assert not ok
    assert "total" in reason.lower()


def test_profit_target_halts_trading():
    mgr = _mgr()
    mgr.update_equity(mgr.profit_target + 1)
    ok, reason = mgr.can_open_new_trade()
    assert not ok
    assert "target" in reason.lower()


def test_day_roll_resets_day_start_equity():
    mgr = _mgr()
    mgr.state.equity = 99_000
    mgr.state.day_start_equity = 100_000
    future = datetime.now(timezone.utc) + timedelta(days=1)
    mgr.roll_day_if_needed(future)
    assert mgr.state.day_start_equity == 99_000


def test_record_trade_updates_equity_and_open_count():
    mgr = _mgr()
    mgr.state.open_positions = 1
    now = datetime.now(timezone.utc)
    mgr.record_trade(
        TradeResult(
            instrument="EUR_USD",
            units=1000,
            entry=1.10,
            exit=1.11,
            pnl=10.0,
            opened_at=now,
            closed_at=now,
        )
    )
    assert mgr.state.equity == 100_010.0
    assert mgr.state.open_positions == 0
