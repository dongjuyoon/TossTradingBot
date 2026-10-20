"""OAuth 2.0 Client Credentials authentication for Toss Securities."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ai_swing_bot.core.config import TossSettings
from ai_swing_bot.market.errors import TossAPIError


class OAuthToken(BaseModel):
    """An access token whose value is redacted from repr and serialization logs."""

    model_config = ConfigDict(frozen=True)

    access_token: SecretStr
    token_type: str
    expires_at: datetime

    def is_valid(self, *, now: datetime | None = None, leeway_seconds: int = 60) -> bool:
        current = now or datetime.now(UTC)
        return current + timedelta(seconds=leeway_seconds) < self.expires_at


class TokenResponse(BaseModel):
    access_token: SecretStr
    token_type: str
    expires_in: int = Field(gt=0)


class TossAuth:
    """Cache one client token and serialize refreshes to avoid invalidation races."""

    def __init__(
        self,
        settings: TossSettings,
        client: httpx.AsyncClient,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._client = client
        self._now = now
        self._token: OAuthToken | None = None
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._token = None

    async def access_token(self) -> str:
        token = self._token
        if token and token.is_valid(now=self._now()):
            return token.access_token.get_secret_value()
        async with self._lock:
            token = self._token
            if token and token.is_valid(now=self._now()):
                return token.access_token.get_secret_value()
            self._token = await self._issue_token()
            return self._token.access_token.get_secret_value()

    async def _issue_token(self) -> OAuthToken:
        try:
            response = await self._client.post(
                "/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.client_id,
                    "client_secret": self._settings.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TimeoutException as exc:
            raise TossAPIError("Toss authentication timed out") from exc
        except httpx.HTTPError as exc:
            raise TossAPIError("Toss authentication transport failed") from exc
        if response.status_code != 200:
            raise TossAPIError("Toss authentication was rejected", status_code=response.status_code)
        try:
            payload = TokenResponse.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise TossAPIError("Toss authentication response was invalid") from exc
        issued_at = self._now()
        return OAuthToken(
            access_token=payload.access_token,
            token_type=payload.token_type,
            expires_at=issued_at + timedelta(seconds=payload.expires_in),
        )
