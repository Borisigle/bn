from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Market:
    id: str
    symbol: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str
