from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from src.core.polymarket_client import PolymarketClientService
from src.strategies.arbitrage_pure.types import Arbitrage, BinaryMarket


@dataclass
class ArbitragePureDetector:
    poly_client: PolymarketClientService
    min_profit_threshold: float = 0.005
    min_market_volume: float = 10_000.0

    long_sum_threshold: float = 0.99
    short_sum_threshold: float = 1.01

    async def scan_markets(self, limit: int = 1000) -> List[Arbitrage]:
        markets = await self.poly_client.get_top_markets(limit=limit)

        opportunities: List[Arbitrage] = []
        for m in markets:
            arb = self.analyze_market(m)
            if arb is None:
                continue
            if arb.profit < self.min_profit_threshold:
                continue
            opportunities.append(arb)

        opportunities.sort(key=lambda a: a.profit, reverse=True)
        return opportunities

    def analyze_market(self, market: BinaryMarket) -> Optional[Arbitrage]:
        if not market.active:
            return None
        if market.volume < self.min_market_volume:
            return None

        if min(market.yes_bid, market.yes_ask, market.no_bid, market.no_ask) <= 0:
            return None

        # Basic sanity checks.
        if market.yes_ask < market.yes_bid or market.no_ask < market.no_bid:
            return None

        long_sum = market.yes_ask + market.no_ask
        short_sum = market.yes_bid + market.no_bid

        best: Optional[Arbitrage] = None

        if long_sum < self.long_sum_threshold:
            profit = max(0.0, 1.0 - long_sum)
            best = Arbitrage(
                type="long",
                market=market.market,
                condition_id=market.condition_id,
                profit=profit,
                yes_price=market.yes_ask,
                no_price=market.no_ask,
                timestamp=time.time(),
                question=market.question,
            )

        if short_sum > self.short_sum_threshold:
            profit = max(0.0, short_sum - 1.0)
            cand = Arbitrage(
                type="short",
                market=market.market,
                condition_id=market.condition_id,
                profit=profit,
                yes_price=market.yes_bid,
                no_price=market.no_bid,
                timestamp=time.time(),
                question=market.question,
            )
            if best is None or cand.profit > best.profit:
                best = cand

        return best
