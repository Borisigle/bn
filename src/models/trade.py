from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Position:
    position_id: int
    market_id: str
    side: str  # "UP" | "DOWN"
    entry_price: float
    entry_time: datetime
    size_usd: float
    shares: float
    sl: float
    tp: float

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.shares


@dataclass(frozen=True)
class Trade:
    position_id: int
    market_id: str
    side: str
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    size_usd: float
    shares: float
    pnl: float
    reason: str
