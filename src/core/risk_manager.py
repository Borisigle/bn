from __future__ import annotations

from dataclasses import dataclass

from src.models.trade import Position


@dataclass
class RiskManager:
    stop_loss: float = 0.15
    take_profit: float = 0.30

    def calculate_sl_tp(self, entry_price: float, side: str) -> dict[str, float]:
        if entry_price <= 0:
            raise ValueError("entry_price must be > 0")

        sl = entry_price * (1.0 - self.stop_loss)
        tp = entry_price * (1.0 + self.take_profit)

        sl = max(0.0001, min(0.9999, sl))
        tp = max(0.0001, min(0.9999, tp))

        return {"sl": sl, "tp": tp}

    def check_position(self, position: Position, current_price: float, time_remaining: int) -> str:
        if time_remaining <= 0:
            return "FORCE_CLOSE"

        if current_price >= position.tp:
            return "TAKE_PROFIT"

        if current_price <= position.sl:
            return "STOP_LOSS"

        return "HOLD"
