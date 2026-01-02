from datetime import datetime, timezone

from src.core.risk_manager import RiskManager
from src.models.trade import Position


def test_sl_tp_calculation() -> None:
    rm = RiskManager(stop_loss=0.15, take_profit=0.30)
    sltp = rm.calculate_sl_tp(entry_price=0.50, side="UP")
    assert sltp["sl"] == 0.50 * 0.85
    assert sltp["tp"] == 0.50 * 1.30


def test_check_position_actions() -> None:
    rm = RiskManager(stop_loss=0.15, take_profit=0.30)

    p = Position(
        position_id=1,
        market_id="m1",
        side="UP",
        entry_price=0.50,
        entry_time=datetime.now(timezone.utc),
        size_usd=10.0,
        shares=20.0,
        sl=0.50 * 0.85,
        tp=0.50 * 1.30,
    )

    assert rm.check_position(p, current_price=0.65, time_remaining=10) == "TAKE_PROFIT"
    assert rm.check_position(p, current_price=0.40, time_remaining=10) == "STOP_LOSS"
    assert rm.check_position(p, current_price=0.50, time_remaining=0) == "FORCE_CLOSE"
    assert rm.check_position(p, current_price=0.50, time_remaining=10) == "HOLD"
