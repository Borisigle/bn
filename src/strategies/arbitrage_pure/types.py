from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


ArbitrageType = Literal["long", "short"]


@dataclass(frozen=True)
class BinaryMarket:
    """Minimal market snapshot needed for pure arbitrage scanning."""

    market: str
    condition_id: str
    question: str
    volume: float

    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float

    active: bool = True


@dataclass(frozen=True)
class Arbitrage:
    type: ArbitrageType
    market: str
    condition_id: str
    profit: float
    yes_price: float
    no_price: float
    timestamp: float
    question: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    market: str
    type: ArbitrageType
    invested: float
    received: float
    profit: float
    success: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class TradeLog:
    timestamp: datetime
    market: str
    type: ArbitrageType
    profit: float
    balance: float
    operation_time: float
