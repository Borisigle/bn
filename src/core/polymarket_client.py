from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import requests

from src.core.rate_limiter import AsyncRateLimiter
from src.strategies.arbitrage_pure.types import BinaryMarket


OrderSide = Literal["BUY", "SELL"]
Outcome = Literal["YES", "NO"]


@dataclass(frozen=True)
class OrderConfig:
    market: str
    condition_id: str
    outcome: Outcome
    side: OrderSide
    shares: float
    expected_price: float


@dataclass(frozen=True)
class Order:
    order_id: str
    market: str
    outcome: Outcome
    side: OrderSide
    filled_price: float
    shares: float


@dataclass
class PolymarketClientService:
    api_key: str = ""
    api_secret: str = ""
    host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    paper_trading: bool = True
    mock_mode: bool = True

    gamma_rate_limiter: AsyncRateLimiter = field(default_factory=lambda: AsyncRateLimiter(max_calls=5, period_seconds=1.0))

    _client: Any = field(default=None, init=False, repr=False)

    async def initialize(self) -> None:
        if self.mock_mode or self.paper_trading:
            return

        if not self.api_key or not self.api_secret:
            raise ValueError("POLYMARKET_API_KEY and POLYMARKET_API_SECRET are required for real trading")

        try:
            from py_clob_client.client import ClobClient

            self._client = ClobClient(host=self.host, api_key=self.api_key, api_secret=self.api_secret)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Polymarket CLOB client: {e}") from e

    async def get_top_markets(self, limit: int = 1000) -> List[BinaryMarket]:
        if self.mock_mode:
            return _mock_markets(limit)

        markets: List[BinaryMarket] = []
        offset = 0
        page_size = min(500, max(1, limit))

        while len(markets) < limit:
            params = {"limit": page_size, "offset": offset, "active": "true"}
            payload = await self._gamma_get_json("/markets", params=params)
            items = payload.get("markets") if isinstance(payload, dict) else payload
            if not isinstance(items, list) or not items:
                break

            for m in items:
                bm = _parse_binary_market(m)
                if bm is not None:
                    markets.append(bm)
                    if len(markets) >= limit:
                        break

            offset += len(items)
            if len(items) < page_size:
                break

        return markets[:limit]

    async def create_market_order(self, cfg: OrderConfig) -> Order:
        if cfg.shares <= 0:
            raise ValueError("shares must be > 0")
        if not (0.0 < cfg.expected_price < 1.0):
            raise ValueError("expected_price must be in (0, 1)")

        if self.paper_trading or self.mock_mode:
            return Order(
                order_id=f"paper-{uuid.uuid4().hex}",
                market=cfg.market,
                outcome=cfg.outcome,
                side=cfg.side,
                filled_price=cfg.expected_price,
                shares=cfg.shares,
            )

        if self._client is None:
            raise RuntimeError("Polymarket client not initialized")

        raise NotImplementedError("Real trading is not enabled in this repository by default.")

    async def redeem(self, yes_shares: float, no_shares: float, condition_id: str) -> float:
        if self.paper_trading or self.mock_mode:
            if yes_shares <= 0 or no_shares <= 0:
                return 0.0
            return float(min(yes_shares, no_shares))

        if self._client is None:
            raise RuntimeError("Polymarket client not initialized")

        raise NotImplementedError("On-chain redeem/merge is not enabled in this repository by default.")

    async def _gamma_get_json(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        await self.gamma_rate_limiter.acquire()

        def _do() -> Any:
            resp = requests.get(f"{self.gamma_host}{path}", params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()

        return await asyncio.to_thread(_do)


def _parse_binary_market(m: Any) -> Optional[BinaryMarket]:
    if not isinstance(m, dict):
        return None

    active = bool(m.get("active", True))
    if not active:
        return None

    question = str(m.get("question") or m.get("title") or "")
    condition_id = str(m.get("conditionId") or m.get("condition_id") or m.get("id") or "")
    market_id = str(m.get("id") or condition_id)
    if not condition_id or not market_id:
        return None

    volume = m.get("volume")
    if volume is None:
        volume = m.get("volumeUsd") or m.get("volume_usd") or m.get("volumeUSD") or 0.0
    try:
        volume_f = float(volume)
    except Exception:
        volume_f = 0.0

    prices = _extract_yes_no_prices(m)
    if prices is None:
        return None

    yes_bid, yes_ask, no_bid, no_ask = prices
    if min(yes_bid, yes_ask, no_bid, no_ask) <= 0:
        return None

    return BinaryMarket(
        market=market_id,
        condition_id=condition_id,
        question=question,
        volume=volume_f,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        active=True,
    )


def _extract_yes_no_prices(market: dict[str, Any]) -> Optional[tuple[float, float, float, float]]:
    outcomes = market.get("outcomes") or market.get("tokens") or market.get("clobTokens")
    if not isinstance(outcomes, list):
        return None

    yes: Optional[dict[str, Any]] = None
    no: Optional[dict[str, Any]] = None

    for o in outcomes:
        if not isinstance(o, dict):
            continue

        label = str(o.get("outcome") or o.get("label") or o.get("name") or "").strip().upper()
        if label in {"YES", "Y", "TRUE"} or "YES" in label:
            yes = o
        elif label in {"NO", "N", "FALSE"} or "NO" in label:
            no = o

    if yes is None or no is None:
        return None

    def _bid_ask(x: dict[str, Any]) -> Optional[tuple[float, float]]:
        bid = x.get("bestBid") or x.get("best_bid") or x.get("bid")
        ask = x.get("bestAsk") or x.get("best_ask") or x.get("ask")
        if bid is None or ask is None:
            return None
        try:
            return float(bid), float(ask)
        except Exception:
            return None

    y = _bid_ask(yes)
    n = _bid_ask(no)
    if y is None or n is None:
        return None

    return y[0], y[1], n[0], n[1]


def _mock_markets(limit: int) -> List[BinaryMarket]:
    rng = random.Random(1337)
    out: List[BinaryMarket] = []

    for i in range(max(limit, 1200)):
        question = f"Mock Market #{i}"
        market_id = f"mock-{i}"
        condition_id = f"cond-{i}"
        volume = float(rng.randint(1_000, 100_000))

        # Create small mispricings around 1.0 to simulate opportunities.
        mid_yes = rng.uniform(0.05, 0.95)
        mid_no = 1.0 - mid_yes

        # Add an inefficiency of up to ~3%.
        ineff = rng.uniform(-0.03, 0.03)
        mid_no = min(0.999, max(0.001, mid_no + ineff))

        # Create a simple bid/ask spread.
        spread = rng.uniform(0.001, 0.01)

        yes_bid = max(0.001, min(0.999, mid_yes - spread))
        yes_ask = max(0.001, min(0.999, mid_yes + spread))
        no_bid = max(0.001, min(0.999, mid_no - spread))
        no_ask = max(0.001, min(0.999, mid_no + spread))

        out.append(
            BinaryMarket(
                market=market_id,
                condition_id=condition_id,
                question=question,
                volume=volume,
                yes_bid=yes_bid,
                yes_ask=yes_ask,
                no_bid=no_bid,
                no_ask=no_ask,
                active=True,
            )
        )

    return out[:limit]
