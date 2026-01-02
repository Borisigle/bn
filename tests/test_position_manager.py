from src.core.position_manager import PositionManager


def test_open_and_close_position_updates_capital_and_pnl() -> None:
    pm = PositionManager(initial_capital=100.0)

    pos = pm.open_position(
        market_id="m1",
        side="UP",
        entry_price=0.50,
        size_usd=10.0,
        sl=0.40,
        tp=0.70,
    )

    assert pm.capital == 90.0
    assert pos.shares == 20.0

    trade = pm.close_position(pos, exit_price=0.60, reason="TAKE_PROFIT")
    assert trade.pnl == 2.0
    assert pm.capital == 102.0
    assert pm.get_open_positions() == []
    assert len(pm.get_trades()) == 1


def test_force_close_all() -> None:
    pm = PositionManager(initial_capital=100.0)

    pos1 = pm.open_position(market_id="m1", side="UP", entry_price=0.50, size_usd=10.0, sl=0.4, tp=0.7)
    pos2 = pm.open_position(market_id="m2", side="DOWN", entry_price=0.40, size_usd=10.0, sl=0.34, tp=0.52)

    trades = pm.force_close_all({"UP": 0.55, "DOWN": 0.35}, reason="FORCED_CLOSE")
    assert {t.position_id for t in trades} == {pos1.position_id, pos2.position_id}
    assert pm.get_open_positions() == []
