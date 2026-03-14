"""Core bot loop — monitors price and manages the grid lifecycle."""

from __future__ import annotations

import logging
import signal
import time

from .config import Config
from .exchange import ExchangeClient
from .order_manager import OrderManager
from .risk import RiskAction, RiskManager

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 10


class GridBot:
    """Main bot that ties together exchange, orders, and risk management."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._exchange = ExchangeClient(config)
        self._order_manager = OrderManager(config, self._exchange)
        self._risk_manager = RiskManager(config)
        self._running = False

    def start(self) -> None:
        """Initialize and start the grid bot."""
        current_price = self._exchange.get_current_price()
        logger.info(
            "Starting grid bot for %s | price=%.8f | range=[%.8f, %.8f] | levels=%d | investment=%.2f",
            self._config.symbol,
            current_price,
            self._config.lower_price,
            self._config.upper_price,
            self._config.grid_levels,
            self._config.total_investment,
        )

        if self._config.dry_run:
            logger.info("*** DRY RUN MODE — no real orders will be placed ***")

        self._order_manager.place_initial_orders(current_price)
        logger.info("Initial grid deployed: %s", self._order_manager.summary())

        self._running = True
        self._run_loop()

    def stop(self) -> None:
        """Gracefully stop the bot and cancel outstanding orders."""
        logger.info("Stopping bot...")
        self._running = False
        self._order_manager.cancel_all_orders()
        logger.info("Final summary: %s", self._order_manager.summary())

    def _run_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                price = self._exchange.get_current_price()
                action = self._risk_manager.evaluate(price)

                if action != RiskAction.CONTINUE:
                    logger.warning("Risk event: %s — shutting down", action.value)
                    self.stop()
                    break

                # In a production bot you would use websockets to detect fills.
                # This loop is a simplified polling approach for demonstration.
                time.sleep(POLL_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                self.stop()
                break
            except Exception:
                logger.exception("Error in main loop")
                time.sleep(POLL_INTERVAL_SECONDS)
