"""Binance exchange client wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from binance.client import Client
from binance.exceptions import BinanceAPIException

from .config import Config

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    status: str


class ExchangeClient:
    """Thin wrapper around the Binance client for placing and managing orders."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._dry_run = config.dry_run

        if config.testnet:
            self._client = Client(
                config.api_key,
                config.api_secret,
                testnet=True,
            )
        else:
            self._client = Client(config.api_key, config.api_secret)

        self._symbol_info: dict | None = None

    def get_current_price(self) -> float:
        """Fetch the current market price for the configured symbol."""
        ticker = self._client.get_symbol_ticker(symbol=self._config.symbol)
        return float(ticker["price"])

    def get_symbol_info(self) -> dict:
        """Fetch and cache exchange info for the trading symbol."""
        if self._symbol_info is None:
            info = self._client.get_symbol_info(self._config.symbol)
            if info is None:
                raise ValueError(f"Symbol {self._config.symbol} not found on exchange")
            self._symbol_info = info
        return self._symbol_info

    def place_limit_order(
        self, side: OrderSide, price: float, quantity: float
    ) -> OrderResult:
        """Place a limit order (or simulate in dry-run mode)."""
        symbol = self._config.symbol
        price_str = f"{price:.8f}"
        qty_str = f"{quantity:.8f}"

        if self._dry_run:
            logger.info(
                "[DRY RUN] %s %s %s @ %s", side.value, qty_str, symbol, price_str
            )
            return OrderResult(
                order_id="dry-run",
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                status="SIMULATED",
            )

        try:
            result = self._client.create_order(
                symbol=symbol,
                side=side.value,
                type="LIMIT",
                timeInForce="GTC",
                quantity=qty_str,
                price=price_str,
            )
            order = OrderResult(
                order_id=str(result["orderId"]),
                symbol=symbol,
                side=side,
                price=float(result["price"]),
                quantity=float(result["origQty"]),
                status=result["status"],
            )
            logger.info("Placed %s order %s @ %s", side.value, order.order_id, price_str)
            return order
        except BinanceAPIException as exc:
            logger.error("Failed to place %s order @ %s: %s", side.value, price_str, exc)
            raise

    def cancel_order(self, order_id: str) -> None:
        """Cancel an open order."""
        if self._dry_run:
            logger.info("[DRY RUN] Cancel order %s", order_id)
            return

        try:
            self._client.cancel_order(
                symbol=self._config.symbol, orderId=int(order_id)
            )
            logger.info("Cancelled order %s", order_id)
        except BinanceAPIException as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            raise

    def get_open_orders(self) -> list[dict]:
        """Get all open orders for the symbol."""
        return self._client.get_open_orders(symbol=self._config.symbol)

    def get_account_balance(self, asset: str) -> float:
        """Get free balance for a given asset."""
        balances = self._client.get_account()["balances"]
        for b in balances:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0
