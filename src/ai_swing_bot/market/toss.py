"""Read-only Toss Securities REST market-data provider."""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_swing_bot.market.auth import TossAuth
from ai_swing_bot.market.errors import TossAPIError
from ai_swing_bot.market.interfaces import MarketDataProvider
from ai_swing_bot.market.models import BarInterval, MarketQuote, OHLCVBar
from ai_swing_bot.market.rate_limit import RateLimiters

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]+$")


class _QuotePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    timestamp: datetime
    last_price: Decimal = Field(alias="lastPrice")
    currency: str


class _CandlePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timestamp: datetime
    open_price: Decimal = Field(alias="openPrice")
    high_price: Decimal = Field(alias="highPrice")
    low_price: Decimal = Field(alias="lowPrice")
    close_price: Decimal = Field(alias="closePrice")
    volume: Decimal
    currency: str


class _NoopLimiter:
    async def wait(self) -> None:
        return None


class TossMarketDataProvider(MarketDataProvider):
    """Validated current-price and candle reads; never exposes order methods."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        auth: TossAuth,
        *,
        rate_limiters: RateLimiters | None = None,
        max_attempts: int = 3,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float], float] = lambda maximum: random.uniform(0, maximum),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._client = client
        self._auth = auth
        self._limits = rate_limiters
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._jitter = jitter

    async def get_quotes(self, symbols: list[str]) -> list[MarketQuote]:
        normalized = list(dict.fromkeys(self._validate_symbol(symbol) for symbol in symbols))
        if not normalized or len(normalized) > 200:
            raise ValueError("symbols must contain between 1 and 200 unique values")
        payload = await self._get(
            "/api/v1/prices",
            params={"symbols": ",".join(normalized)},
            limiter=self._limits.market_data if self._limits else _NoopLimiter(),
        )
        result = payload.get("result")
        if not isinstance(result, list):
            raise TossAPIError("Toss prices response was invalid")
        try:
            return [
                MarketQuote(
                    symbol=item.symbol,
                    timestamp=item.timestamp,
                    last_price=item.last_price,
                    currency=item.currency,
                )
                for raw in result
                for item in [_QuotePayload.model_validate(raw)]
            ]
        except (ValidationError, TypeError) as exc:
            raise TossAPIError("Toss prices response failed validation") from exc

    async def get_candles(
        self,
        symbol: str,
        interval: BarInterval,
        *,
        count: int = 100,
        before: datetime | None = None,
        adjusted: bool = True,
    ) -> list[OHLCVBar]:
        normalized = self._validate_symbol(symbol)
        if not 1 <= count <= 200:
            raise ValueError("count must be between 1 and 200")
        params: dict[str, Any] = {
            "symbol": normalized,
            "interval": interval.value,
            "count": count,
            "adjusted": str(adjusted).lower(),
        }
        if before is not None:
            if before.tzinfo is None or before.utcoffset() is None:
                raise ValueError("before must be timezone-aware")
            params["before"] = before.isoformat()
        payload = await self._get(
            "/api/v1/candles",
            params=params,
            limiter=self._limits.market_data_chart if self._limits else _NoopLimiter(),
        )
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("candles"), list):
            raise TossAPIError("Toss candles response was invalid")
        try:
            bars = [
                OHLCVBar(
                    symbol=normalized,
                    interval=interval,
                    timestamp=item.timestamp,
                    open_price=item.open_price,
                    high_price=item.high_price,
                    low_price=item.low_price,
                    close_price=item.close_price,
                    volume=item.volume,
                    currency=item.currency,
                    adjusted=adjusted,
                )
                for raw in result["candles"]
                for item in [_CandlePayload.model_validate(raw)]
            ]
        except (ValidationError, TypeError) as exc:
            raise TossAPIError("Toss candles response failed validation") from exc
        if any(bars[index].timestamp < bars[index + 1].timestamp for index in range(len(bars) - 1)):
            raise TossAPIError("Toss candles were not newest-first")
        return bars

    async def _get(self, path: str, *, params: dict[str, Any], limiter: Any) -> dict[str, Any]:
        refreshed = False
        for attempt in range(self._max_attempts):
            await limiter.wait()
            token = await self._auth.access_token()
            try:
                response = await self._client.get(
                    path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 == self._max_attempts:
                    raise TossAPIError("Toss market-data transport failed") from exc
                await self._sleep(self._backoff(attempt))
                continue
            if response.status_code == 401 and not refreshed:
                self._auth.invalidate()
                refreshed = True
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 == self._max_attempts:
                    raise TossAPIError(
                        "Toss market-data retries exhausted", status_code=response.status_code
                    )
                await self._sleep(self._retry_delay(response, attempt))
                continue
            if response.status_code != 200:
                raise TossAPIError(
                    "Toss market-data request was rejected", status_code=response.status_code
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise TossAPIError("Toss market-data response was not JSON") from exc
            if not isinstance(payload, dict):
                raise TossAPIError("Toss market-data response was invalid")
            return payload
        raise TossAPIError("Toss market-data request failed")

    def _backoff(self, attempt: int) -> float:
        return self._jitter(min(8.0, 2.0**attempt))

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return self._backoff(attempt)

    @staticmethod
    def _validate_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized or not SYMBOL_PATTERN.fullmatch(normalized):
            raise ValueError(f"invalid symbol: {symbol!r}")
        return normalized
