"""Configuration for the grid trading bot."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class GridType(str, Enum):
    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"


class Config(BaseSettings):
    """Bot configuration loaded from environment variables or .env file."""

    model_config = {"env_file": ".env", "env_prefix": "GRID_BOT_"}

    # Binance API credentials
    api_key: str = Field(description="Binance API key")
    api_secret: str = Field(description="Binance API secret")

    # Trading pair
    symbol: str = Field(default="BTCUSDT", description="Trading pair symbol")

    # Grid parameters (optional when using --scan)
    upper_price: float = Field(default=0.0, description="Upper bound of the grid")
    lower_price: float = Field(default=0.0, description="Lower bound of the grid")
    grid_levels: int = Field(default=10, ge=2, le=200, description="Number of grid levels")
    grid_type: GridType = Field(default=GridType.ARITHMETIC, description="Grid spacing type")

    # Position sizing
    total_investment: float = Field(default=1000.0, description="Total investment amount in quote currency")

    # Risk management
    stop_loss_price: float | None = Field(default=None, description="Stop loss price")
    take_profit_price: float | None = Field(default=None, description="Take profit price")

    # Operational
    testnet: bool = Field(default=False, description="Use Binance testnet")
    dry_run: bool = Field(default=True, description="Simulate orders without placing them")
    log_level: str = Field(default="INFO")

    @field_validator("upper_price")
    @classmethod
    def upper_must_exceed_lower(cls, v: float, info) -> float:
        lower = info.data.get("lower_price")
        # Skip validation when both are 0 (scan mode will set them)
        if v == 0.0 and (lower is None or lower == 0.0):
            return v
        if lower is not None and v <= lower:
            raise ValueError("upper_price must be greater than lower_price")
        return v

    @field_validator("stop_loss_price")
    @classmethod
    def stop_loss_below_lower(cls, v: float | None, info) -> float | None:
        if v is not None:
            lower = info.data.get("lower_price")
            if lower is not None and v >= lower:
                raise ValueError("stop_loss_price should be below lower_price")
        return v

    @field_validator("take_profit_price")
    @classmethod
    def take_profit_above_upper(cls, v: float | None, info) -> float | None:
        if v is not None:
            upper = info.data.get("upper_price")
            if upper is not None and v <= upper:
                raise ValueError("take_profit_price should be above upper_price")
        return v
