"""Minimal OANDA v20 REST client.

Covers what the bot needs: account summary, candles, pricing, market orders
with stop-loss / take-profit, open positions, and trade close.

OANDA v20 API docs: https://developer.oanda.com/rest-live-v20/introduction/
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd
import requests

from .config import OandaConfig

log = logging.getLogger(__name__)


class OandaError(RuntimeError):
    pass


@dataclass
class Candle:
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: int


class OandaClient:
    def __init__(self, cfg: OandaConfig, session: Optional[requests.Session] = None):
        self.cfg = cfg
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {cfg.api_token}",
                "Content-Type": "application/json",
                "Accept-Datetime-Format": "RFC3339",
            }
        )

    # ---- low-level ---------------------------------------------------------

    def _url(self, path: str, *, stream: bool = False) -> str:
        host = self.cfg.stream_host if stream else self.cfg.rest_host
        return f"{host}/v3{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        url = self._url(path)
        resp = self.session.request(method, url, timeout=30, **kwargs)
        if not resp.ok:
            raise OandaError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.text else {}

    # ---- account ----------------------------------------------------------

    def account_summary(self) -> Dict[str, Any]:
        data = self._request("GET", f"/accounts/{self.cfg.account_id}/summary")
        return data["account"]

    def instrument_details(self, instrument: str) -> Dict[str, Any]:
        data = self._request(
            "GET",
            f"/accounts/{self.cfg.account_id}/instruments",
            params={"instruments": instrument},
        )
        instruments = data.get("instruments", [])
        if not instruments:
            raise OandaError(f"Instrument not available on this account: {instrument}")
        return instruments[0]

    # ---- market data -------------------------------------------------------

    def candles(
        self,
        instrument: str,
        granularity: str = "H1",
        count: int = 500,
        price: str = "M",
    ) -> pd.DataFrame:
        """Fetch historical candles as a DataFrame indexed by time."""
        params = {"granularity": granularity, "count": count, "price": price}
        data = self._request(
            "GET", f"/instruments/{instrument}/candles", params=params
        )
        rows = []
        for c in data.get("candles", []):
            if not c.get("complete", False):
                continue
            mid = c["mid"]
            rows.append(
                {
                    "time": pd.to_datetime(c["time"], utc=True),
                    "open": float(mid["o"]),
                    "high": float(mid["h"]),
                    "low": float(mid["l"]),
                    "close": float(mid["c"]),
                    "volume": int(c["volume"]),
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.set_index("time").sort_index()
        return df

    def current_price(self, instrument: str) -> Dict[str, float]:
        data = self._request(
            "GET",
            f"/accounts/{self.cfg.account_id}/pricing",
            params={"instruments": instrument},
        )
        prices = data.get("prices", [])
        if not prices:
            raise OandaError(f"No price returned for {instrument}")
        p = prices[0]
        bid = float(p["bids"][0]["price"])
        ask = float(p["asks"][0]["price"])
        return {"bid": bid, "ask": ask, "mid": (bid + ask) / 2}

    def stream_prices(self, instruments: List[str]) -> Iterator[Dict[str, Any]]:
        url = self._url(
            f"/accounts/{self.cfg.account_id}/pricing/stream", stream=True
        )
        params = {"instruments": ",".join(instruments)}
        with self.session.get(url, params=params, stream=True, timeout=None) as resp:
            if not resp.ok:
                raise OandaError(f"stream {resp.status_code}: {resp.text}")
            for line in resp.iter_lines():
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("type") == "PRICE":
                    yield msg

    # ---- orders / positions -----------------------------------------------

    def market_order(
        self,
        instrument: str,
        units: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        client_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Place a market order. `units` is signed: positive=long, negative=short."""
        order: Dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(int(units)),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }
        if stop_loss is not None:
            order["stopLossOnFill"] = {"price": f"{stop_loss:.5f}"}
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.5f}"}
        if client_tag:
            order["clientExtensions"] = {"tag": client_tag, "id": client_tag[:64]}

        return self._request(
            "POST",
            f"/accounts/{self.cfg.account_id}/orders",
            data=json.dumps({"order": order}),
        )

    def open_positions(self) -> List[Dict[str, Any]]:
        data = self._request(
            "GET", f"/accounts/{self.cfg.account_id}/openPositions"
        )
        return data.get("positions", [])

    def close_position(self, instrument: str, side: str = "ALL") -> Dict[str, Any]:
        """Close long/short/all units of a position. side: LONG, SHORT, or ALL."""
        body: Dict[str, Any] = {}
        if side in ("LONG", "ALL"):
            body["longUnits"] = "ALL"
        if side in ("SHORT", "ALL"):
            body["shortUnits"] = "ALL"
        return self._request(
            "PUT",
            f"/accounts/{self.cfg.account_id}/positions/{instrument}/close",
            data=json.dumps(body),
        )
