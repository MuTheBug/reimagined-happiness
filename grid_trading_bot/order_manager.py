"""Order management — places initial grid orders and handles fills."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import Config
from .exchange import ExchangeClient, OrderResult, OrderSide
from .grid import GridLevel, compute_grid_levels, find_nearest_level

logger = logging.getLogger(__name__)


@dataclass
class GridState:
    """Tracks active orders mapped to grid levels."""

    buy_orders: dict[int, OrderResult] = field(default_factory=dict)   # level_index -> order
    sell_orders: dict[int, OrderResult] = field(default_factory=dict)  # level_index -> order
    filled_buys: int = 0
    filled_sells: int = 0
    realised_pnl: float = 0.0


class OrderManager:
    """Manages the lifecycle of grid orders."""

    def __init__(self, config: Config, exchange: ExchangeClient) -> None:
        self._config = config
        self._exchange = exchange
        self._levels = compute_grid_levels(config)
        self._state = GridState()

    @property
    def state(self) -> GridState:
        return self._state

    @property
    def levels(self) -> list[GridLevel]:
        return self._levels

    def place_initial_orders(self, current_price: float) -> None:
        """Place buy orders below current price and sell orders above it."""
        for level in self._levels:
            if level.price < current_price:
                order = self._exchange.place_limit_order(
                    OrderSide.BUY, level.price, level.quantity
                )
                self._state.buy_orders[level.index] = order
            elif level.price > current_price:
                order = self._exchange.place_limit_order(
                    OrderSide.SELL, level.price, level.quantity
                )
                self._state.sell_orders[level.index] = order
            else:
                logger.info("Skipping level %d — price matches current market", level.index)

        logger.info(
            "Placed %d buy orders and %d sell orders",
            len(self._state.buy_orders),
            len(self._state.sell_orders),
        )

    def handle_buy_fill(self, level_index: int) -> OrderResult | None:
        """When a buy is filled, place a sell at the next grid level above."""
        self._state.filled_buys += 1
        self._state.buy_orders.pop(level_index, None)

        # Place sell at the next level up
        sell_level_index = level_index + 1
        if sell_level_index < len(self._levels):
            sell_level = self._levels[sell_level_index]
            buy_level = self._levels[level_index]
            order = self._exchange.place_limit_order(
                OrderSide.SELL, sell_level.price, buy_level.quantity
            )
            self._state.sell_orders[sell_level_index] = order

            profit = (sell_level.price - buy_level.price) * buy_level.quantity
            self._state.realised_pnl += profit
            logger.info(
                "Buy filled at level %d (%.8f), placed sell at level %d (%.8f), expected profit: %.4f",
                level_index, buy_level.price, sell_level_index, sell_level.price, profit,
            )
            return order
        return None

    def handle_sell_fill(self, level_index: int) -> OrderResult | None:
        """When a sell is filled, place a buy at the next grid level below."""
        self._state.filled_sells += 1
        self._state.sell_orders.pop(level_index, None)

        # Place buy at the level below
        buy_level_index = level_index - 1
        if buy_level_index >= 0:
            buy_level = self._levels[buy_level_index]
            order = self._exchange.place_limit_order(
                OrderSide.BUY, buy_level.price, buy_level.quantity
            )
            self._state.buy_orders[buy_level_index] = order
            logger.info(
                "Sell filled at level %d, placed buy at level %d (%.8f)",
                level_index, buy_level_index, buy_level.price,
            )
            return order
        return None

    def cancel_all_orders(self) -> None:
        """Cancel all active grid orders."""
        for idx, order in list(self._state.buy_orders.items()):
            try:
                self._exchange.cancel_order(order.order_id)
            except Exception:
                logger.exception("Error cancelling buy order at level %d", idx)
        for idx, order in list(self._state.sell_orders.items()):
            try:
                self._exchange.cancel_order(order.order_id)
            except Exception:
                logger.exception("Error cancelling sell order at level %d", idx)

        self._state.buy_orders.clear()
        self._state.sell_orders.clear()
        logger.info("All orders cancelled")

    def summary(self) -> dict:
        """Return a summary of the current grid state."""
        return {
            "active_buy_orders": len(self._state.buy_orders),
            "active_sell_orders": len(self._state.sell_orders),
            "filled_buys": self._state.filled_buys,
            "filled_sells": self._state.filled_sells,
            "realised_pnl": round(self._state.realised_pnl, 8),
            "grid_levels": len(self._levels),
        }
