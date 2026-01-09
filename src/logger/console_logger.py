from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _usd(x: float) -> str:
    return f"${x:,.2f}"


@dataclass
class ConsoleLogger:
    log_dir: str = "logs"
    log_file: str = "bot.log"

    console: Console = field(default_factory=lambda: Console(encoding="utf-8"), init=False)
    file_logger: logging.Logger = field(default_factory=lambda: logging.getLogger("bot"), init=False)

    def __post_init__(self) -> None:
        os.makedirs(self.log_dir, exist_ok=True)

        self.file_logger.setLevel(logging.INFO)
        self.file_logger.propagate = False
        self.file_logger.handlers.clear()

        # File Handler - add encoding='utf-8'
        fh = logging.FileHandler(
            os.path.join(self.log_dir, self.log_file),
            encoding='utf-8'
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        self.file_logger.addHandler(fh)

        self._print_header()

    def _print_header(self) -> None:
        title = Text("POLYMARKET 15MIN BOT - PAPER TRADING", style="bold cyan")
        self.console.print(Panel(title, expand=False, border_style="cyan"))

    def _log(self, message: str, *, style: Optional[str] = None) -> None:
        prefix = f"[{_ts()}] "
        if style:
            self.console.print(prefix + message, style=style)
        else:
            self.console.print(prefix + message)
        self.file_logger.info(message)

    def log_price_update(self, btc_price: float, pct_change: float) -> None:
        self._log(f"📊 BTC Price: {_usd(btc_price)} ({pct_change:+.2f}% last 5min)", style="bold")

    def log_market(self, market_id: str, seconds_to_forced_close: int, status: str) -> None:
        mm, ss = divmod(max(0, int(seconds_to_forced_close)), 60)
        self._log(
            f"🎯 Market: {market_id} | Status: {status} | Time to forced close: {mm}:{ss:02d}",
            style="cyan",
        )

    def log_capital(self, capital: float, open_positions: int) -> None:
        self._log(f"💰 Capital: {_usd(capital)} | Open Positions: {open_positions}", style="green")

    def log_opportunity_detected(self, spread: float, side: str, expected_prob: float, ask: float) -> None:
        self._log(
            f"🔍 Opportunity detected! side={side} spread={spread*100:.2f}% expected={expected_prob:.3f} ask={ask:.3f}",
            style="yellow",
        )

    def log_trade_opened(self, position_id: int, side: str, entry_price: float, size_usd: float, sl: float, tp: float) -> None:
        self._log(
            f"✅ TRADE OPENED | #{position_id} {side} @ {entry_price:.3f} size={_usd(size_usd)} SL={sl:.3f} TP={tp:.3f}",
            style="bold green",
        )

    def log_position_update(self, position_id: int, side: str, current_price: float, pnl: float) -> None:
        style = "green" if pnl >= 0 else "red"
        self._log(
            f"📈 Position #{position_id} {side} | price={current_price:.3f} | uPnL={_usd(pnl)}",
            style=style,
        )

    def log_trade_closed(self, position_id: int, reason: str, pnl: float, capital: float) -> None:
        style = "bold green" if pnl >= 0 else "bold red"
        self._log(
            f"🏁 TRADE CLOSED | #{position_id} reason={reason} pnl={_usd(pnl)} capital={_usd(capital)}",
            style=style,
        )

    def log_forced_close(self) -> None:
        self._log("⏰ FORCE CLOSE window reached - closing all positions", style="bold red")

    def log_info(self, message: str) -> None:
        self._log(message)

    def log_error(self, message: str) -> None:
        self._log(f"❌ {message}", style="bold red")

    def log_summary(self, total_trades: int, wins: int, losses: int, total_pnl: float, capital: float) -> None:
        self._log(
            f"📌 SUMMARY | trades={total_trades} wins={wins} losses={losses} pnl={_usd(total_pnl)} capital={_usd(capital)}",
            style="bold cyan",
        )
