"""Provider contracts that keep data access independent from strategy code."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ai_swing_bot.market.models import BarInterval, MarketQuote, OHLCVBar


class MarketDataProvider(ABC):
    """Read-only market data contract."""

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> list[MarketQuote]:
        """Return current quotes for one or more symbols."""

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        interval: BarInterval,
        *,
        count: int = 100,
        before: datetime | None = None,
        adjusted: bool = True,
    ) -> list[OHLCVBar]:
        """Return completed or current provider candles, newest first."""
