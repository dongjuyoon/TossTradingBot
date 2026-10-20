from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import text

from ai_swing_bot.market.models import BarInterval, MarketQuote, OHLCVBar
from ai_swing_bot.storage import Database, MarketRepository


def quote() -> MarketQuote:
    return MarketQuote(
        symbol="AAPL",
        timestamp=datetime(2026, 10, 20, 14, 30, tzinfo=UTC),
        last_price=Decimal("250.12"),
        currency="USD",
    )


def bar() -> OHLCVBar:
    return OHLCVBar(
        symbol="AAPL",
        interval=BarInterval.ONE_DAY,
        timestamp=datetime(2026, 10, 20, tzinfo=UTC),
        open_price=Decimal("245"),
        high_price=Decimal("252"),
        low_price=Decimal("244"),
        close_price=Decimal("250.12"),
        volume=Decimal("1000000"),
        currency="USD",
        adjusted=True,
    )


def test_repository_enables_wal_and_ignores_duplicates(tmp_path) -> None:
    path = tmp_path / "market.db"
    database = Database(path)
    database.create_schema()
    repository = MarketRepository(database)

    assert repository.save_quotes([quote()]) == 1
    assert repository.save_quotes([quote()]) == 0
    assert repository.save_bars([bar()]) == 1
    assert repository.save_bars([bar()]) == 0
    assert repository.counts() == (1, 1)
    with database.engine.connect() as connection:
        assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    database.close()

    reopened = Database(path)
    reopened.create_schema()
    assert MarketRepository(reopened).counts() == (1, 1)
    reopened.close()
