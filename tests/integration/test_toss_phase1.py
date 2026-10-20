from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from ai_swing_bot.core.config import TossSettings
from ai_swing_bot.market.auth import TossAuth
from ai_swing_bot.market.models import BarInterval
from ai_swing_bot.market.realtime import TossWebSocketClient
from ai_swing_bot.market.toss import TossMarketDataProvider
from ai_swing_bot.storage import Database, MarketRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_TOSS_INTEGRATION") != "1",
        reason="set RUN_TOSS_INTEGRATION=1 for credentialed read-only API tests",
    ),
]


@pytest.mark.anyio
async def test_live_read_only_market_data_and_websocket(tmp_path: Path) -> None:
    settings = TossSettings.load()
    timeout = httpx.Timeout(10.0, connect=10.0, read=20.0)
    async with httpx.AsyncClient(
        base_url=settings.api_base_url,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        auth = TossAuth(settings, client)
        provider = TossMarketDataProvider(client, auth)
        quotes = await provider.get_quotes(["AAPL"])
        daily = await provider.get_candles("AAPL", BarInterval.ONE_DAY, count=2)
        minute = await provider.get_candles("AAPL", BarInterval.ONE_MINUTE, count=2)
        realtime = TossWebSocketClient(settings.websocket_url, auth)
        ack = await realtime.probe(
            realtime.build_declaration(trade_symbols=["AAPL"], orderbook_symbols=["AAPL"])
        )

    assert len(quotes) == 1
    assert daily and minute
    assert set(ack.subscribed) == {"trade:us:AAPL", "orderbook:us:AAPL"}
    assert not ack.rejected

    database = Database(tmp_path / "market.db")
    try:
        database.create_schema()
        repository = MarketRepository(database)
        assert repository.save_quotes(quotes) == 1
        assert repository.save_bars([*daily, *minute]) == len(daily) + len(minute)
    finally:
        database.close()
