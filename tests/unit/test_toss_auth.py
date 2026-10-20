from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from ai_swing_bot.core.config import TossSettings
from ai_swing_bot.market.auth import TossAuth
from ai_swing_bot.market.errors import TossAPIError


def settings() -> TossSettings:
    return TossSettings(client_id="client", client_secret="secret")


@pytest.mark.anyio
async def test_auth_caches_token_and_redacts_secrets() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/oauth2/token"
        return httpx.Response(
            200,
            json={"access_token": "sensitive-token", "token_type": "Bearer", "expires_in": 3600},
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        auth = TossAuth(settings(), client)
        assert await auth.access_token() == "sensitive-token"
        assert await auth.access_token() == "sensitive-token"
        assert calls == 1
        assert "client_id='client'" not in repr(settings())
        assert "client_secret='secret'" not in repr(settings())


@pytest.mark.anyio
async def test_auth_serializes_concurrent_refreshes() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return httpx.Response(
            200, json={"access_token": "token", "token_type": "Bearer", "expires_in": 3600}
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        auth = TossAuth(settings(), client)
        assert await asyncio.gather(auth.access_token(), auth.access_token()) == ["token", "token"]
        assert calls == 1


@pytest.mark.anyio
async def test_auth_refreshes_expiring_token() -> None:
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    tokens = iter(("first", "second"))

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": next(tokens), "token_type": "Bearer", "expires_in": 120},
        )

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        auth = TossAuth(settings(), client, now=lambda: clock)
        assert await auth.access_token() == "first"
        clock += timedelta(seconds=61)
        assert await auth.access_token() == "second"


@pytest.mark.anyio
async def test_auth_error_does_not_expose_response_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="secret response")

    async with httpx.AsyncClient(
        base_url=settings().api_base_url, transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(TossAPIError, match="rejected") as caught:
            await TossAuth(settings(), client).access_token()
        assert "secret response" not in str(caught.value)
        assert caught.value.status_code == 401
