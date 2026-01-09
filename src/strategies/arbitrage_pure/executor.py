from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

from src.core.polymarket_client import OrderConfig, PolymarketClientService
from src.strategies.arbitrage_pure.types import Arbitrage, ExecutionResult


class Logger(Protocol):
    def log_error(self, message: str) -> None: ...

    def log_info(self, message: str) -> None: ...


@dataclass
class ArbitragePureExecutor:
    poly_client: PolymarketClientService
    logger: Logger

    async def execute(self, arb: Arbitrage, amount: float = 10.0) -> ExecutionResult:
        started = time.monotonic()

        try:
            if amount <= 0:
                raise ValueError("amount must be > 0")

            sum_price = arb.yes_price + arb.no_price
            if sum_price <= 0:
                raise ValueError("invalid prices")

            if arb.type == "long":
                shares = amount / sum_price

                yes_cfg = OrderConfig(
                    market=arb.market,
                    condition_id=arb.condition_id,
                    outcome="YES",
                    side="BUY",
                    shares=shares,
                    expected_price=arb.yes_price,
                )
                no_cfg = OrderConfig(
                    market=arb.market,
                    condition_id=arb.condition_id,
                    outcome="NO",
                    side="BUY",
                    shares=shares,
                    expected_price=arb.no_price,
                )

                yes_order, no_order = await asyncio.gather(
                    self.poly_client.create_market_order(yes_cfg),
                    self.poly_client.create_market_order(no_cfg),
                )

                invested = amount
                received = float(
                    yes_order.shares * yes_order.filled_price
                    + no_order.shares * no_order.filled_price
                )

                # Merge/redeem complete sets (paper-mode: min(shares) * $1).
                redeemed = await self.poly_client.redeem(yes_order.shares, no_order.shares, arb.condition_id)
                received = redeemed

                profit = received - invested

            else:
                # Short arb is modeled as: lock $1 collateral per set, split to YES/NO shares,
                # then sell both. Profit comes from selling prices exceeding $1.
                shares = amount

                yes_cfg = OrderConfig(
                    market=arb.market,
                    condition_id=arb.condition_id,
                    outcome="YES",
                    side="SELL",
                    shares=shares,
                    expected_price=arb.yes_price,
                )
                no_cfg = OrderConfig(
                    market=arb.market,
                    condition_id=arb.condition_id,
                    outcome="NO",
                    side="SELL",
                    shares=shares,
                    expected_price=arb.no_price,
                )

                yes_order, no_order = await asyncio.gather(
                    self.poly_client.create_market_order(yes_cfg),
                    self.poly_client.create_market_order(no_cfg),
                )

                invested = amount
                received = float(
                    yes_order.shares * yes_order.filled_price
                    + no_order.shares * no_order.filled_price
                )

                # No merge step in short-arb; keep API symmetry.
                _ = await self.poly_client.redeem(0.0, 0.0, arb.condition_id)
                profit = received - invested

            elapsed = time.monotonic() - started
            self.logger.log_info(
                f"EXECUTED arb type={arb.type} market={arb.market} profit=${profit:.4f} time={elapsed:.2f}s"
            )

            return ExecutionResult(
                market=arb.market,
                type=arb.type,
                invested=invested,
                received=received,
                profit=profit,
                success=True,
            )

        except Exception as e:
            elapsed = time.monotonic() - started
            self.logger.log_error(f"Arbitrage execution failed: {e} ({elapsed:.2f}s)")
            return ExecutionResult(
                market=arb.market,
                type=arb.type,
                invested=amount,
                received=0.0,
                profit=0.0,
                success=False,
                error=str(e),
            )
