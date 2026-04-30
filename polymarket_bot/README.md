# Polymarket Trading Bot

A 24/7, risk-managed trading bot for [Polymarket](https://polymarket.com) on
Polygon, built on the official `py-clob-client` SDK and a pluggable strategy
module that supports either pure technical analysis or a Claude-powered
sentiment overlay.

> ⚠️ **Real money disclaimer.** This bot signs and sends real on-chain orders
> as soon as you provide a funded private key. Prediction markets are highly
> uncertain — you can and will lose money. Start with the smallest deposit
> the bot can trade ($5–$10 per ticket, ~$50–$100 total) and only use a
> wallet whose loss you can absorb.

---

## What it does

* Connects to the Polymarket CLOB REST API for orders + REST market data.
* Subscribes to the CLOB WebSocket for live order-book updates with **automatic
  reconnect and exponential backoff** — no manual intervention if the stream drops.
* Runs a **technical strategy** (EMA + order-book imbalance) by default. If you
  add an Anthropic API key, a **Claude-powered overlay** sanity-checks each
  signal and can veto bad ideas.
* Sizes every trade with **fractional Kelly** (default ¼-Kelly) using the
  estimated edge, the market price, and the bot's current bankroll.
* Enforces **stop-loss**, **take-profit**, **max-drawdown circuit breaker**,
  per-trade USD limits, and a max number of concurrent positions.
* Persists state to disk (`bot_state.json`) so a restart resumes cleanly.

---

## Architecture

```
        ┌──────────────────────────────────────┐
        │  bot.py — main asyncio loop          │
        │   ├─ MarketStream (WebSocket, auto-  │
        │   │   reconnect with backoff)        │
        │   └─ Decision loop (every N seconds) │
        │        ├─ mark-to-market positions   │
        │        ├─ stop-loss / take-profit    │
        │        ├─ drawdown circuit breaker   │
        │        ├─ Strategy.evaluate()        │
        │        ├─ RiskManager.kelly_size_usd │
        │        └─ PolyClob.place_limit_order │
        └──────────────────────────────────────┘
                  │                │
        ┌─────────▼──────┐  ┌──────▼─────────┐
        │ Strategy       │  │ py-clob-client │
        │  ├─ Technical  │  │  (signs +      │
        │  └─ Claude     │  │   submits via  │
        └────────────────┘  │   Polygon)     │
                            └────────────────┘
```

---

## Step-by-step setup (non-technical guide)

### 1. Get the prerequisites

You need three things:

1. **Python 3.10 or newer.** Check with `python3 --version`. Install from
   [python.org](https://www.python.org/downloads/) if missing.
2. **A Polygon wallet funded with USDC.e** (the "bridged" USDC Polymarket uses).
   The simplest path: install [MetaMask](https://metamask.io), create a
   *fresh wallet just for the bot*, and bridge USDC.e to Polygon via
   [Polymarket's deposit page](https://polymarket.com).
3. **A small amount of MATIC** (~$1 worth) in the same wallet to pay Polygon
   gas. Many bridges drop a tiny amount automatically.

### 2. Download the bot

```bash
git clone https://github.com/jupiterxpartan/github-slideshow.git
cd github-slideshow/polymarket_bot
```

### 3. Install the Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure your `.env`

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill in **at minimum**:

| Variable | What to set |
|---|---|
| `PK` | Your Polygon wallet's private key (starts with `0x`, 66 chars total). Export from MetaMask → Account Details → Show Private Key. |
| `WATCHLIST_CONDITION_IDS` | Comma-separated `condition_id`s of the markets the bot is allowed to trade. Open a market on polymarket.com and copy the ID from the URL or the API. |
| `BANKROLL_USDC` | The maximum USDC you let the bot manage. Start small (e.g. `50`). |

Optional:

* `ANTHROPIC_API_KEY` to enable the Claude-powered strategy overlay.
* `POLYGON_RPC_URL` if you want to use Alchemy/Infura instead of the default
  public RPC (more reliable under load).
* `KELLY_FRACTION`, `MIN_EDGE`, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`,
  `MAX_DRAWDOWN_PCT` — risk knobs documented inline in `.env.example`.

### 5. Run the bot

```bash
python run.py
```

You'll see logs like:

```
loaded market 0x1234abcd…: Will Bitcoin close above $100k by…
starting bot: 3 markets, bankroll=$50.00, kelly=0.25, max_dd=25%
connecting to wss://ws-subscriptions-clob.polymarket.com/ws/market for 6 assets
subscribed to 6 markets
```

Stop with `Ctrl+C` — the bot drains gracefully and saves state.

### 6. Run it 24/7 (optional)

The simplest way is `tmux` or `screen`:

```bash
tmux new -s polybot
python run.py
# detach: Ctrl+B then D
```

For production use a process supervisor like `systemd` or `pm2`. Sample
`systemd` unit:

```ini
[Unit]
Description=Polymarket trading bot
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/USER/github-slideshow/polymarket_bot
ExecStart=/home/USER/github-slideshow/polymarket_bot/.venv/bin/python run.py
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/USER/github-slideshow/polymarket_bot/.env

[Install]
WantedBy=multi-user.target
```

---

## Risk management knobs (`.env`)

| Key | Meaning |
|---|---|
| `BANKROLL_USDC` | Hard cap on how much the bot ever risks, regardless of wallet balance. |
| `MIN_TRADE_USDC` / `MAX_TRADE_USDC` | Per-ticket size limits in USD. Defaults: $5 / $25. |
| `KELLY_FRACTION` | Fraction of full Kelly to use. ¼ (0.25) is conservative; ½ is aggressive. |
| `MIN_EDGE` | Minimum (true probability − market price) required before placing a trade. Default 4%. |
| `STOP_LOSS_PCT` | Exit a position once its mark-to-market loss exceeds this percent of cost basis. |
| `TAKE_PROFIT_PCT` | Exit once gains exceed this percent of cost basis. |
| `MAX_DRAWDOWN_PCT` | If equity drops this far below the initial bankroll, the bot flattens everything and halts. |
| `MAX_OPEN_POSITIONS` | Cap on simultaneously open positions. |
| `MAX_SLIPPAGE_BPS` | Tolerated slippage between the strategy's quoted price and the actual fill. |

The Kelly formula used:

```
edge = p_true - p_market           # for BUY (long YES)
f*   = edge / (1 - p_market)
stake = clamp(f* * KELLY_FRACTION * bankroll, MIN_TRADE_USDC, MAX_TRADE_USDC)
```

For the SELL side (buying NO), the mirror formula is used. The result is
further dampened by the strategy's reported `confidence` value.

---

## Plugging in your own strategy

`polybot/strategy.py` defines a tiny `Strategy` Protocol:

```python
class Strategy(Protocol):
    def evaluate(self, snap: MarketSnapshot) -> Signal | None: ...
```

Subclass or write your own and return a `Signal(side, token_id,
market_price, true_probability, confidence, rationale)`. Then wire it up in
`polybot/bot.py` by replacing `build_strategy(...)` with your factory.

The bundled strategies are:

* **`TechnicalStrategy`** — EMA on the YES mid-price + 5-deep order-book
  imbalance. No external dependencies.
* **`ClaudeStrategy`** — wraps the technical signal and asks Claude to
  TRADE/PASS, optionally refining the probability. Uses adaptive thinking +
  prompt caching on the system prompt for low-latency repeat calls.

---

## Project layout

```
polymarket_bot/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py                  # entry point (`python run.py`)
└── polybot/
    ├── __init__.py
    ├── bot.py              # main asyncio loop, glues everything together
    ├── clob.py             # py-clob-client wrapper (orders, books, balance)
    ├── config.py           # typed .env loader with validation
    ├── risk.py             # Kelly, stop-loss/take-profit, drawdown breaker
    ├── state.py            # JSON-on-disk persistence
    ├── strategy.py         # Technical + Claude strategies, Signal/Snapshot
    └── ws.py               # CLOB WebSocket subscriber with auto-reconnect
```

---

## FAQ

**Why does the bot need my private key?**
Polymarket settles on Polygon. Every CLOB order is an EIP-712 signature
produced from your key. The key never leaves your machine — it sits in the
local `.env` file, which is gitignored.

**Why USDC.e and not USDC?**
Polymarket's CLOB collateral is the bridged USDC variant on Polygon
(USDC.e). Native Polygon USDC is a different token contract.

**What happens if my Polygon RPC dies?**
The bot retries. Persistent failures bubble up as logged warnings — the
bot keeps trying. For production, point `POLYGON_RPC_URL` at a paid
provider (Alchemy, Infura, QuickNode, Ankr) for better uptime.

**What if the WebSocket disconnects?**
`MarketStream.run_forever()` reconnects with exponential backoff (1s → 2s →
… → 60s cap). The decision loop continues using the last cached prices and
falls back to REST `get_order_book` when forming new entries.

**Can I dry-run without sending real orders?**
The cleanest dry-run is to set `MIN_TRADE_USDC` and `MAX_TRADE_USDC` below
the CLOB minimum (~5 shares). The bot will log its intended trades but
the size guard in `clob.py` will skip submission. A proper paper-trading
mode is on the roadmap.
