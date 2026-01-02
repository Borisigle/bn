from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


def _getenv_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _getenv_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _getenv_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Config:
    binance_api_key: str
    binance_api_secret: str

    polymarket_api_key: str
    polymarket_api_secret: str
    polymarket_host: str
    gamma_host: str

    capital: float
    position_size: float
    take_profit: float
    stop_loss: float
    spread_threshold: float
    price_move_threshold: float
    trading_until_minute: int

    poll_interval_seconds: float

    paper_trading: bool
    mock_mode: bool

    @classmethod
    def load(cls, dotenv_path: Optional[str] = None) -> "Config":
        load_dotenv(dotenv_path=dotenv_path)

        return cls(
            binance_api_key=os.getenv("BINANCE_API_KEY", ""),
            binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
            polymarket_api_key=os.getenv("POLYMARKET_API_KEY", ""),
            polymarket_api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
            polymarket_host=os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com"),
            gamma_host=os.getenv("GAMMA_HOST", "https://gamma-api.polymarket.com"),
            capital=_getenv_float("CAPITAL", 100.0),
            position_size=_getenv_float("POSITION_SIZE", 0.10),
            take_profit=_getenv_float("TAKE_PROFIT", 0.30),
            stop_loss=_getenv_float("STOP_LOSS", 0.15),
            spread_threshold=_getenv_float("SPREAD_THRESHOLD", 0.05),
            price_move_threshold=_getenv_float("PRICE_MOVE_THRESHOLD", 2.0),
            trading_until_minute=_getenv_int("TRADING_UNTIL_MINUTE", 13),
            poll_interval_seconds=_getenv_float("POLL_INTERVAL_SECONDS", 1.0),
            paper_trading=_getenv_bool("PAPER_TRADING", True),
            mock_mode=_getenv_bool("MOCK_MODE", True),
        )

    def validate(self) -> None:
        if not (0 < self.position_size <= 1):
            raise ValueError("POSITION_SIZE must be in (0, 1].")
        if self.capital <= 0:
            raise ValueError("CAPITAL must be > 0")
        if self.trading_until_minute < 0 or self.trading_until_minute > 14:
            raise ValueError("TRADING_UNTIL_MINUTE must be between 0 and 14")
        if self.poll_interval_seconds <= 0:
            raise ValueError("POLL_INTERVAL_SECONDS must be > 0")
