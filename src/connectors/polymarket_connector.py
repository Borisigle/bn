from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from src.models.market import Market


def _clamp_price(x: float) -> float:
    return max(0.0001, min(0.9999, x))


@dataclass
class PolymarketConnector:
    api_key: str = ""
    api_secret: str = ""
    host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    mock: bool = True

    _client: Any = field(default=None, init=False, repr=False)
    _signal_pct_change: float = field(default=0.0, init=False)
    _market_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.mock and self.api_key and self.api_secret:
            try:
                from py_clob_client.client import ClobClient

                self._client = ClobClient(host=self.host, api_key=self.api_key, api_secret=self.api_secret)
            except Exception:
                self._client = None

    def update_signal(self, btc_pct_change: float) -> None:
        self._signal_pct_change = float(btc_pct_change)

    def get_15min_btc_markets(self) -> List[Market]:
        if self.mock:
            return [self.get_current_market()]

        try:
            resp = requests.get(
                f"{self.gamma_host}/markets",
                params={"limit": 50, "active": "true"},
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return []

        items = payload.get("markets") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []

        markets: List[Market] = []
        for m in items:
            question = str(m.get("question") or m.get("title") or "")
            if "btc" not in question.lower() and "bitcoin" not in question.lower():
                continue
            if "15" not in question:
                continue

            market_id = str(m.get("id") or m.get("conditionId") or m.get("condition_id") or "")
            if not market_id:
                continue

            start = _parse_dt(m.get("startTime") or m.get("start_time") or m.get("createdAt") or m.get("created_at"))
            end = _parse_dt(m.get("endTime") or m.get("end_time") or m.get("resolveTime") or m.get("resolve_time"))

            markets.append(
                Market(
                    id=market_id,
                    symbol="BTC-15M",
                    start_time=start,
                    end_time=end,
                    status=str(m.get("status") or "ACTIVE"),
                )
            )
            self._market_cache[market_id] = m

        return markets

    def get_current_market(self) -> Market:
        now = datetime.now(timezone.utc)
        start = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        end = start + timedelta(minutes=15)

        if self.mock:
            market_id = f"paper-btc-15m-{start.strftime('%Y%m%d-%H%M')}"
            return Market(id=market_id, symbol="BTC-15M", start_time=start, end_time=end, status="ACTIVE")

        # In real mode, we try to find the most relevant active market.
        markets = self.get_15min_btc_markets()
        if markets:
            return markets[0]

        market_id = f"unknown-btc-15m-{start.strftime('%Y%m%d-%H%M')}"
        return Market(id=market_id, symbol="BTC-15M", start_time=start, end_time=end, status="UNKNOWN")

    def get_market_prices(self, market_id: str) -> Dict[str, Dict[str, float]]:
        if self.mock:
            # Small, signal-driven bias around 0.50 with a fixed spread.
            bias = max(-0.20, min(0.20, self._signal_pct_change / 10.0))
            up_mid = _clamp_price(0.5 + bias)
            down_mid = _clamp_price(1.0 - up_mid)
            half_spread = 0.01

            return {
                "UP": {"bid": _clamp_price(up_mid - half_spread), "ask": _clamp_price(up_mid + half_spread)},
                "DOWN": {
                    "bid": _clamp_price(down_mid - half_spread),
                    "ask": _clamp_price(down_mid + half_spread),
                },
            }

        try:
            market = self._market_cache.get(market_id)
            if market is None:
                resp = requests.get(f"{self.gamma_host}/markets/{market_id}", timeout=10)
                resp.raise_for_status()
                market = resp.json()

            prices = _extract_prices_from_gamma_market(market)
            if prices:
                return prices
        except Exception:
            pass

        return {"UP": {"bid": 0.0, "ask": 0.0}, "DOWN": {"bid": 0.0, "ask": 0.0}}

    def place_order(self, market_id: str, side: str, price: float, size: float) -> str:
        if self.mock or self._client is None:
            return f"paper-{uuid.uuid4().hex}"

        raise NotImplementedError(
            "Real trading is intentionally not enabled by default. Set PAPER_TRADING=true for paper mode."
        )

    def close_order(self, order_id: str) -> bool:
        return True

    def get_open_positions(self) -> List[dict[str, Any]]:
        return []

    def cancel_all_orders(self) -> bool:
        return True


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        except Exception:
            return None
    return None


def _extract_prices_from_gamma_market(market: Any) -> Optional[Dict[str, Dict[str, float]]]:
    if not isinstance(market, dict):
        return None

    outcomes = market.get("outcomes") or market.get("tokens") or market.get("clobTokens")
    if not isinstance(outcomes, list):
        return None

    out_map: Dict[str, Dict[str, float]] = {}
    for o in outcomes:
        label = str(o.get("outcome") or o.get("label") or o.get("name") or "").upper()
        if "UP" in label or label in {"YES", "HIGHER", "UP"}:
            side = "UP"
        elif "DOWN" in label or label in {"NO", "LOWER", "DOWN"}:
            side = "DOWN"
        else:
            continue

        bid = o.get("bestBid") or o.get("best_bid") or o.get("bid")
        ask = o.get("bestAsk") or o.get("best_ask") or o.get("ask")
        if bid is None or ask is None:
            continue

        out_map[side] = {"bid": float(bid), "ask": float(ask)}

    if "UP" in out_map and "DOWN" in out_map:
        return out_map

    return None
