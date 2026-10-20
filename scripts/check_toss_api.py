#!/usr/bin/env python3
"""Validate Toss public API schemas without touching account or order endpoints."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

OPENAPI_URL = "https://openapi.tossinvest.com/openapi-docs/latest/openapi.json"
ASYNCAPI_URL = "https://openapi.tossinvest.com/openapi-docs/latest/asyncapi.json"
REQUIRED_PATHS = {
    "/oauth2/token",
    "/api/v1/prices",
    "/api/v1/candles",
    "/api/v1/accounts",
    "/api/v1/holdings",
    "/api/v1/orders",
    "/api/v1/buying-power",
    "/api/v1/commissions",
}


def fetch_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": "ai-swing-bot-phase0/0.0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def validate(openapi: dict[str, object], asyncapi: dict[str, object]) -> list[str]:
    errors: list[str] = []
    paths = openapi.get("paths", {})
    if not isinstance(paths, dict) or not REQUIRED_PATHS.issubset(paths):
        missing = REQUIRED_PATHS.difference(paths if isinstance(paths, dict) else {})
        errors.append(f"missing REST paths: {sorted(missing)}")
    channels = asyncapi.get("channels", {})
    required_channels = {"realtime-trade", "realtime-orderbook", "realtime-order"}
    if not isinstance(channels, dict) or not required_channels.issubset(channels):
        missing = required_channels.difference(channels if isinstance(channels, dict) else {})
        errors.append(f"missing WebSocket channels: {sorted(missing)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    try:
        openapi = fetch_json(OPENAPI_URL)
        asyncapi = fetch_json(ASYNCAPI_URL)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"[FAIL] Unable to read official schemas: {exc}")
        return 1
    errors = validate(openapi, asyncapi)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    openapi_info = openapi.get("info", {})
    asyncapi_info = asyncapi.get("info", {})
    openapi_version = openapi_info.get("version") if isinstance(openapi_info, dict) else None
    asyncapi_version = asyncapi_info.get("version") if isinstance(asyncapi_info, dict) else None
    print(f"[PASS] OpenAPI {openapi_version} required paths present")
    print(f"[PASS] AsyncAPI {asyncapi_version} required channels present")
    print("[SAFE] No token, account, market-data, or order request was sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
