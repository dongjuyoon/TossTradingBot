# Toss Securities Open API capabilities

Verified on 2026-10-20 against the canonical [OpenAPI JSON](https://openapi.tossinvest.com/openapi-docs/latest/openapi.json) (3.1.0, API 1.2.24), [AsyncAPI JSON](https://openapi.tossinvest.com/openapi-docs/latest/asyncapi.json) (3.0.0, API 1.2.2), and [official overview](https://openapi.tossinvest.com/openapi-docs/overview.md).

## Authentication and boundaries

- OAuth 2.0 Client Credentials: `POST /oauth2/token`, form-encoded `client_id`, `client_secret`, and `grant_type=client_credentials`.
- No refresh token is issued. Reissue on expiry; issuing a new token immediately invalidates the previous client token.
- REST base: `https://openapi.tossinvest.com`; Bearer token required for API calls.
- Account, asset, order, and conditional-order calls also require `X-Tossinvest-Account`.
- The calling public IP must be pre-registered; an unregistered IP receives 403.
- Phase 0 makes no credentialed or order request.

## Required capability map

| Requirement | Official capability | Status/constraint |
|---|---|---|
| US current price | `GET /api/v1/prices` | Supported; up to 200 comma-separated symbols |
| US daily bars | `GET /api/v1/candles?interval=1d` | Supported; max 200 bars/page, newest first |
| US minute bars | `GET /api/v1/candles?interval=1m` | Supported; max 200 bars/page, newest first |
| 15m / 1h bars | none | Must aggregate completed 1m bars locally |
| Recent trades | `GET /api/v1/trades` | Supported; same-day, max 50 records |
| Realtime trades | `trade:us` WebSocket channel | Supported |
| Realtime orderbook | `orderbook:us` WebSocket channel | Supported |
| Accounts | `GET /api/v1/accounts` | Supported |
| Holdings | `GET /api/v1/holdings` | Supported |
| Buying power | `GET /api/v1/buying-power` | Supported for KRW/USD cash-based amount |
| Orders/fills | `GET /api/v1/orders`, `GET /api/v1/orders/{orderId}` | Supported |
| Create/modify/cancel | `POST /api/v1/orders` and action endpoints | Supported by API but prohibited until separate approval |
| Realtime order event | `personal:order` WebSocket channel | Supported; account sequence is subscription code |
| FX | `GET /api/v1/exchange-rate` | KRW/USD supported |
| Commission | `GET /api/v1/commissions` | KR/US supported |
| US market calendar | `GET /api/v1/market-calendar/US` | Supported; includes day/pre/regular/after sessions |

Additional official endpoints cover stock master/warnings, rankings, sectors, market indicators, conditional orders, and Korea-only investor/program/short/credit/lending statistics.

## WebSocket protocol constraints

- Endpoint: `wss://openapi-ws.tossinvest.com/ws/v1`, TLS and Bearer handshake required.
- Subscription is declarative full-replace: each JSON array replaces the complete current set; `[]` unsubscribes all.
- Limits: 2 concurrent connections/account, 100 channel-symbol topics/connection, 5 declarations/second.
- Send text `PING` within 180 seconds; 60 seconds is recommended. Server data does not reset the idle timer.
- On disconnect use jittered exponential backoff, reconnect, and restore the full subscription declaration.
- A new third connection evicts the oldest. Order-event backpressure can close the connection.
- New buys must be blocked while realtime connection or data freshness is unhealthy.

## Rate limits and errors

Limits are per client and API group. Published values may change, so clients must read rate-limit response headers and honor 429/`Retry-After`. Groups separate auth, account, asset, stock, bulk stock, market data, chart data, orders, and related services. Known examples include AUTH 5 TPS, ACCOUNT 1 TPS, and MARKET_DATA_CHART 20 TPS.

Retry only idempotent reads after bounded exponential backoff. Do not blindly resubmit create/modify/cancel calls after a timeout because the server may already have accepted them.

## Important documentation discrepancy

One overview sentence still says the API is REST-only, but the canonical AsyncAPI and dedicated connection/channel documentation define a production WebSocket service. Implementation must treat the versioned OpenAPI/AsyncAPI schemas as source of truth and record the schema versions used.
