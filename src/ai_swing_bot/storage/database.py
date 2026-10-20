"""SQLAlchemy engine and Phase 1 market-data tables."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, create_engine, event
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class MarketSnapshotRecord(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", "source", name="uq_market_snapshot_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[str] = mapped_column(String(40), index=True)
    last_price: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(12))
    source: Mapped[str] = mapped_column(String(32))
    session: Mapped[str] = mapped_column(String(16))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OHLCVBarRecord(Base):
    __tablename__ = "ohlcv_bars"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "interval",
            "timestamp",
            "adjusted",
            "source",
            name="uq_ohlcv_bar_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    interval: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[str] = mapped_column(String(40), index=True)
    open_price: Mapped[str] = mapped_column(String(40))
    high_price: Mapped[str] = mapped_column(String(40))
    low_price: Mapped[str] = mapped_column(String(40))
    close_price: Mapped[str] = mapped_column(String(40))
    volume: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(12))
    adjusted: Mapped[bool]
    source: Mapped[str] = mapped_column(String(32))
    session: Mapped[str] = mapped_column(String(16))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Database:
    """SQLite database configured for WAL, foreign keys, and bounded busy waits."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        url = URL.create("sqlite", database=str(path.resolve()))
        self.engine = create_engine(url, connect_args={"timeout": 5.0})
        self._configure_sqlite(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def set_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
            del connection_record
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()
