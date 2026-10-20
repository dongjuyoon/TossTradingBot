---
name: trading-safety-review
description: Review order, portfolio, scheduler, recovery, and AI decision changes for trading safety. Use before paper execution and for every future broker-related change.
---

# Trading safety review

Fail closed for stale or invalid data, unclear market state, API or DB failure, duplicate intent, insufficient cash, or exceeded limits.

- Keep risk rules deterministic and independent of AI. AI may propose but cannot override them.
- Enforce PAPER mode at composition boundaries; missing configuration must never select live trading.
- Give each order intent an idempotency key and reconcile ambiguous outcomes before any retry.
- Validate price, currency, session, timestamp, position, cash, concentration, and planned loss.
- Persist intent, decision basis, order lifecycle, fills, and errors transactionally where feasible.
- On restart, reconcile state before accepting new buys.
- Test duplicates, stale quotes, disconnects, partial fills, rejects, DB failure, and recovery.
- Stop and request explicit user approval before adding any live-order capability.
