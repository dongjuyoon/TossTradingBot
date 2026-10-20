"""Configuration loading that keeps secrets out of logs and source control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required local configuration is missing or unsafe."""


def read_dotenv(path: Path) -> dict[str, str]:
    """Read a small dotenv subset without mutating the process environment."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True, repr=False)
class TossSettings:
    """Toss API connection settings with a redacted representation."""

    client_id: str
    client_secret: str
    api_base_url: str = "https://openapi.tossinvest.com"
    websocket_url: str = "wss://openapi-ws.tossinvest.com/ws/v1"

    def __repr__(self) -> str:
        return (
            "TossSettings(client_id='********', client_secret='********', "
            f"api_base_url={self.api_base_url!r}, websocket_url={self.websocket_url!r})"
        )

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> TossSettings:
        file_values = read_dotenv(dotenv_path or Path(".env"))

        def value(name: str, default: str = "") -> str:
            return os.getenv(name) or file_values.get(name, default)

        client_id = value("TOSS_CLIENT_ID")
        client_secret = value("TOSS_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ConfigurationError("Toss credentials are not configured")
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url=value("TOSS_API_BASE_URL", "https://openapi.tossinvest.com").rstrip("/"),
            websocket_url=value("TOSS_WS_URL", "wss://openapi-ws.tossinvest.com/ws/v1"),
        )
