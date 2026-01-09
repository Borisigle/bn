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
class BotConfig:
    """Config for the pure arbitrage bot."""

    polymarket_api_key: str
    polymarket_api_secret: str
    polymarket_host: str
    gamma_host: str

    starting_capital: float
    position_size: float
    min_profit_threshold: float
    min_market_volume: float

    market_scan_limit: int
    scan_interval_ms: int
    execution_delay_ms: int

    paper_trading: bool
    mock_mode: bool
    log_level: str

    gamma_rps: int

    @classmethod
    def load(cls, dotenv_path: Optional[str] = None) -> "BotConfig":
        load_dotenv(dotenv_path=dotenv_path)

        return cls(
            polymarket_api_key=os.getenv("POLYMARKET_API_KEY", ""),
            polymarket_api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
            polymarket_host=os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com"),
            gamma_host=os.getenv("GAMMA_HOST", "https://gamma-api.polymarket.com"),
            starting_capital=_getenv_float("STARTING_CAPITAL", _getenv_float("CAPITAL", 100.0)),
            position_size=_getenv_float("POSITION_SIZE", 10.0),
            min_profit_threshold=_getenv_float("MIN_PROFIT_THRESHOLD", 0.005),
            min_market_volume=_getenv_float("MIN_MARKET_VOLUME", 10_000.0),
            market_scan_limit=_getenv_int("MARKET_SCAN_LIMIT", 1000),
            scan_interval_ms=_getenv_int("SCAN_INTERVAL", 30_000),
            execution_delay_ms=_getenv_int("EXECUTION_DELAY", 1_000),
            paper_trading=_getenv_bool("PAPER_TRADING", True),
            mock_mode=_getenv_bool("MOCK_MODE", True),
            log_level=os.getenv("LOG_LEVEL", "info"),
            gamma_rps=_getenv_int("GAMMA_RPS", 5),
        )

    def validate(self) -> None:
        if self.starting_capital <= 0:
            raise ValueError("STARTING_CAPITAL must be > 0")
        if self.position_size <= 0:
            raise ValueError("POSITION_SIZE must be > 0")
        if self.min_profit_threshold <= 0:
            raise ValueError("MIN_PROFIT_THRESHOLD must be > 0")
        if self.scan_interval_ms <= 0:
            raise ValueError("SCAN_INTERVAL must be > 0")
        if self.execution_delay_ms < 0:
            raise ValueError("EXECUTION_DELAY must be >= 0")
        if self.market_scan_limit <= 0:
            raise ValueError("MARKET_SCAN_LIMIT must be > 0")
