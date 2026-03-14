"""Grid calculation engine.

Computes grid levels and order quantities for arithmetic and geometric grids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import Config, GridType


@dataclass(frozen=True)
class GridLevel:
    """A single grid level with a price and order quantity."""

    index: int
    price: float
    quantity: float


def compute_grid_prices(config: Config) -> list[float]:
    """Return sorted grid prices from lower_price to upper_price (inclusive)."""
    n = config.grid_levels
    lower = config.lower_price
    upper = config.upper_price

    if config.grid_type == GridType.ARITHMETIC:
        step = (upper - lower) / (n - 1)
        return [round(lower + i * step, 8) for i in range(n)]

    # Geometric grid
    ratio = (upper / lower) ** (1 / (n - 1))
    return [round(lower * (ratio ** i), 8) for i in range(n)]


def compute_grid_levels(config: Config) -> list[GridLevel]:
    """Compute all grid levels with per-level quantities.

    The total investment is split equally across all grid levels in quote
    currency terms, then converted to base quantity at each level's price.
    """
    prices = compute_grid_prices(config)
    per_level_quote = config.total_investment / len(prices)

    levels = []
    for idx, price in enumerate(prices):
        qty = per_level_quote / price
        levels.append(GridLevel(index=idx, price=price, quantity=round(qty, 8)))
    return levels


def find_nearest_level(price: float, levels: list[GridLevel]) -> GridLevel:
    """Find the grid level whose price is closest to the given price."""
    return min(levels, key=lambda lv: abs(lv.price - price))
