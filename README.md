# Binance Grid Trading Bot

A Python grid trading bot for Binance that automatically places buy and sell limit orders at preset price intervals within a defined range.

## How Grid Trading Works

Grid trading divides a price range into evenly-spaced levels. Buy orders are placed below the current market price and sell orders above it. When a buy order fills, a sell order is placed one level up. When a sell order fills, a buy order is placed one level down. This captures profit from price oscillations within the range.

## Features

- **Arithmetic & geometric grids** — choose uniform price spacing or uniform percentage spacing
- **Risk management** — configurable stop-loss and take-profit thresholds
- **Dry-run mode** — simulate trading without placing real orders (enabled by default)
- **Testnet support** — test against the Binance testnet before going live
- **CLI & environment config** — configure via `.env` file, environment variables, or CLI flags

## Installation

```bash
pip install -e .
```

## Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Key settings:

| Variable | Description |
|---|---|
| `GRID_BOT_API_KEY` | Binance API key |
| `GRID_BOT_API_SECRET` | Binance API secret |
| `GRID_BOT_SYMBOL` | Trading pair (default: `BTCUSDT`) |
| `GRID_BOT_UPPER_PRICE` | Upper grid boundary |
| `GRID_BOT_LOWER_PRICE` | Lower grid boundary |
| `GRID_BOT_GRID_LEVELS` | Number of grid levels (default: 10) |
| `GRID_BOT_TOTAL_INVESTMENT` | Total investment in quote currency |
| `GRID_BOT_DRY_RUN` | Simulate orders (default: `true`) |

## Usage

```bash
# Using environment variables / .env file
grid-bot

# Using CLI flags
grid-bot --symbol ETHUSDT --lower 2000 --upper 3000 --levels 20 --investment 500

# Live trading (disables dry-run)
grid-bot --live

# Testnet
grid-bot --testnet
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## Project Structure

```
grid_trading_bot/
  config.py         - Configuration via pydantic-settings
  grid.py           - Grid level computation (arithmetic/geometric)
  exchange.py       - Binance API client wrapper
  order_manager.py  - Order lifecycle management
  risk.py           - Stop-loss / take-profit evaluation
  bot.py            - Main bot loop
  main.py           - CLI entry point
tests/
  test_grid.py
  test_risk.py
  test_order_manager.py
```

## Disclaimer

This software is for educational purposes. Trading cryptocurrencies carries significant risk. Always start with dry-run mode and testnet before using real funds. The authors are not responsible for any financial losses.
