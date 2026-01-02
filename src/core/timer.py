from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _floor_to_15m(dt: datetime) -> datetime:
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


@dataclass
class TradeTimer:
    trading_until_minute: int = 13

    def __post_init__(self) -> None:
        if self.trading_until_minute < 0 or self.trading_until_minute > 14:
            raise ValueError("trading_until_minute must be between 0 and 14")
        self.market_start: datetime = _floor_to_15m(datetime.now(timezone.utc))

    def maybe_rollover(self) -> bool:
        now = datetime.now(timezone.utc)
        if now >= self.market_start + timedelta(minutes=15):
            self.market_start = _floor_to_15m(now)
            return True
        return False

    def market_elapsed(self) -> int:
        now = datetime.now(timezone.utc)
        elapsed = now - self.market_start
        return max(0, int(elapsed.total_seconds()))

    def get_market_status(self) -> str:
        elapsed = self.market_elapsed()
        if elapsed < self.trading_until_minute * 60:
            return "TRADING"
        if elapsed < 15 * 60:
            return "FORCE_CLOSE"
        return "WAITING"

    def get_time_remaining(self) -> int:
        elapsed = self.market_elapsed()
        remaining = self.trading_until_minute * 60 - elapsed
        return max(0, remaining)

    def is_trading_allowed(self) -> bool:
        return self.get_market_status() == "TRADING"

    def current_market_window(self) -> tuple[datetime, datetime]:
        start = self.market_start
        end = start + timedelta(minutes=15)
        return start, end
