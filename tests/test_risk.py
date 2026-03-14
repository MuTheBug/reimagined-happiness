"""Tests for risk management."""

from grid_trading_bot.config import Config
from grid_trading_bot.risk import RiskAction, RiskManager


def _make_config(**overrides):
    defaults = {
        "api_key": "test",
        "api_secret": "test",
        "symbol": "BTCUSDT",
        "upper_price": 50000.0,
        "lower_price": 40000.0,
        "grid_levels": 5,
        "total_investment": 1000.0,
        "dry_run": True,
    }
    defaults.update(overrides)
    return Config(**defaults)


class TestRiskManager:
    def test_continue_within_range(self):
        config = _make_config()
        rm = RiskManager(config)
        assert rm.evaluate(45000.0) == RiskAction.CONTINUE

    def test_stop_loss_triggered(self):
        config = _make_config(stop_loss_price=39000.0)
        rm = RiskManager(config)
        assert rm.evaluate(38000.0) == RiskAction.STOP_LOSS

    def test_stop_loss_exact(self):
        config = _make_config(stop_loss_price=39000.0)
        rm = RiskManager(config)
        assert rm.evaluate(39000.0) == RiskAction.STOP_LOSS

    def test_take_profit_triggered(self):
        config = _make_config(take_profit_price=55000.0)
        rm = RiskManager(config)
        assert rm.evaluate(56000.0) == RiskAction.TAKE_PROFIT

    def test_no_stop_loss_configured(self):
        config = _make_config()
        rm = RiskManager(config)
        assert rm.evaluate(1.0) == RiskAction.CONTINUE

    def test_no_take_profit_configured(self):
        config = _make_config()
        rm = RiskManager(config)
        assert rm.evaluate(999999.0) == RiskAction.CONTINUE
