"""Tests for order manager."""

from unittest.mock import MagicMock

from grid_trading_bot.config import Config
from grid_trading_bot.exchange import ExchangeClient, OrderResult, OrderSide
from grid_trading_bot.order_manager import OrderManager


def _make_config(**overrides):
    defaults = {
        "api_key": "test",
        "api_secret": "test",
        "symbol": "BTCUSDT",
        "upper_price": 200.0,
        "lower_price": 100.0,
        "grid_levels": 3,
        "total_investment": 300.0,
        "dry_run": True,
    }
    defaults.update(overrides)
    return Config(**defaults)


def _mock_exchange(config):
    exchange = MagicMock(spec=ExchangeClient)
    call_count = 0

    def make_order(side, price, quantity):
        nonlocal call_count
        call_count += 1
        return OrderResult(
            order_id=str(call_count),
            symbol=config.symbol,
            side=side,
            price=price,
            quantity=quantity,
            status="NEW",
        )

    exchange.place_limit_order.side_effect = make_order
    return exchange


class TestOrderManager:
    def test_place_initial_orders(self):
        config = _make_config()
        exchange = _mock_exchange(config)
        om = OrderManager(config, exchange)

        om.place_initial_orders(current_price=150.0)

        # Grid: 100, 150, 200 — buy at 100, sell at 200, skip 150
        assert len(om.state.buy_orders) == 1
        assert len(om.state.sell_orders) == 1

    def test_handle_buy_fill_places_sell(self):
        config = _make_config()
        exchange = _mock_exchange(config)
        om = OrderManager(config, exchange)
        om.place_initial_orders(current_price=150.0)

        result = om.handle_buy_fill(level_index=0)
        assert result is not None
        assert result.side == OrderSide.SELL

    def test_handle_sell_fill_places_buy(self):
        config = _make_config()
        exchange = _mock_exchange(config)
        om = OrderManager(config, exchange)
        om.place_initial_orders(current_price=150.0)

        result = om.handle_sell_fill(level_index=2)
        assert result is not None
        assert result.side == OrderSide.BUY

    def test_summary(self):
        config = _make_config()
        exchange = _mock_exchange(config)
        om = OrderManager(config, exchange)
        om.place_initial_orders(current_price=150.0)

        s = om.summary()
        assert s["grid_levels"] == 3
        assert s["active_buy_orders"] == 1
        assert s["active_sell_orders"] == 1

    def test_cancel_all(self):
        config = _make_config()
        exchange = _mock_exchange(config)
        om = OrderManager(config, exchange)
        om.place_initial_orders(current_price=150.0)

        om.cancel_all_orders()
        assert len(om.state.buy_orders) == 0
        assert len(om.state.sell_orders) == 0
