"""Thin wrapper around the official `py-clob-client`.

Goals:
  * Hide credential bootstrap (derive API keys from the private key on first run).
  * Centralise order construction so size/price rounding happens in one place.
  * Surface only the calls the bot actually needs.

Polymarket binary outcome conventions used here:
  * Each market has a `condition_id` and two `token_id`s (YES and NO).
  * Prices are floats in (0, 1) representing the implied probability.
  * Sizes are denominated in *outcome shares*, each redeemable for $1 if it wins.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.constants import POLYGON
from py_clob_client.order_builder.constants import BUY, SELL

from .config import Config

log = logging.getLogger(__name__)

# Polymarket CLOB tick size — prices snap to $0.01.
PRICE_TICK = 0.01
# Minimum order size enforced by the CLOB.
MIN_ORDER_SHARES = 5.0


@dataclass
class BookLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    token_id: str
    bids: list[BookLevel]
    asks: list[BookLevel]

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread_bps(self) -> float | None:
        if self.best_bid is None or self.best_ask is None or self.mid == 0:
            return None
        return (self.best_ask - self.best_bid) / self.mid * 10_000


def _round_price(price: float) -> float:
    """Snap to the CLOB tick and clamp inside (0, 1)."""
    snapped = round(price / PRICE_TICK) * PRICE_TICK
    return max(PRICE_TICK, min(1 - PRICE_TICK, round(snapped, 2)))


def _round_shares(shares: float) -> float:
    """Round down to 2 decimals so we never overspend our budget."""
    return math.floor(shares * 100) / 100


class PolyClob:
    """High-level CLOB facade used by the rest of the bot."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._client = self._build_client(cfg)

    # ------------------------------------------------------------------ setup

    @staticmethod
    def _build_client(cfg: Config) -> ClobClient:
        creds: ApiCreds | None = None
        if cfg.clob_api_key and cfg.clob_api_secret and cfg.clob_api_passphrase:
            creds = ApiCreds(
                api_key=cfg.clob_api_key,
                api_secret=cfg.clob_api_secret,
                api_passphrase=cfg.clob_api_passphrase,
            )

        client = ClobClient(
            host=cfg.clob_host,
            key=cfg.pk,
            chain_id=cfg.chain_id or POLYGON,
            creds=creds,
            signature_type=cfg.signature_type,
            funder=cfg.poly_funder or None,
        )

        if creds is None:
            # First run: derive L2 credentials and cache them in memory.
            derived = client.create_or_derive_api_creds()
            client.set_api_creds(derived)
            log.warning(
                "Derived CLOB API creds. Cache them in your .env to skip this:\n"
                "  CLOB_API_KEY=%s\n  CLOB_API_SECRET=%s\n  CLOB_API_PASSPHRASE=%s",
                derived.api_key,
                derived.api_secret,
                derived.api_passphrase,
            )
        return client

    # ---------------------------------------------------------------- market

    def get_market(self, condition_id: str) -> dict[str, Any]:
        return self._client.get_market(condition_id)

    def get_order_book(self, token_id: str) -> OrderBook:
        raw = self._client.get_order_book(token_id)
        bids = [BookLevel(float(b.price), float(b.size)) for b in (raw.bids or [])]
        asks = [BookLevel(float(a.price), float(a.size)) for a in (raw.asks or [])]
        # Polymarket returns bids ascending and asks ascending; normalise so
        # bids[0] is the best bid and asks[0] is the best ask.
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        return OrderBook(token_id=token_id, bids=bids, asks=asks)

    def get_last_trade_price(self, token_id: str) -> float | None:
        try:
            resp = self._client.get_last_trade_price(token_id=token_id)
            return float(resp["price"]) if resp and "price" in resp else None
        except Exception as exc:  # noqa: BLE001
            log.debug("last trade price lookup failed: %s", exc)
            return None

    # ----------------------------------------------------------------- trade

    def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        usd_size: float,
    ) -> dict[str, Any] | None:
        """Submit a GTC limit order sized in USD.

        Returns the CLOB response dict on success, or None if the request was
        skipped (e.g. dust order, invalid side).
        """
        if side not in (BUY, SELL):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")

        price = _round_price(price)
        if price <= 0 or price >= 1:
            log.info("skipping order: price %.4f outside tradable range", price)
            return None

        shares = _round_shares(usd_size / price)
        if shares < MIN_ORDER_SHARES:
            log.info(
                "skipping order: %.2f shares below CLOB minimum %.2f (usd=%.2f, px=%.2f)",
                shares,
                MIN_ORDER_SHARES,
                usd_size,
                price,
            )
            return None

        args = OrderArgs(price=price, size=shares, side=side, token_id=token_id)
        signed = self._client.create_order(args)
        resp = self._client.post_order(signed, OrderType.GTC)
        log.info(
            "submitted %s %.2f @ %.2f token=%s -> %s",
            side, shares, price, token_id[:10], resp,
        )
        return resp

    def cancel(self, order_id: str) -> Any:
        return self._client.cancel(order_id=order_id)

    def cancel_all(self) -> Any:
        return self._client.cancel_all()

    def open_orders(self) -> list[dict[str, Any]]:
        return self._client.get_orders() or []

    def positions_usdc(self) -> float:
        """Return current free USDC balance available to the trading account."""
        try:
            from py_clob_client.clob_types import AssetType, BalanceAllowanceParams

            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            bal = self._client.get_balance_allowance(params)
            return float(bal.get("balance", 0)) / 1e6  # USDC has 6 decimals
        except Exception as exc:  # noqa: BLE001
            log.warning("failed to read USDC balance: %s", exc)
            return 0.0
