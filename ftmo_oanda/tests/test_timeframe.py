import pytest

from ftmo_oanda.timeframe import all_profiles, for_timeframe


def test_all_known_timeframes_resolve():
    for code in ["M1", "M5", "M15", "M30", "H1", "H4", "D"]:
        p = for_timeframe(code)
        assert p.granularity == code
        assert p.atr_target_mult > p.atr_stop_mult, "reward should exceed risk"
        assert p.ema_fast < p.ema_slow
        assert p.risk_per_trade_pct > 0
        assert p.max_effective_leverage > 0


def test_unknown_timeframe_rejected():
    with pytest.raises(ValueError):
        for_timeframe("M2")


def test_profiles_scale_with_timeframe():
    profiles = all_profiles()
    # Risk-per-trade should be monotonically non-decreasing from M1 -> D.
    order = ["M1", "M5", "M15", "M30", "H1", "H4", "D"]
    risks = [profiles[c].risk_per_trade_pct for c in order]
    assert risks == sorted(risks), f"risk-per-trade not monotonic: {risks}"
    # Same for leverage cap.
    levs = [profiles[c].max_effective_leverage for c in order]
    assert levs == sorted(levs), f"leverage cap not monotonic: {levs}"
