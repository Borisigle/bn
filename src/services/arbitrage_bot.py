from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Protocol

from src.core.bot_config import BotConfig
from src.core.polymarket_client import PolymarketClientService
from src.strategies.arbitrage_pure.detector import ArbitragePureDetector
from src.strategies.arbitrage_pure.executor import ArbitragePureExecutor
from src.strategies.arbitrage_pure.types import TradeLog


class Logger(Protocol):
    def log_debug(self, message: str) -> None: ...
    def log_error(self, message: str) -> None: ...
    def log_info(self, message: str) -> None: ...
    def log_warning(self, message: str) -> None: ...


@dataclass
class ArbitrageBotService:
    poly_client: PolymarketClientService
    config: BotConfig
    logger: Logger

    detector: ArbitragePureDetector = field(init=False)
    executor: ArbitragePureExecutor = field(init=False)

    _running: bool = field(default=False, init=False)
    _balance: float = field(default=0.0, init=False)
    _trade_logs: List[TradeLog] = field(default_factory=list, init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False, repr=False)
    _cycle_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.detector = ArbitragePureDetector(
            self.poly_client,
            min_profit_threshold=self.config.min_profit_threshold,
            min_market_volume=self.config.min_market_volume,
            logger=self.logger,
        )
        self.executor = ArbitragePureExecutor(self.poly_client, self.logger)
        self._balance = float(self.config.starting_capital)

    async def start(self) -> None:
        self._running = True
        self._stop_event = asyncio.Event()

        await self.poly_client.initialize()

        self.logger.log_info(
            f"Starting pure arbitrage bot | balance=${self._balance:.2f} paper={self.config.paper_trading} mock={self.config.mock_mode}"
        )

        while self._running:
            started = time.monotonic()
            try:
                await self.scan_loop()
            except Exception as e:
                self.logger.log_error(f"scan_loop error: {e}")
            elapsed = time.monotonic() - started

            sleep_for = max(0.0, (self.config.scan_interval_ms / 1000.0) - elapsed)

            # Allow stop() to interrupt the sleep.
            try:
                if self._stop_event is not None:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
                else:
                    await asyncio.sleep(sleep_for)
            except asyncio.TimeoutError:
                pass

    async def scan_loop(self) -> None:
        if not self._running:
            return

        cycle_start_time = time.monotonic()
        cycle_number = self._cycle_count
        self._cycle_count += 1

        cycle_header = (
            f"\n{'=' * 60}\n"
            f"📍 CYCLE #{cycle_number} | Time: {datetime.now().isoformat()}\n"
            f"{'=' * 60}"
        )
        self.logger.log_info(cycle_header)

        try:
            min_amount = self._position_amount()
            if self._balance < min_amount or min_amount <= 0:
                self.logger.log_info(
                    f"Balance too low to trade | balance=${self._balance:.2f} position_size=${self.config.position_size:.2f}"
                )
                return

            scan_limit = self.config.market_scan_limit
            
            # SCAN
            scan_start_time = time.monotonic()
            self.logger.log_info(f"🔍 Scanning {scan_limit} markets...")
            
            opportunities = await self.detector.scan_markets(limit=scan_limit)
            scan_time = time.monotonic() - scan_start_time
            
            self.logger.log_info(
                f"✅ Scan complete | Time: {scan_time:.2f}s | Opportunities: {len(opportunities)}"
            )

            if len(opportunities) == 0:
                self.logger.log_info("⏸️ No opportunities found. Next scan in 30 seconds...")
                await asyncio.sleep(30)
                return
            
            # EXECUTE
            executed_count = 0
            total_profit = 0.0
            
            for i, arb in enumerate(opportunities):
                if not self._running:
                    break

                amount = self._position_amount()
                if amount <= 0:
                    break

                self.logger.log_info(
                    f"\n⚡ [{i + 1}/{len(opportunities)}] "
                    f"Executing: {arb.question or arb.market} ({(arb.profit * 100):.2f}% profit)"
                )

                op_started = time.monotonic()
                result = await self.executor.execute(arb, amount=amount)
                op_time = time.monotonic() - op_started

                if result.success:
                    executed_count += 1
                    total_profit += result.profit
                    self._update_balance(result.profit)
                    self._trade_logs.append(
                        TradeLog(
                            timestamp=datetime.now(),
                            market=result.market,
                            type=result.type,
                            profit=result.profit,
                            balance=self._balance,
                            operation_time=op_time,
                        )
                    )
                    self.logger.log_info(
                        f"✅ COMPLETED | "
                        f"Profit: +${result.profit:.2f} | "
                        f"Time: {op_time:.2f}s | "
                        f"Balance: ${self._balance:.2f}"
                    )
                else:
                    self.logger.log_error(f"❌ FAILED | Error: {result.error}")

                # Delay entre ejecuciones
                await asyncio.sleep(self.config.execution_delay_ms / 1000.0)
            
            # CYCLE SUMMARY
            cycle_time = time.monotonic() - cycle_start_time
            
            summary = (
                f"\n📊 CYCLE #{cycle_number} SUMMARY\n"
                f"├─ Total time: {cycle_time:.2f}s\n"
                f"├─ Scan time: {scan_time:.2f}s\n"
                f"├─ Opportunities found: {len(opportunities)}\n"
                f"├─ Operations executed: {executed_count}\n"
                f"├─ Total profit: +${total_profit:.2f}\n"
                f"├─ Balance: ${self._balance:.2f}\n"
                f"└─ Next cycle in 30 seconds...\n"
                f"{'=' * 60}"
            )
            self.logger.log_info(summary)

        except Exception as error:
            self.logger.log_error(f"Cycle error: {error}")
        
        # Wait for next cycle
        await asyncio.sleep(30)

    def stop(self) -> None:
        self._running = False
        if self._stop_event is not None:
            self._stop_event.set()
        self.logger.log_info("Stopping bot...")

    def get_balance(self) -> float:
        return float(self._balance)

    def get_trade_logs(self) -> List[TradeLog]:
        return list(self._trade_logs)

    def _position_amount(self) -> float:
        if self._balance <= 0:
            return 0.0

        size = float(self.config.position_size)
        # Allow POSITION_SIZE<=1 to mean fraction of capital.
        if 0 < size <= 1:
            size = self._balance * size

        return min(size, self._balance)

    def _update_balance(self, profit: float) -> None:
        self._balance += float(profit)
