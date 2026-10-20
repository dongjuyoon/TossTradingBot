#!/usr/bin/env python3
"""Check Ollama availability and benchmark a model only when it is installed."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request


def request_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen3:8b"))
    parser.add_argument(
        "--base-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    parser.add_argument("--skip-inference", action="store_true")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    try:
        version = request_json(f"{base_url}/api/version")
        tags = request_json(f"{base_url}/api/tags")
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"[FAIL] Ollama unavailable: {exc}")
        return 1

    models = {str(item.get("name")) for item in tags.get("models", []) if isinstance(item, dict)}
    print(f"[PASS] Ollama server: {version.get('version', 'unknown')}")
    if args.model not in models:
        print(f"[WARN] Model {args.model!r} is not installed; inference test skipped")
        return 0
    if args.skip_inference:
        print(f"[PASS] Model present: {args.model}")
        return 0

    started = time.perf_counter()
    result = request_json(
        f"{base_url}/api/generate",
        {"model": args.model, "prompt": "Reply with exactly: OK", "stream": False},
    )
    elapsed = time.perf_counter() - started
    eval_count = int(result.get("eval_count", 0) or 0)
    eval_duration = int(result.get("eval_duration", 0) or 0)
    tokens_per_second = eval_count / (eval_duration / 1_000_000_000) if eval_duration else 0.0
    print(f"[PASS] Inference latency: {elapsed:.2f}s")
    print(f"[PASS] Generated tokens: {eval_count}; tokens/s: {tokens_per_second:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
