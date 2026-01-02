from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from src.models.trade import Position, Trade


@dataclass
class PositionManager:
    initial_capital: float = 100.0

    capital: float = field(init=False)
    _positions: Dict[int, Position] = field(default_factory=dict, init=False)
    _trades: List[Trade] = field(default_factory=list, init=False)
    _next_id: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        self.capital = float(self.initial_capital)

    def open_position(
        self,
        market_id: str,
        side: str,
        entry_price: float,
        size_usd: float,
        sl: float,
        tp: float,
    ) -> Position:
        if size_usd <= 0:
            raise ValueError("size_usd must be > 0")
        if entry_price <= 0:
            raise ValueError("entry_price must be > 0")
        if self.capital < size_usd:
            raise ValueError("Insufficient capital")

        shares = size_usd / entry_price
        self.capital -= size_usd

        position = Position(
            position_id=self._next_id,
            market_id=market_id,
            side=side,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc),
            size_usd=size_usd,
            shares=shares,
            sl=sl,
            tp=tp,
        )

        self._positions[position.position_id] = position
        self._next_id += 1
        return position

    def close_position(self, position: Position, exit_price: float, reason: str) -> Trade:
        if exit_price <= 0:
            raise ValueError("exit_price must be > 0")

        exit_value = exit_price * position.shares
        pnl = exit_value - position.size_usd
        self.capital += exit_value

        trade = Trade(
            position_id=position.position_id,
            market_id=position.market_id,
            side=position.side,
            entry_price=position.entry_price,
            entry_time=position.entry_time,
            exit_price=exit_price,
            exit_time=datetime.now(timezone.utc),
            size_usd=position.size_usd,
            shares=position.shares,
            pnl=pnl,
            reason=reason,
        )

        self._positions.pop(position.position_id, None)
        self._trades.append(trade)
        return trade

    def get_open_positions(self) -> List[Position]:
        return list(self._positions.values())

    def get_trades(self) -> List[Trade]:
        return list(self._trades)

    def get_open_position_for_market(self, market_id: str) -> Optional[Position]:
        for p in self._positions.values():
            if p.market_id == market_id:
                return p
        return None

    def force_close_all(
        self,
        exit_prices: Union[float, Dict[str, float]],
        reason: str = "FORCED_CLOSE",
    ) -> List[Trade]:
        trades: List[Trade] = []
        for position in list(self._positions.values()):
            if isinstance(exit_prices, dict):
                exit_price = float(exit_prices[position.side])
            else:
                exit_price = float(exit_prices)
            trades.append(self.close_position(position, exit_price=exit_price, reason=reason))
        return trades

    def unrealized_pnl(self, position: Position, current_price: float) -> float:
        return (current_price - position.entry_price) * position.shares
