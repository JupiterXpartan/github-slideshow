"""Strategy handler — pluggable signal generator.

Two implementations are provided:

  * `TechnicalStrategy` — pure heuristic; works offline and is the safe default.
    Combines a small EMA on the mid-price with order-book imbalance to estimate
    "fair" probability vs market price.

  * `ClaudeStrategy` — wraps the technical signal and asks Claude for a
    sanity check + sentiment overlay. Falls back to the technical signal
    when the LLM is unavailable.

A `Strategy` returns a `Signal` describing direction, model probability, and
confidence — the rest of the bot turns that into an actual order.

Plugging in your own model
--------------------------
Implement `Strategy.evaluate(snapshot) -> Signal | None`. Anything that can
read an order book and produce a probability estimate works (xgboost, a
fine-tuned model, an external HTTP service, etc).
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal, Protocol

from .clob import OrderBook

log = logging.getLogger(__name__)

Side = Literal["BUY", "SELL"]


@dataclass
class MarketSnapshot:
    """All the per-market context a strategy needs to make a decision."""

    condition_id: str
    question: str                    # human-readable "Will X happen?"
    yes_token_id: str
    no_token_id: str
    yes_book: OrderBook
    no_book: OrderBook
    last_yes_price: float | None
    recent_yes_mids: list[float]     # short trailing window (oldest -> newest)


@dataclass
class Signal:
    side: Side                       # BUY YES, or SELL YES (== BUY NO)
    token_id: str                    # token to trade (yes or no)
    market_price: float              # current ask if buying, bid if selling
    true_probability: float          # the model's estimate of P(YES)
    confidence: float                # 0..1, used to dampen Kelly
    rationale: str = ""


class Strategy(Protocol):
    def evaluate(self, snap: MarketSnapshot) -> Signal | None: ...


# --------------------------------------------------------------------------- TA

@dataclass
class TechnicalStrategy:
    """Order-book imbalance + short EMA on the mid-price."""

    ema_alpha: float = 0.3
    imbalance_weight: float = 0.5    # how strongly imbalance pulls fair value
    min_book_depth_usd: float = 50.0 # ignore markets with paper-thin books

    def evaluate(self, snap: MarketSnapshot) -> Signal | None:
        book = snap.yes_book
        if book.best_bid is None or book.best_ask is None:
            return None

        bid_depth = sum(l.price * l.size for l in book.bids[:5])
        ask_depth = sum(l.price * l.size for l in book.asks[:5])
        if bid_depth + ask_depth < self.min_book_depth_usd:
            return None

        mid = book.mid or 0.5
        ema = self._ema(snap.recent_yes_mids + [mid])

        # Imbalance in (-1, +1): positive => more bid pressure => fair px > mid.
        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)

        # Pull EMA toward the imbalance-implied fair value, clamped to (0,1).
        fair = ema + self.imbalance_weight * imbalance * (1 - ema) * ema
        fair = max(0.01, min(0.99, fair))

        # Confidence rises with depth and falls with spread.
        spread_bps = book.spread_bps or 1_000
        confidence = max(0.0, min(1.0, 1 - spread_bps / 1_000)) * min(
            1.0, (bid_depth + ask_depth) / 500.0
        )

        if fair > book.best_ask:
            return Signal(
                side="BUY",
                token_id=snap.yes_token_id,
                market_price=book.best_ask,
                true_probability=fair,
                confidence=confidence,
                rationale=f"TA: fair={fair:.3f} > ask={book.best_ask:.3f}, imb={imbalance:+.2f}",
            )
        if fair < book.best_bid:
            # Selling YES is equivalent to buying NO at (1 - bid).
            no_price = 1 - book.best_bid
            return Signal(
                side="SELL",
                token_id=snap.no_token_id,
                market_price=no_price,
                true_probability=1 - fair,
                confidence=confidence,
                rationale=f"TA: fair={fair:.3f} < bid={book.best_bid:.3f}, imb={imbalance:+.2f}",
            )
        return None

    def _ema(self, series: list[float]) -> float:
        if not series:
            return 0.5
        ema = series[0]
        for x in series[1:]:
            ema = self.ema_alpha * x + (1 - self.ema_alpha) * ema
        return ema


# ------------------------------------------------------------------------- LLM

_LLM_SYSTEM_PROMPT = """You are a quantitative analyst evaluating Polymarket prediction-market mispricings.

