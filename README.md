# Polymarket 15-Min BTC Up/Down Arbitrage Bot (Paper Trading)

A modular, production-oriented Python bot that monitors BTC price movement (Binance via CCXT), scans Polymarket 15-minute BTC Up/Down markets, and paper-trades a simple edge/spread strategy with risk controls.

## Features

- 15-minute market timer with forced close at minute 13
- Binance connector (CCXT) with rolling price-change calculation
- Polymarket connector (Gamma discovery + optional CLOB client)
- Paper trading with compounding capital (default $100)
- Risk management (stop loss / take profit / forced close)
- Pretty console logging + file logs (`logs/bot.log`)
- Unit tests for core logic

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env if desired

python -m src.main
```

### Modes

- `PAPER_TRADING=true` (default): simulated trades only.
- `MOCK_MODE=true` (default): no external API calls; BTC and Polymarket prices are simulated so the bot can run anywhere.
  - Set `MOCK_MODE=false` to use real Binance prices and attempt to discover Polymarket markets via Gamma.
  - Real trading via the Polymarket CLOB requires API keys and additional configuration.

## Notes / Disclaimer

This repository is for educational purposes. Markets are risky. Do not deploy with real funds without careful review, monitoring, and thorough testing.

## Running tests

```bash
pytest -q
```
