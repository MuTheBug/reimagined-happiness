"""CLI entry point for the grid trading bot."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from .bot import GridBot
from .config import Config


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Binance Grid Trading Bot")
    parser.add_argument("--symbol", help="Trading pair (e.g. BTCUSDT)")
    parser.add_argument("--upper", type=float, help="Upper grid price")
    parser.add_argument("--lower", type=float, help="Lower grid price")
    parser.add_argument("--levels", type=int, help="Number of grid levels")
    parser.add_argument("--investment", type=float, help="Total investment in quote currency")
    parser.add_argument("--stop-loss", type=float, help="Stop loss price")
    parser.add_argument("--take-profit", type=float, help="Take profit price")
    parser.add_argument("--grid-type", choices=["arithmetic", "geometric"], default=None)
    parser.add_argument("--testnet", action="store_true", help="Use Binance testnet")
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (place real orders)")
    parser.add_argument("--log-level", default=None)

    args = parser.parse_args(argv)

    # Build config overrides from CLI args
    overrides: dict = {}
    if args.symbol:
        overrides["symbol"] = args.symbol
    if args.upper is not None:
        overrides["upper_price"] = args.upper
    if args.lower is not None:
        overrides["lower_price"] = args.lower
    if args.levels is not None:
        overrides["grid_levels"] = args.levels
    if args.investment is not None:
        overrides["total_investment"] = args.investment
    if args.stop_loss is not None:
        overrides["stop_loss_price"] = args.stop_loss
    if args.take_profit is not None:
        overrides["take_profit_price"] = args.take_profit
    if args.grid_type is not None:
        overrides["grid_type"] = args.grid_type
    if args.testnet:
        overrides["testnet"] = True
    if args.live:
        overrides["dry_run"] = False
    if args.log_level:
        overrides["log_level"] = args.log_level

    config = Config(**overrides)  # type: ignore[arg-type]
    setup_logging(config.log_level)

    bot = GridBot(config)

    def handle_signal(signum, frame):
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    bot.start()


if __name__ == "__main__":
    main()
