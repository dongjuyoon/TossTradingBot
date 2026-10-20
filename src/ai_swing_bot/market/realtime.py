"""Toss realtime trade and orderbook client with fail-closed health state."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from ai_swing_bot.market.auth import TossAuth
from ai_swing_bot.market.errors import TossAPIError
from ai_swing_bot.market.models import MarketSession
from ai_swing_bot.market.toss import SYMBOL_PATTERN


class SubscriptionRejection(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: str
    code: str
    message: str


class SubscriptionAck(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    id: str | None = None
    subscribed: list[str]
    rejected: list[SubscriptionRejection]

    @field_validator("type")
    @classmethod
    def require_type(cls, value: str) -> str:
        if value != "subscriptions":
            raise ValueError("not a subscriptions frame")
        return value


class TradeTick(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: datetime
    price: Decimal = Field(gt=0)
    volume: Decimal = Field(gt=0)
    currency: str
    source: str = "toss"
    session: MarketSession = MarketSession.UNKNOWN

    @field_validator("timestamp")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class OrderBookLevel(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)


class OrderBookSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: datetime
    currency: str
    asks: list[OrderBookLevel]
    bids: list[OrderBookLevel]
    source: str = "toss"
    session: MarketSession = MarketSession.UNKNOWN

    @field_validator("timestamp")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


RealtimeEvent = SubscriptionAck | TradeTick | OrderBookSnapshot


class EventDeduplicator:
    """Bounded content-key cache because Toss realtime frames have no sequence field."""

    def __init__(self, max_entries: int = 5000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._keys: OrderedDict[str, None] = OrderedDict()

    def is_duplicate(self, topic: str, data: dict[str, Any]) -> bool:
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        key = hashlib.sha256(f"{topic}\0{canonical}".encode()).hexdigest()
        if key in self._keys:
            self._keys.move_to_end(key)
            return True
        self._keys[key] = None
        if len(self._keys) > self._max_entries:
            self._keys.popitem(last=False)
        return False


class TossWebSocketClient:
    """Realtime client that reconnects and restores the entire desired subscription."""

    def __init__(
        self,
        url: str,
        auth: TossAuth,
        *,
        keepalive_seconds: float = 60,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float], float] = lambda maximum: random.uniform(0, maximum),
    ) -> None:
        self._url = url
        self._auth = auth
        self._keepalive_seconds = keepalive_seconds
        self._sleep = sleep
        self._jitter = jitter
        self._deduplicator = EventDeduplicator()
        self._connected = False
        self._last_received_at: datetime | None = None
        self._desired: list[dict[str, Any]] = []
        self._connection: ClientConnection | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def is_healthy(self, *, max_age: timedelta = timedelta(minutes=3)) -> bool:
        if not self._connected or self._last_received_at is None:
            return False
        return datetime.now(UTC) - self._last_received_at <= max_age

    @staticmethod
    def build_declaration(
        *, trade_symbols: list[str] | None = None, orderbook_symbols: list[str] | None = None
    ) -> list[dict[str, Any]]:
        trades = TossWebSocketClient._symbols(trade_symbols or [])
        books = TossWebSocketClient._symbols(orderbook_symbols or [])
        if len(trades) + len(books) > 100:
            raise ValueError("a connection supports at most 100 channel-symbol topics")
        declaration: list[dict[str, Any]] = [{"id": str(uuid4())}]
        if trades:
            declaration.append({"type": "trade:us", "codes": trades})
        if books:
            declaration.append({"type": "orderbook:us", "codes": books})
        if len(declaration) == 1:
            return []
        return declaration

    async def set_subscriptions(self, declaration: list[dict[str, Any]]) -> None:
        self._validate_declaration(declaration)
        self._desired = declaration
        if self._connection is not None:
            await self._connection.send(json.dumps(self._desired))

    async def probe(
        self, declaration: list[dict[str, Any]], *, timeout: float = 15
    ) -> SubscriptionAck:
        """Connect once and require a subscription acknowledgement."""
        self._validate_declaration(declaration)
        token = await self._auth.access_token()
        try:
            async with connect(
                self._url,
                additional_headers={"Authorization": f"Bearer {token}"},
                proxy=None,
                ping_interval=None,
                open_timeout=10,
            ) as websocket:
                await websocket.send(json.dumps(declaration))
                raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        except (TimeoutError, ConnectionClosed, InvalidHandshake, OSError) as exc:
            raise TossAPIError("Toss WebSocket probe failed") from exc
        event = self.parse_frame(raw)
        if not isinstance(event, SubscriptionAck):
            raise TossAPIError("Toss WebSocket did not acknowledge subscriptions")
        if event.rejected:
            raise TossAPIError("Toss WebSocket rejected one or more subscriptions")
        return event

    async def stream(self, declaration: list[dict[str, Any]]) -> AsyncIterator[RealtimeEvent]:
        """Reconnect forever on transient failures and restore full subscriptions."""
        await self.set_subscriptions(declaration)
        attempt = 0
        while True:
            token = await self._auth.access_token()
            try:
                async with connect(
                    self._url,
                    additional_headers={"Authorization": f"Bearer {token}"},
                    proxy=None,
                    ping_interval=None,
                    open_timeout=10,
                ) as websocket:
                    self._connection = websocket
                    self._connected = True
                    await websocket.send(json.dumps(self._desired))
                    keepalive = asyncio.create_task(self._keepalive(websocket))
                    attempt = 0
                    try:
                        async for raw in websocket:
                            event = self.parse_frame(raw)
                            if event is None:
                                continue
                            self._last_received_at = datetime.now(UTC)
                            yield event
                    finally:
                        keepalive.cancel()
                        await asyncio.gather(keepalive, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except (ConnectionClosed, InvalidHandshake, OSError, TossAPIError):
                self._connected = False
                self._connection = None
                delay = self._jitter(min(30.0, 2.0**attempt))
                attempt += 1
                await self._sleep(delay)
            finally:
                self._connected = False
                self._connection = None

    def parse_frame(self, raw: str | bytes) -> RealtimeEvent | None:
        try:
            frame = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise TossAPIError("Toss WebSocket frame was invalid JSON") from exc
        if not isinstance(frame, dict):
            raise TossAPIError("Toss WebSocket frame was invalid")
        frame_type = frame.get("type")
        if frame_type == "pong":
            return None
        if frame_type == "error":
            raise TossAPIError("Toss WebSocket returned an error frame")
        if frame_type == "subscriptions":
            try:
                return SubscriptionAck.model_validate(frame)
            except ValidationError as exc:
                raise TossAPIError("Toss subscription acknowledgement was invalid") from exc
        if frame_type != "message":
            raise TossAPIError("Toss WebSocket frame type was unknown")
        topic = frame.get("topic")
        data = frame.get("data")
        if not isinstance(topic, str) or not isinstance(data, dict):
            raise TossAPIError("Toss WebSocket message frame was invalid")
        if self._deduplicator.is_duplicate(topic, data):
            return None
        try:
            channel, market, symbol = topic.split(":", 2)
            if market != "us":
                raise ValueError("unexpected market")
            if channel == "trade":
                return TradeTick(symbol=symbol, **data)
            if channel == "orderbook":
                return OrderBookSnapshot(symbol=symbol, **data)
        except (ValueError, ValidationError, TypeError) as exc:
            raise TossAPIError("Toss WebSocket market message failed validation") from exc
        raise TossAPIError("Toss WebSocket topic was unknown")

    async def _keepalive(self, websocket: ClientConnection) -> None:
        while True:
            await self._sleep(self._keepalive_seconds)
            await websocket.send("PING")

    @staticmethod
    def _symbols(symbols: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols))
        if any(not symbol or not SYMBOL_PATTERN.fullmatch(symbol) for symbol in normalized):
            raise ValueError("invalid subscription symbol")
        return normalized

    @staticmethod
    def _validate_declaration(declaration: list[dict[str, Any]]) -> None:
        topic_count = 0
        for item in declaration:
            if not isinstance(item, dict):
                raise ValueError("subscription declaration items must be objects")
            if "type" not in item:
                continue
            if item["type"] not in {"trade:us", "orderbook:us"}:
                raise ValueError("only US trade and orderbook subscriptions are supported")
            codes = item.get("codes")
            if not isinstance(codes, list) or not codes:
                raise ValueError("subscription codes must be a non-empty list")
            TossWebSocketClient._symbols(codes)
            topic_count += len(codes)
        if topic_count > 100:
            raise ValueError("a connection supports at most 100 channel-symbol topics")
