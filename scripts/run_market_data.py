#!/usr/bin/env python3
"""Fetch validated Toss market data and persist it to SQLite (read-only API use)."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

from ai_swing_bot.core.config import TossSettings
from ai_swing_bot.market.auth import TossAuth
from ai_swing_bot.market.models import BarInterval
from ai_swing_bot.market.rate_limit import RateLimiters
from ai_swing_bot.market.toss import TossMarketDataProvider
from ai_swing_bot.storage import Database, MarketRepository


async def collect(symbols: list[str], count: int, database_path: Path) -> tuple[int, int]:
    settings = TossSettings.load()
    timeout = httpx.Timeout(10.0, connect=10.0, read=20.0)
    async with httpx.AsyncClient(
        base_url=settings.api_base_url,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        auth = TossAuth(settings, client)
        provider = TossMarketDataProvider(client, auth, rate_limiters=RateLimiters())
        quotes = await provider.get_quotes(symbols)
        bars = []
        for symbol in symbols:
            bars.extend(
                await provider.get_candles(symbol, BarInterval.ONE_DAY, count=count, adjusted=True)
            )
            bars.extend(
                await provider.get_candles(
                    symbol, BarInterval.ONE_MINUTE, count=count, adjusted=True
                )
            )

    database = Database(database_path)
    try:
        database.create_schema()
        repository = MarketRepository(database)
        inserted_quotes = repository.save_quotes(quotes)
        inserted_bars = repository.save_bars(bars)
        return inserted_quotes, inserted_bars
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="*", default=["AAPL"])
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--database", type=Path, default=Path("data/market.db"))
    args = parser.parse_args()
    quotes, bars = asyncio.run(collect(args.symbols, args.count, args.database))
    print(f"[PASS] inserted current-price snapshots: {quotes}")
    print(f"[PASS] inserted OHLCV bars: {bars}")
    print(f"[PASS] database: {args.database}")
    print("[SAFE] read-only market-data endpoints only; no order endpoint called")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
