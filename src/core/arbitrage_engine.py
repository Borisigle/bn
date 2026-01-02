from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Opportunity:
    side: str  # "UP" | "DOWN"
    spread: float
    expected_prob: float
    entry_price: float


@dataclass
class ArbitrageEngine:
    spread_threshold: float = 0.05
    price_move_threshold: float = 2.0

    # How aggressively to map % move -> probability edge.
    max_prob_delta: float = 0.30

    def _expected_probability(self, pct_change: float) -> tuple[str, float]:
        side = "UP" if pct_change >= 0 else "DOWN"
        normalized = min(1.0, abs(pct_change) / max(self.price_move_threshold, 1e-9))
        prob = 0.5 + (normalized * self.max_prob_delta)
        prob = min(0.99, max(0.01, prob))
        return side, prob

    def detect_opportunity(
        self,
        btc_price: float,
        market_prices: dict[str, dict[str, float]],
        btc_pct_change: Optional[float] = None,
    ) -> Optional[Opportunity]:
        """Return an Opportunity when Binance movement implies an edge vs Polymarket ask.

        market_prices is expected to be shaped like:
        {
          "UP": {"bid": 0.50, "ask": 0.52},
          "DOWN": {"bid": 0.48, "ask": 0.50}
        }
        """

        if btc_pct_change is None:
            return None

        if abs(btc_pct_change) < self.price_move_threshold:
            return None

        side, expected_prob = self._expected_probability(btc_pct_change)
        side_prices = market_prices.get(side)
        if not side_prices:
            return None

        ask = float(side_prices.get("ask", 1.0))
        spread = expected_prob - ask
        if spread <= 0:
            return None

        return Opportunity(side=side, spread=spread, expected_prob=expected_prob, entry_price=ask)

    def should_enter(self, opportunity: Opportunity, capital_available: float) -> bool:
        return opportunity.spread >= self.spread_threshold and capital_available > 0

    def as_dict(self, opportunity: Opportunity) -> dict[str, Any]:
        return {
            "side": opportunity.side,
            "spread": opportunity.spread,
            "expected_prob": opportunity.expected_prob,
            "entry_price": opportunity.entry_price,
        }
