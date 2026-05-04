import numpy as np
import pandas as pd

from ftmo_oanda.strategies.ema_atr_trend import EmaAtrTrendStrategy
from ftmo_oanda.timeframe import for_timeframe


def _candles(prices):
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="h", tz="UTC")
    p = np.asarray(prices, dtype=float)
    high = p + 0.001
    low = p - 0.001
    return pd.DataFrame(
        {"open": p, "high": high, "low": low, "close": p, "volume": 100},
        index=idx,
    )


def test_long_signal_on_clear_uptrend():
    profile = for_timeframe("H1")
    df = _candles(np.linspace(1.10, 1.20, 200))
    sig = EmaAtrTrendStrategy(profile).signal(df)
    assert sig is not None
    assert sig.side == "long"
    assert sig.target > sig.entry > sig.stop


def test_short_signal_on_clear_downtrend():
    profile = for_timeframe("H1")
    df = _candles(np.linspace(1.20, 1.10, 200))
    sig = EmaAtrTrendStrategy(profile).signal(df)
    assert sig is not None
    assert sig.side == "short"
    assert sig.stop > sig.entry > sig.target


def test_no_signal_on_flat_market():
    profile = for_timeframe("H1")
    df = _candles([1.10] * 200)
    assert EmaAtrTrendStrategy(profile).signal(df) is None


def test_required_bars_returned_when_too_few():
    profile = for_timeframe("H1")
    df = _candles([1.10, 1.11, 1.12])
    assert EmaAtrTrendStrategy(profile).signal(df) is None
