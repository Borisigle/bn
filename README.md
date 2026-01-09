# Polymarket Pure Arbitrage Bot

A modular TypeScript bot that monitors Polymarket for pure arbitrage opportunities (where the sum of YES and NO prices deviates from 1.0) and executes trades.

## Features

- Scans 1000+ markets for mispricings.
- Support for Long Arbitrage (YES + NO < 1) and Short Arbitrage (YES + NO > 1).
- Paper trading mode with auto-compounding.
- Mock mode for testing without external API calls.
- Built with TypeScript and Polymarket CLOB SDK.

## Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your private key and configuration
   ```

## Usage

- **Development mode**:
  ```bash
  npm run dev
  ```

- **Build**:
  ```bash
  npm run build
  ```

- **Start**:
  ```bash
  npm run start
  ```

## Configuration

The bot can be configured via `.env`:

- `POLYMARKET_PRIVATE_KEY`: Your wallet private key.
- `STARTING_CAPITAL`: Initial capital for paper trading.
- `POSITION_SIZE`: Amount per trade (if <= 1, interpreted as % of balance).
- `MIN_PROFIT_THRESHOLD`: Minimum profit to execute a trade.
- `PAPER_TRADING`: Set to `true` to simulate trades.
- `MOCK_MODE`: Set to `true` to use simulated market data.

## Logs

Expected logs:
- Scanning progress.
- Opportunity detection details.
- Execution status and profit/loss.
- Balance updates.
