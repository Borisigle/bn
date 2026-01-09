from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class AsyncRateLimiter:
    """Simple async sliding-window rate limiter.

    The limiter blocks when more than max_calls were made within period_seconds.
    """

    max_calls: int
    period_seconds: float

    _calls: deque[float] = field(default_factory=deque, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def acquire(self) -> None:
        if self.max_calls <= 0:
            return

        async with self._lock:
            now = time.monotonic()

            while self._calls and now - self._calls[0] >= self.period_seconds:
                self._calls.popleft()

            if len(self._calls) < self.max_calls:
                self._calls.append(now)
                return

            sleep_for = self.period_seconds - (now - self._calls[0])
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

            now = time.monotonic()
            while self._calls and now - self._calls[0] >= self.period_seconds:
                self._calls.popleft()

            self._calls.append(now)
