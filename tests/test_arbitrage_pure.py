import asyncio
from dataclasses import dataclass
from typing import List

from src.core.polymarket_client import Order, OrderConfig
from src.strategies.arbitrage_pure.detector import ArbitragePureDetector
from src.strategies.arbitrage_pure.executor import ArbitragePureExecutor
from src.strategies.arbitrage_pure.types import Arbitrage, BinaryMarket


@dataclass
class StubLogger:
    infos: List[str]
    errors: List[str]

    def log_info(self, message: str) -> None:
        self.infos.append(message)

    def log_error(self, message: str) -> None:
        self.errors.append(message)


class StubPolymarketClient:
    def __init__(self, markets: List[BinaryMarket]):
        self._markets = markets
        self.orders: List[OrderConfig] = []

    async def initialize(self) -> None:
        return

    async def get_top_markets(self, limit: int = 1000) -> List[BinaryMarket]:
        return self._markets[:limit]

    async def create_market_order(self, cfg: OrderConfig) -> Order:
        self.orders.append(cfg)
        return Order(
            order_id="paper",
            market=cfg.market,
            outcome=cfg.outcome,
            side=cfg.side,
            filled_price=cfg.expected_price,
            shares=cfg.shares,
        )

    async def redeem(self, yes_shares: float, no_shares: float, condition_id: str) -> float:
        if yes_shares <= 0 or no_shares <= 0:
            return 0.0
        return float(min(yes_shares, no_shares))


def test_detector_finds_long_and_short_and_sorts_by_profit() -> None:
    markets = [
        BinaryMarket(
            market="m1",
            condition_id="c1",
            question="Long Arb",
            volume=50_000,
            yes_bid=0.47,
            yes_ask=0.48,
            no_bid=0.48,
            no_ask=0.49,
            active=True,
        ),
        BinaryMarket(
            market="m2",
            condition_id="c2",
            question="Short Arb",
            volume=50_000,
            yes_bid=0.52,
            yes_ask=0.53,
            no_bid=0.50,
            no_ask=0.51,
            active=True,
        ),
        BinaryMarket(
            market="m3",
            condition_id="c3",
            question="No Arb",
            volume=50_000,
            yes_bid=0.49,
            yes_ask=0.50,
            no_bid=0.50,
            no_ask=0.51,
            active=True,
        ),
    ]

    client = StubPolymarketClient(markets)
    detector = ArbitragePureDetector(client, min_profit_threshold=0.005, min_market_volume=10_000)

    opps = asyncio.run(detector.scan_markets(limit=1000))

    assert len(opps) == 2
    assert {o.type for o in opps} == {"long", "short"}
    assert opps[0].profit >= opps[1].profit
    assert opps[0].market == "m1"  # long profit=3% > short profit=2%


def test_executor_long_profit_math_and_redeem() -> None:
    markets: List[BinaryMarket] = []
    client = StubPolymarketClient(markets)
    logger = StubLogger(infos=[], errors=[])
    executor = ArbitragePureExecutor(client, logger)

    arb = Arbitrage(
        type="long",
        market="m1",
        condition_id="c1",
        profit=0.03,
        yes_price=0.48,
        no_price=0.49,
        timestamp=0.0,
        question="Long Arb",
    )

    result = asyncio.run(executor.execute(arb, amount=10.0))
    assert result.success

    # Invest $10, buy s shares of YES and NO where s = 10/(0.97) and redeem s dollars.
    assert abs(result.invested - 10.0) < 1e-9
    assert result.received > 10.0
    assert result.profit > 0
    assert len(client.orders) == 2


def test_executor_short_profit_math() -> None:
    client = StubPolymarketClient([])
    logger = StubLogger(infos=[], errors=[])
    executor = ArbitragePureExecutor(client, logger)

    arb = Arbitrage(
        type="short",
        market="m2",
        condition_id="c2",
        profit=0.02,
        yes_price=0.52,
        no_price=0.50,
        timestamp=0.0,
        question="Short Arb",
    )

    result = asyncio.run(executor.execute(arb, amount=10.0))
    assert result.success
    assert abs(result.invested - 10.0) < 1e-9
    assert abs(result.received - 10.2) < 1e-9
    assert abs(result.profit - 0.2) < 1e-9
    assert len(client.orders) == 2
