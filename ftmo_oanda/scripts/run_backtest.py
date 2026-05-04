"""Entry point: backtest the strategy on historical OANDA candles.

Usage:
    python scripts/run_backtest.py --instrument EUR_USD --tf H1 --bars 5000
"""
from __future__ import annotations

import argparse
import logging

from ftmo_oanda.backtest import run_backtest
from ftmo_oanda.config import AppConfig
from ftmo_oanda.oanda_client import OandaClient
from ftmo_oanda.risk import FtmoRiskManager
from ftmo_oanda.timeframe import for_timeframe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instrument", default="EUR_USD")
    parser.add_argument("--tf", default=None, help="Override TIMEFRAME from .env")
    parser.add_argument("--bars", type=int, default=5000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = AppConfig.from_env()
    tf = args.tf or cfg.trading.timeframe
    profile = for_timeframe(tf)

    client = OandaClient(cfg.oanda)
    # OANDA caps a single candle request at 5000.
    chunk = min(args.bars, 5000)
    candles = client.candles(args.instrument, granularity=tf, count=chunk)
    if candles.empty:
        raise SystemExit(f"no candles returned for {args.instrument}/{tf}")

    risk = FtmoRiskManager(cfg.ftmo, profile)
    stats = run_backtest(candles, profile, risk, instrument=args.instrument)

    print(f"\nBacktest: {args.instrument} {tf}  ({len(candles)} bars)")
    print(f"  starting equity   {stats['starting_equity']:>14,.2f}")
    print(f"  ending equity     {stats['ending_equity']:>14,.2f}")
    print(f"  return            {stats['return_pct']:>14.2f}%")
    print(f"  trades            {int(stats['trades']):>14d}")
    print(f"  win rate          {stats['win_rate_pct']:>14.2f}%")
    print(f"  expectancy        {stats['expectancy']:>14.2f}")
    print(f"  profit factor     {stats['profit_factor']:>14.2f}")
    print(f"  max drawdown      {stats['max_drawdown_pct']:>14.2f}%")
    print(f"  avg win / loss    {stats['avg_win']:>7.2f} / {stats['avg_loss']:>7.2f}")


if __name__ == "__main__":
    main()
