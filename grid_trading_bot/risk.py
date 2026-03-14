"""Risk management — stop loss, take profit, and exposure checks."""

from __future__ import annotations

import logging
from enum import Enum

from .config import Config

logger = logging.getLogger(__name__)


class RiskAction(str, Enum):
    CONTINUE = "continue"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class RiskManager:
    """Evaluates market price against configured risk thresholds."""

    def __init__(self, config: Config) -> None:
        self._stop_loss = config.stop_loss_price
        self._take_profit = config.take_profit_price
        self._lower = config.lower_price
        self._upper = config.upper_price

    def evaluate(self, current_price: float) -> RiskAction:
        """Check if the current price triggers a risk event."""
        if self._stop_loss is not None and current_price <= self._stop_loss:
            logger.warning("STOP LOSS triggered at %.8f (threshold %.8f)", current_price, self._stop_loss)
            return RiskAction.STOP_LOSS

        if self._take_profit is not None and current_price >= self._take_profit:
            logger.warning("TAKE PROFIT triggered at %.8f (threshold %.8f)", current_price, self._take_profit)
            return RiskAction.TAKE_PROFIT

        if current_price < self._lower or current_price > self._upper:
            logger.info("Price %.8f outside grid range [%.8f, %.8f]", current_price, self._lower, self._upper)

        return RiskAction.CONTINUE
