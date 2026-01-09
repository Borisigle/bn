from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from typing import Dict


if __package__ is None or __package__ == "":
    # Allow running via: python src/main.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core.bot_config import BotConfig
from src.core.config import Config
from src.core.polymarket_client import PolymarketClientService
from src.logger.console_logger import ConsoleLogger
from src.services.arbitrage_bot import ArbitrageBotService


def _exit_prices_from_market_prices(market_prices: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    def _pick(side: str) -> float:
        side_prices = market_prices.get(side, {})
        bid = float(side_prices.get("bid", 0.0) or 0.0)
        ask = float(side_prices.get("ask", 0.0) or 0.0)
        if bid > 0:
            return bid
        if ask > 0:
            return ask
        return 0.0001

    return {"UP": _pick("UP"), "DOWN": _pick("DOWN")}


async def arbitrage_pure_main() -> None:
    cfg = BotConfig.load()
    cfg.validate()

    logger = ConsoleLogger(log_level=os.getenv("LOG_LEVEL", "info"))

    poly = PolymarketClientService(
        api_key=cfg.polymarket_api_key,
        api_secret=cfg.polymarket_api_secret,
        host=cfg.polymarket_host,
        gamma_host=cfg.gamma_host,
        paper_trading=cfg.paper_trading,
        mock_mode=cfg.mock_mode,
    )
    poly.gamma_rate_limiter.max_calls = cfg.gamma_rps

    bot = ArbitrageBotService(poly, cfg, logger)

    stop_event = asyncio.Event()

    def _request_stop() -> None:
        bot.stop()
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # add_signal_handler is not available on some platforms.
            pass

    task = asyncio.create_task(bot.start())

    await stop_event.wait()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def legacy_main() -> None:
    """Legacy 15-minute BTC UP/DOWN strategy loop."""

    from src.connectors.binance_connector import BinanceConnector
    from src.connectors.polymarket_connector import PolymarketConnector
    from src.core.arbitrage_engine import ArbitrageEngine
    from src.core.position_manager import PositionManager
    from src.core.risk_manager import RiskManager
    from src.core.timer import TradeTimer

    cfg = Config.load()
    cfg.validate()

    logger = ConsoleLogger()

    timer = TradeTimer(trading_until_minute=cfg.trading_until_minute)
    binance = BinanceConnector(api_key=cfg.binance_api_key, api_secret=cfg.binance_api_secret, mock=cfg.mock_mode)
    polymarket = PolymarketConnector(
        api_key=cfg.polymarket_api_key,
        api_secret=cfg.polymarket_api_secret,
        host=cfg.polymarket_host,
        gamma_host=cfg.gamma_host,
        mock=cfg.mock_mode,
    )

    arb = ArbitrageEngine(spread_threshold=cfg.spread_threshold, price_move_threshold=cfg.price_move_threshold)
    risk = RiskManager(stop_loss=cfg.stop_loss, take_profit=cfg.take_profit)
    positions = PositionManager(initial_capital=cfg.capital)

    forced_close_logged = False
    last_position_log_ts = 0.0

    try:
        while True:
            if timer.maybe_rollover():
                forced_close_logged = False

            status = timer.get_market_status()
            seconds_to_forced_close = timer.get_time_remaining()

            market = polymarket.get_current_market()

            btc_price = binance.get_btc_price()
            if btc_price is None:
                logger.log_error("Unable to fetch BTC price")
                time.sleep(cfg.poll_interval_seconds)
                continue

            pct_change = binance.get_price_change(minutes=5)
            polymarket.update_signal(pct_change)

            market_prices = polymarket.get_market_prices(market.id)

            logger.log_price_update(btc_price, pct_change)
            logger.log_market(market.id, seconds_to_forced_close, status)
            logger.log_capital(positions.capital, len(positions.get_open_positions()))

            if status == "TRADING":
                opp = arb.detect_opportunity(btc_price=btc_price, market_prices=market_prices, btc_pct_change=pct_change)
                if opp:
                    logger.log_opportunity_detected(opp.spread, opp.side, opp.expected_prob, opp.entry_price)

                    already_in_market = positions.get_open_position_for_market(market.id) is not None
                    if not already_in_market and arb.should_enter(opp, capital_available=positions.capital):
                        cfg_size = float(cfg.position_size)
                        size_usd = positions.capital * cfg_size if 0 < cfg_size <= 1 else min(cfg_size, positions.capital)

                        sltp = risk.calculate_sl_tp(opp.entry_price, opp.side)
                        pos = positions.open_position(
                            market_id=market.id,
                            side=opp.side,
                            entry_price=opp.entry_price,
                            size_usd=size_usd,
                            sl=sltp["sl"],
                            tp=sltp["tp"],
                        )
                        logger.log_trade_opened(
                            pos.position_id,
                            pos.side,
                            pos.entry_price,
                            pos.size_usd,
                            pos.sl,
                            pos.tp,
                        )

                # Risk checks (SL/TP) while trading.
                for pos in positions.get_open_positions():
                    current_price = float(market_prices.get(pos.side, {}).get("bid", 0.0))
                    if current_price <= 0:
                        continue

                    action = risk.check_position(pos, current_price=current_price, time_remaining=seconds_to_forced_close)
                    if action == "HOLD":
                        now = time.time()
                        if now - last_position_log_ts >= 5:
                            last_position_log_ts = now
                            logger.log_position_update(
                                pos.position_id,
                                pos.side,
                                current_price,
                                positions.unrealized_pnl(pos, current_price),
                            )
                        continue

                    trade = positions.close_position(pos, exit_price=current_price, reason=action)
                    logger.log_trade_closed(trade.position_id, trade.reason, trade.pnl, positions.capital)

            elif status == "FORCE_CLOSE":
                if not forced_close_logged:
                    logger.log_forced_close()
                    forced_close_logged = True

                if positions.get_open_positions():
                    exit_prices = _exit_prices_from_market_prices(market_prices)
                    trades = positions.force_close_all(exit_prices, reason="FORCED_CLOSE")
                    for trade in trades:
                        logger.log_trade_closed(trade.position_id, trade.reason, trade.pnl, positions.capital)

            time.sleep(cfg.poll_interval_seconds)

    except KeyboardInterrupt:
        # graceful shutdown
        market = polymarket.get_current_market()
        market_prices = polymarket.get_market_prices(market.id)
        if positions.get_open_positions():
            exit_prices = _exit_prices_from_market_prices(market_prices)
            trades = positions.force_close_all(exit_prices, reason="SHUTDOWN")
            for trade in trades:
                logger.log_trade_closed(trade.position_id, trade.reason, trade.pnl, positions.capital)

        all_trades = positions.get_trades()
        total_pnl = sum(t.pnl for t in all_trades)
        wins = sum(1 for t in all_trades if t.pnl > 0)
        losses = sum(1 for t in all_trades if t.pnl < 0)
        logger.log_summary(len(all_trades), wins, losses, total_pnl, positions.capital)


def main() -> None:
    mode = os.getenv("BOT_MODE", "ARBITRAGE_PURE").strip().upper()
    if mode in {"LEGACY", "BTC_15M", "BTC15M"}:
        legacy_main()
        return

    asyncio.run(arbitrage_pure_main())


if __name__ == "__main__":
    main()
