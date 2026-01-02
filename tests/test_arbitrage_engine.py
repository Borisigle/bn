from src.core.arbitrage_engine import ArbitrageEngine


def test_detect_opportunity_up() -> None:
    engine = ArbitrageEngine(spread_threshold=0.05, price_move_threshold=2.0)

    market_prices = {
        "UP": {"bid": 0.50, "ask": 0.52},
        "DOWN": {"bid": 0.48, "ask": 0.50},
    }

    opp = engine.detect_opportunity(btc_price=45_000.0, market_prices=market_prices, btc_pct_change=3.0)
    assert opp is not None
    assert opp.side == "UP"
    assert opp.entry_price == 0.52
    assert opp.spread > 0
    assert engine.should_enter(opp, capital_available=100.0)


def test_detect_opportunity_none_when_move_small() -> None:
    engine = ArbitrageEngine(spread_threshold=0.05, price_move_threshold=2.0)

    market_prices = {
        "UP": {"bid": 0.50, "ask": 0.52},
        "DOWN": {"bid": 0.48, "ask": 0.50},
    }

    opp = engine.detect_opportunity(btc_price=45_000.0, market_prices=market_prices, btc_pct_change=1.0)
    assert opp is None
