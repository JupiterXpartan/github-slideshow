"""Polymarket CLOB WebSocket subscriber with auto-reconnect.

Streams `book` and `last_trade_price` events for a watchlist of token_ids and
fans them out to a callback. The connection is supervised — on any failure the
loop sleeps with exponential backoff (capped at 60s) and reconnects forever.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

log = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class MarketStream:
    def __init__(self, ws_url: str, asset_ids: list[str], handler: EventHandler):
        if not asset_ids:
            raise ValueError("MarketStream requires at least one asset_id")
        self.ws_url = ws_url
        self.asset_ids = asset_ids
        self.handler = handler
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._run_once()
                backoff = 1.0  # reset after a clean session
            except asyncio.CancelledError:
                raise
            except (ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
                log.warning("WS dropped (%s); reconnecting in %.1fs", exc, backoff)
            except Exception as exc:  # noqa: BLE001
                log.exception("WS unexpected error: %s; reconnecting in %.1fs", exc, backoff)

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60.0)

    async def _run_once(self) -> None:
        log.info("connecting to %s for %d assets", self.ws_url, len(self.asset_ids))
        async with websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_queue=1024,
        ) as ws:
            sub = {"type": "market", "assets_ids": self.asset_ids}
            await ws.send(json.dumps(sub))
            log.info("subscribed to %d markets", len(self.asset_ids))

            async for raw in ws:
                if self._stop.is_set():
                    return
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    log.debug("non-json frame ignored: %r", raw[:120])
                    continue

                # Polymarket sends arrays of events.
                events = payload if isinstance(payload, list) else [payload]
                for event in events:
                    try:
                        await self.handler(event)
                    except Exception as exc:  # noqa: BLE001
                        # Never let a handler bug kill the stream.
                        log.exception("handler crashed on event %s: %s", event, exc)
