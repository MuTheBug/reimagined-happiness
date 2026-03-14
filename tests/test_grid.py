"""Tests for grid calculation engine."""

import pytest

from grid_trading_bot.config import Config, GridType
from grid_trading_bot.grid import compute_grid_levels, compute_grid_prices, find_nearest_level


def _make_config(**overrides):
    defaults = {
        "api_key": "test",
        "api_secret": "test",
        "symbol": "BTCUSDT",
        "upper_price": 50000.0,
        "lower_price": 40000.0,
        "grid_levels": 5,
        "total_investment": 1000.0,
        "grid_type": GridType.ARITHMETIC,
        "dry_run": True,
    }
    defaults.update(overrides)
    return Config(**defaults)


class TestComputeGridPrices:
    def test_arithmetic_grid_count(self):
        config = _make_config(grid_levels=5)
        prices = compute_grid_prices(config)
        assert len(prices) == 5

    def test_arithmetic_grid_bounds(self):
        config = _make_config(lower_price=100.0, upper_price=200.0, grid_levels=3)
        prices = compute_grid_prices(config)
        assert prices[0] == 100.0
        assert prices[-1] == 200.0

    def test_arithmetic_grid_spacing(self):
        config = _make_config(lower_price=100.0, upper_price=200.0, grid_levels=3)
        prices = compute_grid_prices(config)
        assert prices == [100.0, 150.0, 200.0]

    def test_geometric_grid_bounds(self):
        config = _make_config(
            lower_price=100.0, upper_price=400.0, grid_levels=3, grid_type=GridType.GEOMETRIC
        )
        prices = compute_grid_prices(config)
        assert prices[0] == 100.0
        assert abs(prices[-1] - 400.0) < 1e-6

    def test_geometric_grid_ratio(self):
        config = _make_config(
            lower_price=100.0, upper_price=400.0, grid_levels=3, grid_type=GridType.GEOMETRIC
        )
        prices = compute_grid_prices(config)
        ratio_1 = prices[1] / prices[0]
        ratio_2 = prices[2] / prices[1]
        assert abs(ratio_1 - ratio_2) < 1e-6


class TestComputeGridLevels:
    def test_levels_have_quantity(self):
        config = _make_config(total_investment=1000.0, grid_levels=5)
        levels = compute_grid_levels(config)
        for level in levels:
            assert level.quantity > 0

    def test_total_quote_approximately_matches_investment(self):
        config = _make_config(total_investment=1000.0, grid_levels=5)
        levels = compute_grid_levels(config)
        total_quote = sum(lv.price * lv.quantity for lv in levels)
        assert abs(total_quote - 1000.0) < 0.01


class TestFindNearestLevel:
    def test_exact_match(self):
        config = _make_config(lower_price=100.0, upper_price=200.0, grid_levels=3)
        levels = compute_grid_levels(config)
        nearest = find_nearest_level(150.0, levels)
        assert nearest.price == 150.0

    def test_between_levels(self):
        config = _make_config(lower_price=100.0, upper_price=200.0, grid_levels=3)
        levels = compute_grid_levels(config)
        nearest = find_nearest_level(120.0, levels)
        assert nearest.price == 100.0  # closer to 100 than 150