You will receive:
  * the market question,
  * the current YES order book (bids/asks with size),
  * a recent series of mid-prices,
  * a baseline technical signal with a candidate fair-value probability.

Your job: decide whether to TRADE or PASS. If trading, provide an estimate of
the true probability of YES and a confidence in [0, 1].

Be a sceptic. Reject signals when:
  * the spread is wide and depth is thin,
  * the question hinges on near-term events you can't price without fresh news,
  * the technical edge is small (< 4 percentage points),
  * the question wording is ambiguous.

Respond ONLY as compact JSON:
  {"action":"TRADE"|"PASS","side":"BUY"|"SELL","true_probability":float,
   "confidence":float,"rationale":"short explanation"}

`side` is required only when action == TRADE. BUY means buy YES; SELL means
buy NO (equivalently, sell YES)."""


@dataclass
class ClaudeStrategy:
    """Wraps a TA signal with an LLM sanity-check.

    The TA signal is the source of truth for *what to consider*; Claude's
    job is to veto bad ideas and (occasionally) refine the probability.
    """

    api_key: str
    model: str = "claude-opus-4-7"
    fallback: Strategy = field(default_factory=TechnicalStrategy)

    def __post_init__(self) -> None:
        # Lazy import so the bot still runs without `anthropic` installed.
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is required for ClaudeStrategy. "
                "Install with `pip install anthropic`."
            ) from exc

    def evaluate(self, snap: MarketSnapshot) -> Signal | None:
        base = self.fallback.evaluate(snap)
        if base is None:
            return None

        try:
            verdict = self._ask_claude(snap, base)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM strategy failed (%s); falling back to TA", exc)
            return base

        if verdict.get("action") != "TRADE":
            log.info("LLM passed on %s: %s", snap.condition_id[:10], verdict.get("rationale", ""))
            return None

        side: Side = verdict.get("side", base.side)
        if side == "BUY":
            token_id = snap.yes_token_id
            market_price = snap.yes_book.best_ask or base.market_price
        else:
            token_id = snap.no_token_id
            market_price = (1 - (snap.yes_book.best_bid or 1 - base.market_price))

        return Signal(
            side=side,
            token_id=token_id,
            market_price=market_price,
            true_probability=float(verdict.get("true_probability", base.true_probability)),
            confidence=float(verdict.get("confidence", base.confidence)),
            rationale=f"LLM: {verdict.get('rationale', '')[:140]}",
        )

    def _ask_claude(self, snap: MarketSnapshot, base: Signal) -> dict:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        payload = {
            "question": snap.question,
            "yes_book": {
                "bids": [(l.price, l.size) for l in snap.yes_book.bids[:5]],
                "asks": [(l.price, l.size) for l in snap.yes_book.asks[:5]],
            },
            "recent_yes_mids": [round(p, 4) for p in snap.recent_yes_mids[-20:]],
            "ta_signal": {
                "side": base.side,
                "fair_probability": round(base.true_probability, 4),
                "market_price": round(base.market_price, 4),
                "confidence": round(base.confidence, 3),
                "rationale": base.rationale,
            },
            "now_unix": int(time.time()),
        }

        # The system prompt is stable and large enough to benefit from caching.
        msg = client.messages.create(
            model=self.model,
            max_tokens=512,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": _LLM_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": "Evaluate this opportunity:\n" + json.dumps(payload),
                }
            ],
        )

        text = next(
            (block.text for block in msg.content if getattr(block, "type", None) == "text"),
            "",
        ).strip()

        # Strip optional code fences and parse.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        return json.loads(text)


def build_strategy(
    *,
    anthropic_api_key: str,
    llm_model: str,
) -> Strategy:
    """Pick the LLM-backed strategy when a key is configured, else pure TA."""
    if anthropic_api_key:
        log.info("using Claude-backed strategy (model=%s)", llm_model)
        return ClaudeStrategy(api_key=anthropic_api_key, model=llm_model)
    log.info("ANTHROPIC_API_KEY not set; using technical-only strategy")
    return TechnicalStrategy()


# Rolling mid-price history shared by the bot loop.
class MidHistory:
    def __init__(self, max_len: int = 60) -> None:
        self._buf: dict[str, deque[float]] = {}
        self._max_len = max_len

    def push(self, condition_id: str, mid: float) -> None:
        buf = self._buf.setdefault(condition_id, deque(maxlen=self._max_len))
        buf.append(mid)

    def get(self, condition_id: str) -> list[float]:
        return list(self._buf.get(condition_id, ()))
