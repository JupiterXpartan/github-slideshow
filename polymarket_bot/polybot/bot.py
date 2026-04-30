"""Main 24/7 trading bot loop.

Responsibilities:
  1. Pull market metadata for every condition_id in the watchlist.
  2. Subscribe to live order-book updates over WebSocket.
  3. On every poll tick:
       a. Mark every open position to the latest mid-price.
       b. Trigger stop-loss / take-profit exits as needed.
       c. Check the max-drawdown circuit breaker.
       d. Ask the strategy for new entry signals.
       e. Size any entries with fractional Kelly and submit GTC orders.
  4. Persist state on every change so a restart resumes cleanly.

The bot uses two cooperating asyncio tasks:
  * `MarketStream.run_forever()`  — keeps mid-prices fresh from the WS feed.
  * `_decision_loop()`            — periodic polling, sizing, and execution.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from py_clob_client.order_builder.constants import BUY, SELL
from rich.logging import RichHandler

from .clob import OrderBook, PolyClob
from .config import Config
from .risk import RiskManager
from .state import load_state, save_state
from .strategy import MarketSnapshot, MidHistory, Strategy, build_strategy
from .ws import MarketStream

log = logging.getLogger("polybot")


class Bot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.clob = PolyClob(cfg)
        self.state = load_state(cfg.state_file, cfg.bankroll_usdc)
        self.risk = RiskManager(
            self.state,
            kelly_fraction=cfg.kelly_fraction,
            min_trade_usdc=cfg.min_trade_usdc,
            max_trade_usdc=cfg.max_trade_usdc,
            min_edge=cfg.min_edge,
            stop_loss_pct=cfg.stop_loss_pct,
            take_profit_pct=cfg.take_profit_pct,
            max_drawdown_pct=cfg.max_drawdown_pct,
            max_open_positions=cfg.max_open_positions,
            max_slippage_bps=cfg.max_slippage_bps,
        )
        self.strategy: Strategy = build_strategy(
            anthropic_api_key=cfg.anthropic_api_key,
            llm_model=cfg.llm_model,
        )
        self.mid_history = MidHistory()
        self.markets: dict[str, dict[str, Any]] = {}     # condition_id -> market dict
        self.token_to_condition: dict[str, str] = {}
        self.token_to_side: dict[str, str] = {}          # token_id -> "yes"/"no"
        self.latest_mid: dict[str, float] = {}           # token_id -> mid price
        self._stop = asyncio.Event()
        self._stream: MarketStream | None = None

    # ---------------------------------------------------------------- bootstrap

    def _bootstrap_markets(self) -> list[str]:
        """Fetch metadata for every condition_id and return the list of YES+NO token_ids to subscribe."""
        if not self.cfg.watchlist:
            raise RuntimeError(
                "WATCHLIST_CONDITION_IDS is empty — give the bot at least one market to trade."
            )

        asset_ids: list[str] = []
        for cid in self.cfg.watchlist:
            market = self.clob.get_market(cid)
            tokens = market.get("tokens", [])
            if len(tokens) != 2:
                log.warning("skipping %s: expected 2 outcome tokens, got %d", cid, len(tokens))
                continue

            yes = next((t for t in tokens if str(t.get("outcome", "")).lower() == "yes"), tokens[0])
            no = next((t for t in tokens if t is not yes), tokens[1])
            self.markets[cid] = {
                "question": market.get("question", ""),
                "yes_token_id": yes["token_id"],
                "no_token_id": no["token_id"],
            }
            for tid, side in ((yes["token_id"], "yes"), (no["token_id"], "no")):
                self.token_to_condition[tid] = cid
                self.token_to_side[tid] = side
                asset_ids.append(tid)

            log.info("loaded market %s: %s", cid[:10], market.get("question", "")[:80])

        if not asset_ids:
            raise RuntimeError("no valid markets in watchlist")
        return asset_ids

    # --------------------------------------------------------------- WS handler

    async def _on_ws_event(self, event: dict[str, Any]) -> None:
        """Update cached mid-prices from CLOB book events."""
        event_type = event.get("event_type") or event.get("type")
        asset_id = event.get("asset_id") or event.get("market")
        if not asset_id:
            return

        if event_type == "book":
            bids = event.get("bids", []) or event.get("buys", [])
            asks = event.get("asks", []) or event.get("sells", [])
            best_bid = max((float(b["price"]) for b in bids), default=None)
            best_ask = min((float(a["price"]) for a in asks), default=None)
            if best_bid is not None and best_ask is not None:
                mid = (best_bid + best_ask) / 2
                self.latest_mid[asset_id] = mid
                cid = self.token_to_condition.get(asset_id)
                if cid and self.token_to_side.get(asset_id) == "yes":
                    self.mid_history.push(cid, mid)
        elif event_type == "last_trade_price":
            try:
                self.latest_mid[asset_id] = float(event["price"])
            except (KeyError, TypeError, ValueError):
                pass

    # ----------------------------------------------------------- decision loop

    async def _decision_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception as exc:  # noqa: BLE001
                log.exception("decision loop error: %s", exc)

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.cfg.poll_interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        if self.state.halted:
            log.warning("bot halted: %s", self.state.halt_reason)
            return

        # ----- mark to market ----- #
        marks = {tok: self.latest_mid.get(tok, pos.entry_price)
                 for tok, pos in self.state.positions.items()}

        if self.risk.check_drawdown(marks):
            await self._panic_flatten()
            save_state(self.cfg.state_file, self.state)
            return

        # ----- protective exits ----- #
        for tok, pos in list(self.state.positions.items()):
            mark = marks.get(tok, pos.entry_price)
            should_exit, reason = self.risk.should_exit(pos, mark)
            if should_exit:
                log.info("exiting %s: %s", tok[:10], reason)
                self._submit_exit(tok, pos)

        # ----- entry signals ----- #
        for cid, market in self.markets.items():
            if not self.risk.can_open_new():
                break
            yes_tok = market["yes_token_id"]
            no_tok = market["no_token_id"]
            if yes_tok in self.state.positions or no_tok in self.state.positions:
                continue  # already in this market — don't double-up

            yes_book = await asyncio.to_thread(self.clob.get_order_book, yes_tok)
            no_book = await asyncio.to_thread(self.clob.get_order_book, no_tok)
            snap = MarketSnapshot(
                condition_id=cid,
                question=market["question"],
                yes_token_id=yes_tok,
                no_token_id=no_tok,
                yes_book=yes_book,
                no_book=no_book,
                last_yes_price=self.latest_mid.get(yes_tok),
                recent_yes_mids=self.mid_history.get(cid),
            )
            sig = await asyncio.to_thread(self.strategy.evaluate, snap)
            if sig is None:
                continue

            stake = self.risk.kelly_size_usd(
                side=sig.side,
                market_price=sig.market_price,
                true_prob=sig.true_probability,
                bankroll=self._effective_bankroll(),
            )
            stake *= max(0.1, sig.confidence)  # dampen by signal confidence
            if stake < self.cfg.min_trade_usdc:
                log.debug("skipping %s: stake $%.2f below min $%.2f",
                          cid[:10], stake, self.cfg.min_trade_usdc)
                continue

            await self._submit_entry(sig, stake)

        save_state(self.cfg.state_file, self.state)

    def _effective_bankroll(self) -> float:
        return max(0.0, self.state.initial_bankroll + self.state.realized_pnl)

    async def _submit_entry(self, sig, stake_usd: float) -> None:
        clob_side = BUY  # we always BUY the chosen outcome token
        log.info(
            "ENTRY %s stake=$%.2f px=%.3f p_true=%.3f conf=%.2f | %s",
            sig.side, stake_usd, sig.market_price,
            sig.true_probability, sig.confidence, sig.rationale,
        )
        resp = await asyncio.to_thread(
            self.clob.place_limit_order,
            sig.token_id, clob_side, sig.market_price, stake_usd,
        )
        if not resp:
            return
        # Treat the limit price as the entry until we get a real fill from the WS.
        shares = round(stake_usd / sig.market_price, 2)
        self.risk.open_position(sig.token_id, sig.side, sig.market_price, shares)

    def _submit_exit(self, token_id: str, pos) -> None:
        # Selling our outcome token = posting a SELL at the current best bid.
        side_token_book = self.clob.get_order_book(token_id)
        target_px = side_token_book.best_bid or pos.entry_price
        resp = self.clob.place_limit_order(token_id, SELL, target_px, pos.shares * target_px)
        if resp:
            self.risk.close_position(token_id, target_px)

    async def _panic_flatten(self) -> None:
        log.error("flattening all positions due to circuit breaker")
        for tok, pos in list(self.state.positions.items()):
            try:
                self._submit_exit(tok, pos)
            except Exception as exc:  # noqa: BLE001
                log.exception("panic exit failed for %s: %s", tok[:10], exc)
        try:
            self.clob.cancel_all()
        except Exception as exc:  # noqa: BLE001
            log.warning("cancel_all failed: %s", exc)

    # -------------------------------------------------------------------- run

    async def run(self) -> None:
        asset_ids = self._bootstrap_markets()
        self._stream = MarketStream(self.cfg.clob_ws_url, asset_ids, self._on_ws_event)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                pass  # Windows

        log.info(
            "starting bot: %d markets, bankroll=$%.2f, kelly=%.2f, max_dd=%.0f%%",
            len(self.markets),
            self.cfg.bankroll_usdc,
            self.cfg.kelly_fraction,
            self.cfg.max_drawdown_pct * 100,
        )

        await asyncio.gather(
            self._stream.run_forever(),
            self._decision_loop(),
        )

    def _handle_shutdown(self) -> None:
        log.warning("shutdown requested; draining…")
        self._stop.set()
        if self._stream:
            self._stream.stop()


def main() -> None:
    cfg = Config.load()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_path=False)],
    )
    bot = Bot(cfg)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
