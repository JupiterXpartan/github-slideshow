"""Terminal dashboard - read-only view of account, FTMO usage, and positions."""
from __future__ import annotations

import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .config import AppConfig
from .oanda_client import OandaClient
from .timeframe import for_timeframe


def _make_view(cfg: AppConfig, client: OandaClient) -> Panel:
    profile = for_timeframe(cfg.trading.timeframe)
    summary = client.account_summary()
    positions = client.open_positions()

    nav = float(summary.get("NAV", summary.get("balance", 0)))
    bal = float(summary.get("balance", nav))
    initial = cfg.ftmo.initial_balance
    daily_loss_floor = bal * (cfg.ftmo.max_daily_loss_pct / 100)
    total_loss_floor = initial * (1 - cfg.ftmo.max_total_loss_pct / 100)
    target = initial * (1 + cfg.ftmo.profit_target_pct / 100)

    acct = Table(title="Account", show_header=False, expand=True)
    acct.add_column(style="cyan")
    acct.add_column(justify="right")
    acct.add_row("Environment", cfg.oanda.environment)
    acct.add_row("Account ID", cfg.oanda.account_id)
    acct.add_row("Balance", f"{bal:,.2f}")
    acct.add_row("NAV (equity)", f"{nav:,.2f}")
    acct.add_row("Open positions", str(summary.get("openPositionCount", 0)))
    acct.add_row("Margin used", f"{float(summary.get('marginUsed', 0)):,.2f}")

    ftmo = Table(title="FTMO guardrails", show_header=False, expand=True)
    ftmo.add_column(style="cyan")
    ftmo.add_column(justify="right")
    ftmo.add_row("Profit target", f"{target:,.2f}")
    ftmo.add_row("Total-loss floor", f"{total_loss_floor:,.2f}")
    ftmo.add_row("Daily-loss budget", f"{daily_loss_floor:,.2f}")
    ftmo.add_row("Distance to target", f"{nav - target:+,.2f}")
    ftmo.add_row("Distance to total floor", f"{nav - total_loss_floor:+,.2f}")

    tf = Table(title=f"Timeframe profile ({profile.granularity})", show_header=False, expand=True)
    tf.add_column(style="cyan")
    tf.add_column(justify="right")
    tf.add_row("Risk per trade", f"{profile.risk_per_trade_pct:.2f}%")
    tf.add_row("Max effective leverage", f"{profile.max_effective_leverage:.0f}x")
    tf.add_row("ATR stop / target", f"{profile.atr_stop_mult} / {profile.atr_target_mult}")
    tf.add_row("Reward:risk", f"{profile.reward_risk:.2f}")
    tf.add_row("EMA fast / slow", f"{profile.ema_fast} / {profile.ema_slow}")
    tf.add_row("Max concurrent", str(profile.max_concurrent_positions))

    pos = Table(title="Open positions", expand=True)
    pos.add_column("Instrument")
    pos.add_column("Long units", justify="right")
    pos.add_column("Short units", justify="right")
    pos.add_column("Unrealized P&L", justify="right")
    for p in positions:
        pos.add_row(
            p["instrument"],
            p["long"]["units"],
            p["short"]["units"],
            f"{float(p.get('unrealizedPL', 0)):+,.2f}",
        )
    if not positions:
        pos.add_row("(none)", "", "", "")

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(acct, ftmo)
    grid.add_row(tf, pos)
    return Panel(grid, title="FTMO / OANDA bot dashboard", border_style="green")


def main() -> None:
    cfg = AppConfig.from_env()
    client = OandaClient(cfg.oanda)
    console = Console()
    with Live(_make_view(cfg, client), console=console, refresh_per_second=1) as live:
        while True:
            time.sleep(5)
            try:
                live.update(_make_view(cfg, client))
            except Exception as exc:  # transient errors shouldn't kill the view
                console.print(f"[red]refresh error: {exc}[/red]")


if __name__ == "__main__":
    main()
