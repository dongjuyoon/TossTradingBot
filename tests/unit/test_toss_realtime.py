from __future__ import annotations

import json
from datetime import timedelta

import pytest

from ai_swing_bot.market.errors import TossAPIError
from ai_swing_bot.market.realtime import (
    EventDeduplicator,
    OrderBookSnapshot,
    SubscriptionAck,
    TossWebSocketClient,
    TradeTick,
)


def test_declaration_is_full_replace_and_deduplicated() -> None:
    declaration = TossWebSocketClient.build_declaration(
        trade_symbols=["aapl", "AAPL"], orderbook_symbols=["MSFT"]
    )
    assert declaration[1] == {"type": "trade:us", "codes": ["AAPL"]}
    assert declaration[2] == {"type": "orderbook:us", "codes": ["MSFT"]}
    assert TossWebSocketClient.build_declaration() == []


def test_declaration_enforces_topic_limit() -> None:
    symbols = [f"S{index}" for index in range(51)]
    with pytest.raises(ValueError, match="100"):
        TossWebSocketClient.build_declaration(trade_symbols=symbols, orderbook_symbols=symbols)


def test_parse_ack_trade_orderbook_and_pong() -> None:
    client = object.__new__(TossWebSocketClient)
    client._deduplicator = EventDeduplicator()  # noqa: SLF001

    ack = client.parse_frame(
        json.dumps({"type": "subscriptions", "subscribed": ["trade:us:AAPL"], "rejected": []})
    )
    assert isinstance(ack, SubscriptionAck)

    trade = client.parse_frame(
        json.dumps(
            {
                "type": "message",
                "topic": "trade:us:AAPL",
                "data": {
                    "price": "250.1",
                    "volume": "2",
                    "timestamp": "2026-10-20T16:00:00-04:00",
                    "currency": "USD",
                },
            }
        )
    )
    assert isinstance(trade, TradeTick)
    assert trade.symbol == "AAPL"

    orderbook = client.parse_frame(
        json.dumps(
            {
                "type": "message",
                "topic": "orderbook:us:MSFT",
                "data": {
                    "timestamp": "2026-10-20T16:00:00-04:00",
                    "currency": "USD",
                    "asks": [{"price": "520", "volume": "10"}],
                    "bids": [{"price": "519.9", "volume": "8"}],
                },
            }
        )
    )
    assert isinstance(orderbook, OrderBookSnapshot)
    assert client.parse_frame('{"type":"pong"}') is None


def test_duplicate_event_is_dropped() -> None:
    client = object.__new__(TossWebSocketClient)
    client._deduplicator = EventDeduplicator()  # noqa: SLF001
    raw = json.dumps(
        {
            "type": "message",
            "topic": "trade:us:AAPL",
            "data": {
                "price": "250.1",
                "volume": "2",
                "timestamp": "2026-10-20T16:00:00-04:00",
                "currency": "USD",
            },
        }
    )
    assert isinstance(client.parse_frame(raw), TradeTick)
    assert client.parse_frame(raw) is None


def test_invalid_or_error_frames_fail_closed() -> None:
    client = object.__new__(TossWebSocketClient)
    client._deduplicator = EventDeduplicator()  # noqa: SLF001
    with pytest.raises(TossAPIError):
        client.parse_frame("not json")
    with pytest.raises(TossAPIError):
        client.parse_frame('{"type":"error","error":{"code":"server-shutdown"}}')


def test_disconnected_client_is_unhealthy() -> None:
    client = object.__new__(TossWebSocketClient)
    client._connected = False  # noqa: SLF001
    client._last_received_at = None  # noqa: SLF001
    assert client.is_healthy(max_age=timedelta(hours=1)) is False
