from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple


@dataclass
class BinanceConnector:
    api_key: str = ""
    api_secret: str = ""
    mock: bool = True

    _exchange: object = field(default=None, init=False, repr=False)
    _price_history: Deque[Tuple[float, float]] = field(default_factory=lambda: deque(maxlen=2000), init=False)
    _mock_price: float = field(default=45_000.0, init=False)

    def __post_init__(self) -> None:
        if not self.mock:
            import ccxt

            self._exchange = ccxt.binance(
                {
                    "enableRateLimit": True,
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                }
            )

    def get_btc_price(self) -> Optional[float]:
        ts = time.time()

        if self.mock:
            self._mock_price *= 1.0 + random.uniform(-0.0008, 0.0008)
            price = float(self._mock_price)
            self._price_history.append((ts, price))
            return price

        try:
            ticker = self._exchange.fetch_ticker("BTC/USDT")
            price = float(ticker["last"])
            self._price_history.append((ts, price))
            return price
        except Exception:
            if self._price_history:
                return self._price_history[-1][1]
            return None

    def get_price_change(self, minutes: int = 5) -> float:
        if not self._price_history:
            return 0.0

        now_ts, now_price = self._price_history[-1]
        target_ts = now_ts - (minutes * 60)

        past_price = None
        for ts, price in reversed(self._price_history):
            if ts <= target_ts:
                past_price = price
                break

        if past_price is None or past_price == 0:
            return 0.0

        return ((now_price - past_price) / past_price) * 100.0

    def is_price_moving(self, threshold: float = 2.0, minutes: int = 5) -> bool:
        return abs(self.get_price_change(minutes=minutes)) >= threshold
