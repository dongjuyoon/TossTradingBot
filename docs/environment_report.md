# Phase 0 environment report

Checked on 2026-10-20 (America/Los_Angeles).

| Item | Result | Notes |
|---|---|---|
| macOS | PASS | macOS 26.6.2, arm64 |
| Python | PASS | Homebrew Python 3.12.15 at `/opt/homebrew/bin/python3.12` |
| Project virtualenv | PASS | `.venv` created with Python 3.12 |
| Git | PASS | Apple Git 2.50.1 available; project repository initialized |
| SQLite | PASS | system CLI 3.51.0; Python 3.12 `sqlite3` 3.54.1 |
| Ollama CLI/server | PASS | 0.40.6; local server responds at `127.0.0.1:11434` |
| `qwen3:8b` | BLOCKED | no local models are installed; no model download was performed automatically |
| TradingAgents | PARTIAL | official v0.7.0 requires Python >=3.11 and supports Ollama; resolver succeeds on Python 3.12 with `websockets==16.1.1`; not installed in Phase 0 |
| Toss credentials | BLOCKED | credentials were not provided; token/account checks were intentionally skipped |
| Toss schemas | PASS | canonical OpenAPI 1.2.24 and AsyncAPI 1.2.2 downloaded and validated |

## Compatibility findings

- TradingAgents v0.7.0 is a Git dependency rather than a PyPI release and is pinned to its official tag.
- `websockets==17.3` conflicts with TradingAgents' current `google-genai` dependency (`websockets<17`), so the project pins `16.1.1`.
- TradingAgents brings cloud-provider packages even when only Ollama is used. It remains an optional `ai` extra until Phase 4 to avoid unnecessary installation.
- Ollama's OpenAI-compatible endpoint is `http://localhost:11434/v1`; the model and server must exist before integration tests can run.

## User actions required for full external checks

1. Install the local model with `ollama pull qwen3:8b`, then run `.venv/bin/python scripts/check_ollama.py`.
2. Register a Toss Open API client and allowed public IP, copy `.env.example` to `.env`, and fill credentials locally.
3. Never paste credentials into logs or chat. Phase 1 should add an explicit authentication-only integration test.
