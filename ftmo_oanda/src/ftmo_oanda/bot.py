"""Live trading loop.

Polls OANDA for fresh candles each bar, evaluates the strategy, and submits
bracketed market orders if the FTMO risk manager approves. Defaults to
``DRY_RUN=true`` so first runs print intended trades without sending them.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .config import AppConfig
from .oanda_client import OandaClient
from .risk import FtmoRiskManager
from .strategies.ema_atr_trend import EmaAtrTrendStrategy
from .timeframe import TimeframeProfile, for_timeframe, GRANULARITY_MINUTES

log = logging.getLogger(__name__)


@dataclass
class BotState:
    last_signal_bar: Dict[str, str]  # instrument -> ISO timestamp string
    cooldown_remaining: Dict[str, int]


class Bot:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.profile: TimeframeProfile = for_timeframe(cfg.trading.timeframe)
        self.client = OandaClient(cfg.oanda)
        summary = self.client.account_summary()
        starting = float(summary.get("balance", cfg.ftmo.initial_balance))
        self.risk = FtmoRiskManager(cfg.ftmo, self.profile, starting_equity=starting)
        self.strategy = EmaAtrTrendStrategy(self.profile)
        self.state = BotState(last_signal_bar={}, cooldown_remaining={})

    # ------------------------------------------------------------------

    def _sleep_until_next_bar(self) -> None:
        """Coarse poll cadence: half the bar duration, capped to sane bounds."""
        minutes = GRANULARITY_MINUTES.get(self.profile.granularity, 60)
        sleep_s = max(15.0, min(60 * 60.0, minutes * 30.0))
        log.debug("Sleeping %.1fs before next poll", sleep_s)
        time.sleep(sleep_s)

    def _refresh_equity(self) -> None:
        try:
            summary = self.client.account_summary()
            equity = float(summary.get("NAV", summary.get("balance", 0)))
            self.risk.update_equity(equity)
            self.risk.state.open_positions = int(summary.get("openPositionCount", 0))
        except Exception as exc:  # network blips shouldn't crash the loop
            log.warning("Failed to refresh equity: %s", exc)

    def _evaluate_instrument(self, instrument: str) -> None:
        candles = self.client.candles(
            instrument,
            granularity=self.profile.granularity,
            count=self.profile.candles_history,
        )
        if candles.empty:
            log.warning("No candles for %s", instrument)
            return

        last_bar_time = candles.index[-1].isoformat()
        if self.state.last_signal_bar.get(instrument) == last_bar_time:
            return  # already evaluated this closed bar

        cd = self.state.cooldown_remaining.get(instrument, 0)
        if cd > 0:
            self.state.cooldown_remaining[instrument] = cd - 1
            self.state.last_signal_bar[instrument] = last_bar_time
            return

        sig = self.strategy.signal(candles)
        self.state.last_signal_bar[instrument] = last_bar_time
        if sig is None:
            return

        ok, reason = self.risk.can_open_new_trade()
        if not ok:
            log.info("Skip %s signal: %s", instrument, reason)
            return

        # Pull instrument metadata for accurate leverage caps.
        try:
            details = self.client.instrument_details(instrument)
            margin_rate = float(details.get("marginRate", 0.05))
            instr_leverage_cap = (1.0 / margin_rate) if margin_rate > 0 else None
        except Exception:
            instr_leverage_cap = None

        units = self.risk.position_size(
            entry_price=sig.entry,
            stop_price=sig.stop,
            pip_value_per_unit=1.0,  # quote-currency P&L per 1.0 price move
            instrument_leverage_cap=instr_leverage_cap,
        )
        if units == 0:
            log.info("Skip %s: position size rounds to zero", instrument)
            return

        log.info(
            "%s %s entry=%.5f stop=%.5f target=%.5f units=%d (tf=%s, risk=%.2f%%)",
            instrument,
            sig.side.upper(),
            sig.entry,
            sig.stop,
            sig.target,
            units,
            self.profile.granularity,
            self.profile.risk_per_trade_pct,
        )

        if self.cfg.trading.dry_run:
            log.info("[DRY_RUN] not sending order")
        else:
            try:
                self.client.market_order(
                    instrument=instrument,
                    units=units,
                    stop_loss=sig.stop,
                    take_profit=sig.target,
                    client_tag=f"ftmo-bot-{self.profile.granularity}",
                )
                self.risk.state.open_positions += 1
                self.state.cooldown_remaining[instrument] = self.profile.cooldown_bars
            except Exception as exc:
                log.error("Order failed for %s: %s", instrument, exc)

    # ------------------------------------------------------------------

    def run_forever(self) -> None:
        log.info(
            "Bot starting: env=%s tf=%s instruments=%s dry_run=%s",
            self.cfg.oanda.environment,
            self.profile.granularity,
            self.cfg.trading.instruments,
            self.cfg.trading.dry_run,
        )
        while True:
            self._refresh_equity()
            ok, reason = self.risk.can_open_new_trade()
            if not ok:
                log.info("Trading halted: %s", reason)
                # Continue running for monitoring even when halted.
            for instrument in self.cfg.trading.instruments:
                try:
                    self._evaluate_instrument(instrument)
                except Exception as exc:
                    log.exception("Error evaluating %s: %s", instrument, exc)
            self._sleep_until_next_bar()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = AppConfig.from_env()
    Bot(cfg).run_forever()


if __name__ == "__main__":
    main()
