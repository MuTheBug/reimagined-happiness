# Binance Grid Trading Bot

A Python grid trading bot for Binance that automatically places buy and sell limit orders at preset price intervals within a defined range.

## How Grid Trading Works

Grid trading divides a price range into evenly-spaced levels. Buy orders are placed below the current market price and sell orders above it. When a buy order fills, a sell order is placed one level up. When a sell order fills, a buy order is placed one level down. This captures profit from price oscillations within the range.

## Features

- **Smart symbol scanner** — auto-analyzes all USDT pairs to find the most profitable ranging symbol
- **Ranging behavior forecasting** — uses Hurst exponent, ADX, Bollinger Band oscillation, and grid backtesting to predict which symbols will be profitable for grid trading
- **Auto grid configuration** — automatically computes optimal upper/lower bounds and grid levels from price action (support/resistance via IQR analysis)
- **Arithmetic & geometric grids** — choose uniform price spacing or uniform percentage spacing
- **Risk management** — configurable stop-loss and take-profit thresholds
- **Dry-run mode** — simulate trading without placing real orders (enabled by default)
- **Testnet support** — test against the Binance testnet before going live
- **CLI & environment config** — configure via `.env` file, environment variables, or CLI flags

## Installation

```bash
# Recommended: use a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Or install as a package (gives you the grid-bot command)
pip install .
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

### Smart Scanner (recommended)

```bash
# Scan all USDT pairs and find the best symbol for grid trading
grid-bot --scan

# Auto-select the best symbol and start the bot immediately
grid-bot --auto

# Show top 20 candidates
grid-bot --scan --scan-top 20
```

The scanner analyzes each symbol using:
- **Hurst exponent** — detects mean-reverting behavior (H < 0.5 = price tends to revert to mean)
- **ADX (Average Directional Index)** — confirms ranging market (ADX < 25 = no strong trend)
- **Bollinger Band oscillation** — measures how frequently price bounces within bands
- **Grid backtest** — simulates grid trading on 7 days of hourly data to estimate real profit
- **Range consistency** — checks what % of candles stay within the detected range
- **Volume filter** — ensures sufficient liquidity (>$5M daily volume)

### Web Scanner Dashboard

Open `scanner.html` in any browser — no server required. It connects directly to Binance's public API, runs the full scanner analysis in JavaScript, and displays ranked recommendations with grid visualizations.

### Manual Mode

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
  scanner.py        - Symbol scanner with Hurst, ADX, backtest analysis
  config.py         - Configuration via pydantic-settings
  grid.py           - Grid level computation (arithmetic/geometric)
  exchange.py       - Binance API client wrapper
  order_manager.py  - Order lifecycle management
  risk.py           - Stop-loss / take-profit evaluation
  bot.py            - Main bot loop
  main.py           - CLI entry point
scanner.html          - Standalone web scanner dashboard (open in browser)
tests/
  test_scanner.py
  test_grid.py
  test_risk.py
  test_order_manager.py
```

## Disclaimer

This software is for educational purposes. Trading cryptocurrencies carries significant risk. Always start with dry-run mode and testnet before using real funds. The authors are not responsible for any financial losses.
