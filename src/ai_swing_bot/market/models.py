"""Validated market-data domain models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BarInterval(StrEnum):
    ONE_MINUTE = "1m"
    ONE_DAY = "1d"


class MarketSession(StrEnum):
    """Session is unknown when the provider payload doesn't identify it."""

    UNKNOWN = "UNKNOWN"
    DAY = "DAY"
    PRE = "PRE"
    REGULAR = "REGULAR"
    AFTER = "AFTER"


class MarketQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: datetime
    last_price: Decimal = Field(gt=0)
    currency: str
    source: str = "toss"
    session: MarketSession = MarketSession.UNKNOWN

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class OHLCVBar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    interval: BarInterval
    timestamp: datetime
    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    currency: str
    adjusted: bool
    source: str = "toss"
    session: MarketSession = MarketSession.UNKNOWN

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_ohlc_range(self) -> OHLCVBar:
        if self.high_price < max(self.open_price, self.close_price, self.low_price):
            raise ValueError("high_price is below another OHLC value")
        if self.low_price > min(self.open_price, self.close_price, self.high_price):
            raise ValueError("low_price is above another OHLC value")
        return self
