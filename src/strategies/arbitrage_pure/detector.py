from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from src.core.polymarket_client import PolymarketClientService
from src.strategies.arbitrage_pure.types import Arbitrage, BinaryMarket


class LoggerProtocol:
    def log_debug(self, message: str) -> None: ...
    def log_info(self, message: str) -> None: ...
    def log_error(self, message: str) -> None: ...
    def log_warning(self, message: str) -> None: ...


@dataclass
class ArbitragePureDetector:
    poly_client: PolymarketClientService
    min_profit_threshold: float = 0.005
    min_market_volume: float = 10_000.0

    long_sum_threshold: float = 0.99
    short_sum_threshold: float = 1.01

    logger: Optional[LoggerProtocol] = None

    async def scan_markets(self, limit: int = 1000) -> List[Arbitrage]:
        start_time = time.time()
        
        if self.logger:
            self.logger.log_info("🔍 [SCAN START] Beginning market scan...")
        
        try:
            # ===== FETCH MARKETS =====
            fetch_start_time = time.time()
            
            if self.logger:
                self.logger.log_debug("⏱️ [FETCH] Starting market fetch...")
            
            markets = await self.poly_client.get_top_markets(limit=limit)
            
            fetch_time = time.time() - fetch_start_time
            fetch_time_ms = fetch_time * 1000
            
            if self.logger:
                self.logger.log_debug(f"⏱️ [FETCH] Completed in {fetch_time:.2f}s ({fetch_time_ms:.0f}ms)")
                self.logger.log_debug(f"📊 [FETCH] Got {len(markets)} markets")
                if fetch_time > 0:
                    self.logger.log_debug(f"📈 [FETCH] Speed: {(len(markets) / fetch_time):.1f} markets/sec")
            
            if len(markets) == 0:
                if self.logger:
                    self.logger.log_warning("⚠️ [FETCH] No markets returned from API")
                return []
            
            # ===== ANALYZE MARKETS =====
            analyze_start_time = time.time()
            
            if self.logger:
                self.logger.log_debug(f"⏱️ [ANALYZE] Starting analysis of {len(markets)} markets...")
            
            opportunities: List[Arbitrage] = []
            analyzed = 0
            errors = 0
            
            for market in markets:
                analyzed += 1
                
                # Log every 100 markets
                if analyzed % 100 == 0 and self.logger:
                    elapsed = time.time() - analyze_start_time
                    speed = analyzed / elapsed if elapsed > 0 else 0
                    self.logger.log_debug(
                        f"📍 [ANALYZE] Progress: {analyzed}/{len(markets)} "
                        f"({(analyzed / len(markets) * 100):.1f}%) - "
                        f"{speed:.1f} markets/sec"
                    )
                
                try:
                    arb = self.analyze_market(market)
                    if arb is None:
                        continue
                    if arb.profit < self.min_profit_threshold:
                        continue
                    opportunities.append(arb)
                except Exception as error:
                    errors += 1
                    if errors <= 5 and self.logger:  # Log only first 5 errors
                        self.logger.log_warning(f"⚠️ [ANALYZE] Error analyzing market {getattr(market, 'market', 'unknown')}: {error}")
            
            opportunities.sort(key=lambda a: a.profit, reverse=True)
            
            analyze_time = time.time() - analyze_start_time
            analyze_time_ms = analyze_time * 1000
            
            if self.logger:
                self.logger.log_debug(f"⏱️ [ANALYZE] Completed in {analyze_time:.2f}s ({analyze_time_ms:.0f}ms)")
                self.logger.log_debug(f"📊 [ANALYZE] Errors: {errors}/{len(markets)}")
                if analyze_time > 0:
                    self.logger.log_debug(f"📈 [ANALYZE] Speed: {(len(markets) / analyze_time):.1f} markets/sec")
            
            # ===== SUMMARY =====
            total_time = time.time() - start_time
            total_time_ms = total_time * 1000
            
            if self.logger:
                self.logger.log_info(
                    f"🎯 [SCAN COMPLETE] Found {len(opportunities)} opportunities "
                    f"in {total_time:.2f}s ({total_time_ms:.0f}ms) "
                    f"(Fetch: {fetch_time:.2f}s, Analyze: {analyze_time:.2f}s)"
                )
            
            # ===== PERFORMANCE CHECK =====
            if total_time > 35:  # > 35 seconds
                if self.logger:
                    self.logger.log_warning(
                        f"⚠️ [PERFORMANCE] Scan took {total_time:.2f}s "
                        f"(Target: 30s). Performance issue detected!"
                    )
            else:
                if self.logger:
                    self.logger.log_info("✅ [PERFORMANCE] Scan within target time")
            
            return opportunities
            
        except Exception as error:
            if self.logger:
                self.logger.log_error(f"❌ [SCAN ERROR] Failed to scan markets: {error}")
            return []

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
