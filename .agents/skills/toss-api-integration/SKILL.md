---
name: toss-api-integration
description: Implement or review Toss Securities Open API authentication, market data, account reads, and realtime subscriptions for this project. Use for Toss API work; never use it to authorize live orders.
---

# Toss API integration

Use the canonical versioned OpenAPI and AsyncAPI documents linked from `docs/api_capabilities.md`. Revalidate them before implementation because fields and limits can change.

- Keep credentials in `.env`; never print tokens, secrets, or account identifiers.
- Separate `MarketDataProvider`, `AccountProvider`, and `Broker` interfaces.
- Treat timestamps, market session, currency, source, and freshness as required data.
- Handle 429 using response headers and bounded jittered backoff. Retry reads only when safe.
- Never automatically retry an order mutation after an ambiguous timeout.
- Restore full WebSocket subscriptions after reconnect and block new buys while data is stale.
- This project is PAPER-only. Do not implement or invoke live order mutations without later explicit user approval.
