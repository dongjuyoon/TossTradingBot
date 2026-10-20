from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from ai_swing_bot.core.config import TossSettings
from ai_swing_bot.market.auth import TossAuth
from ai_swing_bot.market.errors import TossAPIError
from ai_swing_bot.market.models import BarInterval
from ai_swing_bot.market.toss import TossMarketDataProvider


def token_response() -> httpx.Response:
    return httpx.Response(
        200, json={"access_token": "token", "token_type": "Bearer", "expires_in": 3600}
    )


def settings() -> TossSettings:
    return TossSettings(client_id="client", client_secret="secret")


@pytest.mark.anyio
async def test_quotes_are_validated_and_symbols_are_deduplicated() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return token_response()
        assert request.url.params["symbols"] == "AAPL,MSFT"
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "AAPL",
                        "timestamp": "2026-10-20T10:00:00-04:00",
                        "lastPrice": "250.12",
                        "currency": "USD",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        provider = TossMarketDataProvider(client, TossAuth(settings(), client))
        quotes = await provider.get_quotes(["aapl", "AAPL", "msft"])
    assert quotes[0].symbol == "AAPL"
    assert str(quotes[0].last_price) == "250.12"
    assert quotes[0].timestamp.tzinfo is not None


@pytest.mark.anyio
async def test_candles_validate_order_and_ohlc() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return token_response()
        return httpx.Response(
            200,
            json={
                "result": {
                    "candles": [
                        {
                            "timestamp": "2026-10-20T10:01:00-04:00",
                            "openPrice": "10",
                            "highPrice": "12",
                            "lowPrice": "9",
                            "closePrice": "11",
                            "volume": "100",
                            "currency": "USD",
                        },
                        {
                            "timestamp": "2026-10-20T10:00:00-04:00",
                            "openPrice": "9",
                            "highPrice": "11",
                            "lowPrice": "8",
                            "closePrice": "10",
                            "volume": "80",
                            "currency": "USD",
                        },
                    ]
                }
            },
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        provider = TossMarketDataProvider(client, TossAuth(settings(), client))
        bars = await provider.get_candles("aapl", BarInterval.ONE_MINUTE, count=2)
    assert len(bars) == 2
    assert bars[0].timestamp > bars[1].timestamp
    assert bars[0].adjusted is True


@pytest.mark.anyio
async def test_401_invalidates_token_once() -> None:
    token_calls = 0
    price_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls, price_calls
        if request.url.path == "/oauth2/token":
            token_calls += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"token-{token_calls}",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        price_calls += 1
        if price_calls == 1:
            return httpx.Response(401)
        assert request.headers["Authorization"] == "Bearer token-2"
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "AAPL",
                        "timestamp": "2026-10-20T10:00:00-04:00",
                        "lastPrice": "250",
                        "currency": "USD",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        provider = TossMarketDataProvider(client, TossAuth(settings(), client))
        assert len(await provider.get_quotes(["AAPL"])) == 1
    assert token_calls == 2


@pytest.mark.anyio
async def test_429_honors_retry_after() -> None:
    calls = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path == "/oauth2/token":
            return token_response()
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0.25"})
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "AAPL",
                        "timestamp": "2026-10-20T10:00:00-04:00",
                        "lastPrice": "250",
                        "currency": "USD",
                    }
                ]
            },
        )

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        provider = TossMarketDataProvider(client, TossAuth(settings(), client), sleep=fake_sleep)
        await provider.get_quotes(["AAPL"])
    assert delays == [0.25]


@pytest.mark.anyio
async def test_invalid_payload_is_rejected() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return token_response()
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "AAPL",
                        "timestamp": "2026-10-20T10:00:00-04:00",
                        "lastPrice": "-1",
                        "currency": "USD",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        provider = TossMarketDataProvider(client, TossAuth(settings(), client))
        with pytest.raises(TossAPIError, match="validation"):
            await provider.get_quotes(["AAPL"])


@pytest.mark.anyio
async def test_before_must_be_timezone_aware() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return token_response()

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        provider = TossMarketDataProvider(client, TossAuth(settings(), client))
        with pytest.raises(ValueError, match="timezone-aware"):
            await provider.get_candles("AAPL", BarInterval.ONE_DAY, before=datetime(2026, 1, 1))
