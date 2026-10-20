"""Transactional, idempotent persistence of validated market data."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from ai_swing_bot.market.models import MarketQuote, OHLCVBar
from ai_swing_bot.storage.database import Database, MarketSnapshotRecord, OHLCVBarRecord


class MarketRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save_quotes(self, quotes: Iterable[MarketQuote]) -> int:
        rows = [
            {
                "symbol": quote.symbol,
                "timestamp": quote.timestamp.astimezone(UTC).isoformat(),
                "last_price": str(quote.last_price),
                "currency": quote.currency,
                "source": quote.source,
                "session": quote.session.value,
            }
            for quote in quotes
        ]
        return self._insert_ignore(MarketSnapshotRecord, rows)

    def save_bars(self, bars: Iterable[OHLCVBar]) -> int:
        rows = [
            {
                "symbol": bar.symbol,
                "interval": bar.interval.value,
                "timestamp": bar.timestamp.astimezone(UTC).isoformat(),
                "open_price": str(bar.open_price),
                "high_price": str(bar.high_price),
                "low_price": str(bar.low_price),
                "close_price": str(bar.close_price),
                "volume": str(bar.volume),
                "currency": bar.currency,
                "adjusted": bar.adjusted,
                "source": bar.source,
                "session": bar.session.value,
            }
            for bar in bars
        ]
        return self._insert_ignore(OHLCVBarRecord, rows)

    def counts(self) -> tuple[int, int]:
        with self._database.session_factory() as session:
            quotes = session.scalar(select(func.count()).select_from(MarketSnapshotRecord)) or 0
            bars = session.scalar(select(func.count()).select_from(OHLCVBarRecord)) or 0
            return quotes, bars

    def _insert_ignore(self, model: type, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0
        with self._database.session_factory.begin() as session:
            result = session.execute(insert(model).values(rows).on_conflict_do_nothing())
            return max(0, result.rowcount or 0)
