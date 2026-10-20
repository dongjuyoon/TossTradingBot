# Phase 1 architecture boundary

Phase 1 implements Toss OAuth, validated current-price and 1-minute/daily candle reads, realtime US trade/orderbook subscriptions, bounded retries, rate limits, and SQLite persistence. It does not implement a broker, portfolio, strategy, scheduler, or order mutation.

Later phases must depend on explicit `MarketDataProvider`, `AccountProvider`, and `Broker` interfaces. The first broker implementation is `PaperBroker`; no live-order implementation is authorized.

The realtime connection is unhealthy until connected and recently receiving valid frames. Downstream trading code must fail closed whenever this health condition is false.
