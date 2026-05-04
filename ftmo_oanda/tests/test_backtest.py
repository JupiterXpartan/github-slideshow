import numpy as np
import pandas as pd

from ftmo_oanda.backtest import run_backtest
from ftmo_oanda.config import FtmoConfig
from ftmo_oanda.risk import FtmoRiskManager
from ftmo_oanda.timeframe import for_timeframe


def _ohlc(close):
    idx = pd.date_range("2024-01-01", periods=len(close), freq="h", tz="UTC")
    c = np.asarray(close, dtype=float)
    h = c + 0.0005
    l = c - 0.0005
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c, "volume": 100}, index=idx)


def test_backtest_runs_and_reports_stats():
    profile = for_timeframe("H1")
    risk = FtmoRiskManager(FtmoConfig(), profile)
    # Trending then mean-reverting series, gives at least some signals.
    series = np.concatenate([np.linspace(1.10, 1.30, 600), np.linspace(1.30, 1.10, 600)])
    candles = _ohlc(series)
    stats = run_backtest(candles, profile, risk, instrument="EUR_USD", pip_value_per_unit=1.0)
    assert "trades" in stats
    assert stats["starting_equity"] == 100_000.0
    # Don't assert profitability - that would be cherry-picking.
    assert stats["trades"] >= 0
