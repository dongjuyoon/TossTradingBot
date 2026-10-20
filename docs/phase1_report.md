# Phase 1 implementation report

Completed on 2026-10-20 against Toss OpenAPI 1.2.24 and AsyncAPI 1.2.2.

## Implemented

- OAuth 2.0 Client Credentials with cached tokens, expiry leeway, serialized refresh, and redacted errors.
- `MarketDataProvider` read-only interface and `TossMarketDataProvider` implementation.
- Current prices for up to 200 symbols and 1-minute/daily candles for US equities.
- Timezone-aware timestamps, exact decimal parsing, OHLC/volume validation, symbol normalization, and newest-first validation.
- Per-group rate limiting, bounded retries for reads, `Retry-After` support, and one-time 401 token refresh.
- SQLite WAL persistence for `market_snapshots` and `ohlcv_bars`, transactional inserts, UTC timestamp normalization, and duplicate prevention.
- WebSocket US trade/orderbook subscriptions with full-replace declarations, topic limits, text `PING`, validated frames, bounded deduplication, health state, reconnect, and subscription restoration.
- Read-only collection CLI at `scripts/run_market_data.py`.

## Verification

- Unit/default suite: 21 collected, 20 passed, 1 credentialed integration test skipped by default.
- Credentialed integration suite: 1 passed.
- Live AAPL collection: one price snapshot plus five daily and five 1-minute bars stored in `data/market.db`.
- Live WebSocket handshake accepted both `trade:us:AAPL` and `orderbook:us:AAPL`.
- Reopening the database retained `(1, 10)` snapshot/bar counts.
- Ruff lint and format checks passed.

No order create, modify, cancel, conditional-order, or personal-order WebSocket functionality was implemented or called.

## Deferred

- 15-minute and 1-hour aggregation belongs to Phase 2 indicator/data processing.
- Account/portfolio persistence and PaperBroker belong to Phase 5.
- Schema migrations, backups, and long-running operational monitoring will be added when their owning phases begin.
