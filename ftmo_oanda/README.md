# FTMO / OANDA trading scaffold

A realistic, FTMO-aware algorithmic trading bot built on the OANDA v20 REST API.
Settings, position size, leverage, ATR brackets, and signal cadence **auto-adjust
to whatever timeframe you select** (M1 through D), so the same code runs sensibly
on a scalping setup or a swing setup.

> **Honest expectations.** This is not the viral-Twitter "90% win rate" system.
> A well-engineered trend-following bot like this one typically wins 40-55% of
> trades with positive expectancy when its rules and risk caps are respected.
> Anything claiming 90% on real, live, non-cherry-picked trades is almost
> certainly fiction. The point of this scaffold is to *survive* the FTMO daily-
> loss / total-loss rules while giving you a positive-expectancy edge to
> compound.

## What's in here

| File | Purpose |
| --- | --- |
| `src/ftmo_oanda/config.py` | Loads OANDA + FTMO + trading config from `.env` |
| `src/ftmo_oanda/oanda_client.py` | Minimal OANDA v20 REST client (candles, pricing, orders, positions) |
| `src/ftmo_oanda/timeframe.py` | `TimeframeProfile` - auto-adjusts risk / leverage / ATR / EMA / cooldown by granularity |
| `src/ftmo_oanda/risk.py` | `FtmoRiskManager` - daily-loss + total-loss + profit-target gates and position sizing |
| `src/ftmo_oanda/strategies/ema_atr_trend.py` | EMA-cross trend strategy with ATR stop / target |
| `src/ftmo_oanda/backtest.py` | Bar-by-bar backtester with realistic stats |
| `src/ftmo_oanda/bot.py` | Live trading loop |
| `src/ftmo_oanda/dashboard.py` | Rich terminal dashboard |
| `tests/` | Unit tests for risk, strategy, timeframe, backtester |

## Setup

```bash
cd ftmo_oanda
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# edit .env with your OANDA practice token + FTMO challenge parameters
```

Get an OANDA practice token at <https://www.oanda.com/demo-account/tpa/personal_token>.
**Always test on a practice account first.**

## Run

```bash
# Backtest the configured timeframe on historical candles
python scripts/run_backtest.py --instrument EUR_USD --tf H1 --bars 5000

# Read-only dashboard
python scripts/run_dashboard.py

# Live bot - DRY_RUN=true (default) only logs intended orders
python scripts/run_bot.py
```

To go live, set `DRY_RUN=false` in `.env`. The bot still refuses to place new
trades when daily loss, total loss, or profit target gates are tripped.

## How "auto-adjust by timeframe" works

`for_timeframe(code)` returns a frozen `TimeframeProfile`. Lower timeframes get
smaller risk-per-trade, tighter ATR multiples, faster EMAs, and lower effective
leverage; higher timeframes get the opposite. Every other component reads from
the active profile, so changing `TIMEFRAME=M15` to `TIMEFRAME=H4` in `.env`
adjusts:

- risk-per-trade (% of equity)
- max effective leverage (capped further by FTMO + per-instrument margin rate)
- ATR period and stop / target multipliers
- EMA fast / slow lookbacks
- bars to wait after a trade closes (cooldown)
- max concurrent positions across the portfolio
- candles requested per warmup

| TF  | Risk/trade | Max lev | ATR stop / tgt | EMA F/S | Cooldown | Max concurrent |
| --- | ---------- | ------- | -------------- | ------- | -------- | -------------- |
| M1  | 0.10%      | 5x      | 1.5 / 2.25     | 8 / 21  | 10 bars  | 1              |
| M5  | 0.20%      | 8x      | 1.75 / 2.75    | 12 / 34 | 6 bars   | 2              |
| M15 | 0.30%      | 10x     | 2.0 / 3.0      | 20 / 50 | 4 bars   | 2              |
| M30 | 0.40%      | 12x     | 2.0 / 3.0      | 20 / 50 | 3 bars   | 3              |
| H1  | 0.50%      | 15x     | 2.0 / 3.5      | 21 / 55 | 3 bars   | 3              |
| H4  | 0.75%      | 20x     | 2.5 / 4.0      | 21 / 55 | 2 bars   | 4              |
| D   | 1.00%      | 25x     | 3.0 / 4.5      | 20 / 50 | 1 bar    | 5              |

Tune the table in `timeframe.py` once you have a backtest you trust. The
defaults err on the conservative side so the FTMO 5%-day / 10%-total caps
absorb a normal losing streak.

## FTMO guardrails

`FtmoRiskManager.can_open_new_trade()` returns `False` when:

- equity has dropped to the **total-loss floor** (`initial * (1 - max_total_loss_pct/100)`)
- realized + unrealized losses since UTC midnight reach the **daily-loss budget**
- equity has already crossed the **profit target** (stop trading, lock the pass)
- open positions would exceed the timeframe's `max_concurrent_positions`

Position sizing computes the integer number of units that risks
`risk_per_trade_pct` of current equity over the planned stop distance, then
clamps the notional by the *minimum* of: timeframe leverage, OANDA per-
instrument leverage, and FTMO max leverage.

## Tests

```bash
pytest -q
```

17 tests cover the pieces that don't need a live OANDA account: timeframe
scaling, risk-manager guardrails, position sizing, strategy signals on
synthetic data, and the backtester loop.

## What this scaffold does **not** do

- Forecast prices with deep learning. The strategy is a deliberately simple
  EMA + ATR trend filter so you can see exactly why each trade fires.
- Trade news / event windows differently. Add an FTMO news filter yourself
  before going live.
- Persist state across restarts. The risk manager rebuilds its day-start
  equity from the OANDA account each launch.
- Hedge. Each instrument trades one direction at a time.

These are obvious next iterations once the basic loop is working on a demo
account.
